import json
import logging
from operator import contains
import os
import re
import resource
from typing import Any, Dict, List, cast

import jsondiff
from jsondiff import symbols
import yaml

from embeddings.embeddings_engine import EmbeddingsEngine
from validation.severity import Severity, analyze_component_severity, get_issue_type



class ManifestsValidator:
    def __init__(self, embeddings_engine: EmbeddingsEngine):
        self.logger = logging.getLogger(__name__)
        self.embeddings_engine = embeddings_engine

    def validate(
        self, analyzed_cluster_path: str, reference_manifests_path: str
    ) -> Dict[str, Any]:
        reference_cluster = self._generate_cluster(reference_manifests_path)
        analyzed_cluster = self._generate_cluster(analyzed_cluster_path)
        return self._validate_microservices(analyzed_cluster, reference_cluster)

    def _generate_cluster(self, manifests_path: str) -> Any:
        """Generate a cluster object from the manifests."""
        if not os.path.isdir(manifests_path):
            raise NotADirectoryError(
                f"Manifests path is not a directory: {manifests_path}"
            )

        cluster = {}
        supporting_resources = {}

        # First pass: collect all resources
        for root, dir, files in os.walk(manifests_path):
            for file in files:
                if file.endswith(".yaml") or file.endswith(".yml"):
                    with open(os.path.join(root, file), "r") as f:
                        try:
                            documents = yaml.safe_load_all(
                                f
                            )  # This handles multiple documents
                            for resource in documents:
                                if resource and isinstance(resource, dict):
                                    resource_type = resource.get("kind", "").lower()
                                    resource_name = resource.get("metadata", {}).get(
                                        "name", "unknown"
                                    )

                                    # Get microservice name from labels or resource name
                                    microservice_name = self._get_microservice_name(
                                        resource
                                    )

                                    if resource_type in [
                                        "deployment",
                                        "statefulset",
                                        "pod",
                                        "job",
                                        "daemonset",
                                        "service",
                                        "ingress",
                                        "persistentvolumeclaim",
                                        "persistentvolume",
                                        "serviceaccount",
                                    ]:
                                        cluster.setdefault(microservice_name, {})

                                        # Store resource by type
                                        cluster[microservice_name][
                                            resource_type
                                        ] = resource

                                    elif resource_type in ["configmap", "secret"]:
                                        # Supporting resources - store separately for merging
                                        supporting_resources[resource_name] = resource
                        except yaml.YAMLError as e:
                            raise ValueError(f"Error parsing YAML file {file}: {e}")

        # Second pass: merge supporting resources into primary resources
        for microservice_name, resources in cluster.items():
            for resource_name, resource in resources.items():
                self._merge_supporting_resources(resource, supporting_resources)
        self._sort_lists(cluster)
        return cluster

    def _merge_supporting_resources(
        self, resource: Dict[str, Any], supporting_resources: Dict[str, Any]
    ):
        """Merge supporting resources into the primary resource."""
        resource_type = resource.get("kind", "").lower()

        if resource_type in ["deployment", "statefulset", "daemonset"]:
            # Merge into pod template
            pod_spec = resource.get("spec", {}).get("template", {}).get("spec", {})
            self._merge_pod_supporting_resources(pod_spec, supporting_resources)
        elif resource_type in ["pod", "job"]:
            # Merge directly into pod spec
            pod_spec = resource.get("spec", {})
            self._merge_pod_supporting_resources(pod_spec, supporting_resources)

    def _merge_pod_supporting_resources(
        self, pod_spec: Dict[str, Any], supporting_resources: Dict[str, Any]
    ):
        """Merge supporting resources into pod spec."""
        containers = pod_spec.get("containers", [])

        for container in containers:
            # Merge ConfigMaps and Secrets into env vars
            self._merge_env_vars(container, supporting_resources)
        
    def _merge_env_vars(
        self, container: Dict[str, Any], supporting_resources: Dict[str, Any]
    ):
        """Merge ConfigMap and Secret references into actual env vars."""
        if "env" not in container:
            container["env"] = []

        # Handle envFrom (ConfigMap/Secret references)
        env_from = container.get("envFrom", [])
        for env_source in env_from:
            if "configMapRef" in env_source:
                cm_name = env_source["configMapRef"]["name"]
                if cm_name in supporting_resources:
                    cm_data = supporting_resources[cm_name].get("data", {})
                    for key, value in cm_data.items():
                        container["env"].append({"name": key, "value": value})

            elif "secretRef" in env_source:
                secret_name = env_source["secretRef"]["name"]
                if secret_name in supporting_resources:
                    secret_data = supporting_resources[secret_name].get("data", {})
                    for key, value in secret_data.items():
                        container["env"].append({"name": key, "value": value})

        # Handle individual env var references
        for env_var in container.get("env", []):
            if "valueFrom" in env_var:
                value_from = env_var["valueFrom"]
                if "configMapKeyRef" in value_from:
                    cm_name = value_from["configMapKeyRef"]["name"]
                    key = value_from["configMapKeyRef"]["key"]
                    if cm_name in supporting_resources:
                        cm_data = supporting_resources[cm_name].get("data", {})
                        env_var["value"] = cm_data.get(key, "")
                        del env_var["valueFrom"]

                elif "secretKeyRef" in value_from:
                    secret_name = value_from["secretKeyRef"]["name"]
                    key = value_from["secretKeyRef"]["key"]
                    if secret_name in supporting_resources:
                        secret_data = supporting_resources[secret_name].get("data", {})
                        env_var["value"] = secret_data.get(key, "")
                        del env_var["valueFrom"]

        # Remove envFrom since we've merged everything
        if "envFrom" in container:
            del container["envFrom"]

    def _sort_lists(self, cluster: Dict[str, Any]):
        # Sort env vars and other lists for consistency
        for microservice_name, resources in cluster.items():
            for resource_name, resource in resources.items():
                if "spec" in resource and "template" in resource["spec"]:
                    pod_spec = resource["spec"]["template"].get("spec", {})
                    if "containers" in pod_spec:
                        for container in pod_spec["containers"]:
                            if "env" in container:
                                container["env"].sort(key=lambda x: x.get("name", ""))
                            if "ports" in container:
                                container["ports"].sort(key=lambda x: x.get("containerPort", 0))
                            if "volumeMounts" in container:
                                container["volumeMounts"].sort(
                                    key=lambda x: x.get("name", "")
                                )
                elif "env" in resource:
                    resource["env"].sort(key=lambda x: x.get("name", ""))

    def _validate_microservices(
        self, analyzed_cluster: Dict[str, Dict], reference_cluster: Dict[str, Dict]
    ) -> Dict[str, Any]:
        """Validate microservices by comparing a target manifests with a reference."""
        diff = jsondiff.diff(reference_cluster,analyzed_cluster, syntax="explicit")
        summary = {
            "resources_analyzed": [],
            "resources_extra": {},  # Analyzed has but reference doesn't
            "resources_missing": {},  # Reference has but Analyzed doesn't
            "resource_differences": {},  # Value differences
        }
        # Process each microservice in the diff
        for verb, action in diff.items():
            if verb is symbols.insert:
                if isinstance(action, dict):
                    for microservice, resource in action.items():
                        summary["resources_extra"].setdefault(microservice, [])
                        summary["resources_extra"][microservice].append(
                            {"path": microservice, "value": resource}
                        )
                        summary["resources_analyzed"].append(microservice)
            elif verb is symbols.update:
                if isinstance(action, dict):
                    for microservice, intervention in action.items():
                        summary["resources_analyzed"].append(microservice)
                        summary["resources_extra"][microservice] = []
                        summary["resources_missing"][microservice] = []
                        summary["resource_differences"][microservice] = []
                        self.logger.debug(
                            f"Processing microservice {microservice} with intervention {intervention}"
                        )
                        self._process_diff(
                            microservice,
                            intervention,
                            summary,
                            f"{microservice}",
                            reference_cluster,
                        )
            elif verb is symbols.delete:

                if isinstance(action, list):
                    for microservice in action:
                        summary["resources_analyzed"].append(microservice)
                        summary["resources_missing"][microservice] = {
                            "path": microservice,
                            "value": reference_cluster[microservice],
                        }
        return summary

    def _get_microservice_name(self, resource: Dict[str, Any]) -> str:
        """Extract the microservice name from the resource."""
        # Try to get the microservice name from labels or metadata
        name = resource.get("metadata", {}).get("name", None)
        if not name:
            # Fallback to a generic name if not found
            raise ValueError("Resource does not have a valid name or metadata.")
        return name

    def _process_diff(
        self,
        microservice: str,
        diff: Dict[str, Any],
        summary: Dict[str, Any],
        path: str,
        cluster: Dict[str, Any],
    ):
        """Process diff recursively."""
        for key, value in diff.items():

            if key is symbols.insert:
                # Analyzed has extra fields that reference doesn't have
                self.logger.debug(f"Analyzing insert key {value}")

                summary["resources_extra"][microservice].append(
                    {"path": path, "value": value}  # Use parent path, not current_path
                )
            elif key is symbols.delete:
                # Analyzed is missing fields that reference has
                # Delete value is always a list of keys of deleted elements
                self.logger.debug(f"Analyzing delete key {value}")

                content = self._get_manifest_value(cluster, path.split("//")[:], value)
                summary["resources_missing"][microservice].append(
                    {"path": path, "value": content}  # Use parent path, not current_path
                )
            elif key is symbols.update:
                # Both have the field but with different values/structure
                if isinstance(value, dict):
                    self.logger.debug(f"Analyzing update key {value}")

                    self._process_diff(microservice, value, summary, path, cluster)
                else: 
                    self.logger.warning(f"Update non processed {value}")

            else:
                # Regular field name - continue recursion
                current_path = f"{path}//{key}" if path != "/" else f"//{key}"
                if isinstance(value, dict):
                    self._process_diff(
                        microservice, value, summary, current_path, cluster
                    )
                else:
                    summary["resource_differences"][microservice].append(
                        {
                            "path": current_path,
                            "reference_value": self._get_value_by_path(
                                cluster, current_path.split("//")[:]
                            ),
                            "analyzed": value,
                        }
                    )

    def _get_value_by_path(self, data: Dict[str, Any], path: List[str]) -> Any:
        """Retrieve a value from a nested dictionary using a list of keys as the path."""
        current = data
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current.get(key, None)
            elif isinstance(current, list):
                current = current[int(key)]
        self.logger.debug(f"Retrieved value by path {path}: {current}")
        return current

    def _get_manifest_value(self, cluster: Dict[str, Any], path: List[str],  diff_keys: List[str | int]) -> Any:
        """Retrieve the list of elements deleted on the original manifest using the keys provided by the diff_keys parameter
        If the keys are indexes we return the list of manifest's values. If the keys are strings we compose a list of dicts with the shape {key: manifest_value} and return it
        """
        if isinstance(diff_keys[0], str):
            diffs = [{key: self._get_value_by_path(cluster, path)[key] } for key in diff_keys]
        else:
            diffs =  [self._get_value_by_path(cluster, path)[key] for key in diff_keys]
    
        self.logger.debug(f"path {path}, diff_keys: {diffs}")
        return diffs

    def _analyze_path_severity(self, path: str, issue_type: str = "missing") -> Severity:
        """Analyze a path and return nuanced severity based on component and issue type."""
        
        # Extract the component from the path
        component = self._extract_component_from_path(path)
        
        # Use enhanced severity analysis
        return analyze_component_severity(component, issue_type, path)

    def evaluate_issue_severity(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Determine the severity with enhanced nuanced analysis."""
        if not analysis:
            return {"low": [{"severity": "LOW", "description": "No differences found between manifests."}]}
       
        # Check for missing resources with nuanced analysis
        if analysis.get("resources_missing"):
            for microservice, resources in analysis["resources_missing"].items():
                if isinstance(resources, dict) and resources.get("path") == microservice:
                    self.logger.critical(f"Entire microservice missing: {microservice}")
                    resources.setdefault("severity", Severity("CRITICAL", f"Missing entire microservice {microservice}."))
                    continue
                
                if isinstance(resources, list):
                    for resource in resources:
                        path = resource.get("path", "")
                        component = self._extract_component_from_path(path)
                        # Determine if this is a missing component or missing attribute
                        issue_type, sub_issue_type = get_issue_type(path, resource.get("value", ""))
                        severity_level = analyze_component_severity(component, issue_type, sub_issue_type)
                        resource.setdefault("severity", severity_level)
    
        # Check for extra resources with nuanced analysis
        if analysis.get("resources_extra"):
            for microservice, resources in analysis["resources_extra"].items():
                for resource in resources:
                    path = resource.get("path", "")
                    component = self._extract_component_from_path(path)

                    issue_type = "extra"
                    severity_level = analyze_component_severity(component, issue_type)
                    resource.setdefault("severity", severity_level)

        # Check for value differences with nuanced analysis
        if analysis.get("resource_differences"):
            for microservice, differences in analysis["resource_differences"].items():
                for diff in differences:
                    path = diff.get("path", "")
                    component = self._extract_component_from_path(path)
                    issue_type = "value_difference"
                    severity_level = analyze_component_severity(component, issue_type)

                    # Slightly reduce severity for value differences vs missing
                    if severity_level.level == "CRITICAL":
                        adjusted_severity = Severity("HIGH", f"Value difference in {path} for {microservice}")
                    else:
                        adjusted_severity = severity_level
                    
                    diff.setdefault("severity", adjusted_severity)
    
        return self._serialize_severity_objects(analysis)

    def _serialize_severity_objects(self, obj) -> Any:
        """Recursively convert all Severity objects to dictionaries for JSON serialization."""
        if isinstance(obj, Severity):
            return obj.to_dict()
        elif isinstance(obj, dict):
            return {key: self._serialize_severity_objects(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_severity_objects(item) for item in obj]
        else:
            return obj



    def _extract_component_from_path(self, path: str) -> str:
        """Extract the main component name from a path."""
        if not path:
            return "unknown"
        
        path_parts = path.split("//")
        
        # Common component mappings
        component_map = {
            "env": "env",
            "ports": "ports", 
            "port": "ports",
            "image": "image",
            "volume": "volumeMounts",
            "command": "commandArgs",
            "args": "commandArgs",
            "workingdir": "workingDir",
            "probe": "readinessProbe",
            "liveness": "livenessProbe",
            "readiness": "readinessProbe",
            "resource": "resources",
            "security": "securityContext",
            "selector": "selector",
            "annotation": "annotations",
            "replica": "replicas",
            "serviceaccount": "serviceAccount",
            "matchlabels": "selector",
            "spec": "template",
            "labels": "metadata",
            "metadata": "metadata",
            "containers": "containers",

        }
        
        if len(path_parts) == 1:
            return "microservice"

        # Look for known components in the path
        for part in reversed(path_parts):
            part_lower = part.lower()
            for key, value in component_map.items():
                if key in part_lower:
                    return value
                if str.isdigit(part_lower):
                    continue
            
        return "configuration"
    
    def save_analysis(self, analysis: Dict[str, Any], file_path: str) -> None:
        """Save the analysis to a file."""
        with open(file_path, 'w') as file:
            json.dump(analysis, file, indent=2)
            self.logger.info(f"Analysis saved to {file_path}")
