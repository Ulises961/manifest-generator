import logging
import os
import sys
from typing import Any, Dict, Optional, List

import jsondiff
from jsondiff import symbols
import yaml

from embeddings.embeddings_engine import EmbeddingsEngine


class ManifestsValidator:
    def __init__(self, embeddings_engine: EmbeddingsEngine):
        self.logger = logging.getLogger(__name__)
        self.embeddings_engine = embeddings_engine

    def validate(
        self, llm_manifests_path: str, heuristics_manifests_path: str
    ) -> Dict[str, Any]:
        # Implement validation logic here
        heuristics_cluster = self._generate_cluster(heuristics_manifests_path)
        llm_cluster = self._generate_cluster(llm_manifests_path)
        return self._validate_microservices(llm_cluster, heuristics_cluster)

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

    def _validate_microservices(
        self, llm_cluster: Dict[str, Dict], heuristics_cluster: Dict[str, Dict]
    ) -> Dict[str, Any]:
        """Validate microservices by comparing LLM-generated manifests with heuristics."""
        diff = jsondiff.diff(llm_cluster, heuristics_cluster, syntax="explicit")
        summary = {
            "resources_analyzed": [],
            "resources_extra": {},  # LLM has but Heuristics doesn't
            "resources_missing": {},  # Heuristics has but LLM doesn't
            "resource_differences": {},  # Value differences
        }
        # Process each microservice in the diff
        for verb, action in diff.items():
            if verb is symbols.update or verb is symbols.insert:
                if isinstance(action, dict):
                    for microservice, intervention in action.items():
                        summary["resources_analyzed"].append(microservice)
                        summary["resources_extra"][microservice] = []
                        summary["resources_missing"][microservice] = []
                        summary["resource_differences"][microservice] = []

                        self._process_diff(
                            microservice,
                            intervention,
                            summary,
                            f"{microservice}",
                            llm_cluster,
                        )
            elif verb is symbols.delete:

                if isinstance(action, list):
                    for microservice in action:
                        summary["resources_analyzed"].append(microservice)
                        summary["resources_missing"][microservice] = {
                            "path": microservice,
                            "value": llm_cluster[microservice],
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
                # LLM has extra fields that Heuristics doesn't have
                summary["resources_extra"][microservice].append(
                    {"path": path, "value": value}  # Use parent path, not current_path
                )
            elif key is symbols.delete:
                # LLM is missing fields that Heuristics has
                content = self._get_value(cluster, path.split("//")[:], value)
                summary["resources_missing"][microservice].append(
                    {"path": path, "value": content}  # Use parent path, not current_path
                )
            elif key is symbols.update:
                # Both have the field but with different values/structure
                if isinstance(value, dict):
                    self._process_diff(microservice, value, summary, path, cluster)

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
                            "heuristics_value": self._get_value_by_path(
                                cluster, current_path.split("//")[:]
                            ),
                            "llm_value": value,
                        }
                    )

    def _get_value_by_path(self, data: Dict[str, Any], path: List[str],) -> Any:
        """Retrieve a value from a nested dictionary using a list of keys as the path."""
        current = data
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            elif isinstance(current, list):
                current = current[int(key)]
        return current

    def _get_value(self, data: Dict[str, Any], path: List[str],  diff_keys: list) -> Any:
        if isinstance(diff_keys[0], str):
            return [{key: self._get_value_by_path(data, path)[key] } for key in diff_keys]
        return  [self._get_value_by_path(data, path)[key] for key in diff_keys]