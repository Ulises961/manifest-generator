from email import header
import json
import logging
import os
import re
from typing import Any, Dict, List

import jsondiff
from jsondiff import symbols
import yaml

from utils.file_utils import save_csv, save_json
import Levenshtein
from validation.severity import analyze_component_severity, get_issue_type


class ManifestsValidator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def levenshtein_manifests_distance(
        self,
        analyzed_cluster_path: str,
        reference_cluster_path: str,
    ):
        analyzed_cluster = self._generate_cluster_for_levenshtein(analyzed_cluster_path)
        reference_cluster = self._generate_cluster_for_levenshtein(
            reference_cluster_path
        )
        total_lines_reference = self.count_cluster_lines(reference_cluster)


        diff = self._structure_diff(analyzed_cluster, reference_cluster)
        levenshtein_similarity = self.manifest_similarity(json.dumps(analyzed_cluster, sort_keys=True), json.dumps(reference_cluster, sort_keys=True))
        
        report_path = os.path.join(reference_cluster_path, "..", "results") 
        os.makedirs(report_path, exist_ok=True)

        result = self.analyze_diff_for_levenshtein(diff, verbose=False)

        if os.getenv("USE_REFERENCE_MANIFESTS", "false").lower() == "true":
            analyzed_repo_path = os.path.join(analyzed_cluster_path, "..","results")
            os.makedirs(analyzed_repo_path, exist_ok=True)
        
            severity_report_path = os.path.join(analyzed_repo_path, "diff_report_with_reference.csv")
            self.generate_severity_report(result, severity_report_path)
            
        else:
            self.export_diff_report(result, levenshtein_similarity, total_lines_reference, os.path.join(report_path, "diff_report.json"))


    def count_value_lines(self, value, is_removed=False, details=None, path_prefix=""):
        """
        Recursively count lines in a value, handling different data types.
        Records detailed information about what's being counted for explainability.
        """
        count = 0
        
        if isinstance(value, dict):
            for k, v in value.items():
                if isinstance(v, dict) or isinstance(v, list):
                    count += 1  # Count the key as a line
                    if details is not None:
                        details['dict_keys'] += 1
                        details['items'].append({
                            'type': 'dict_key',
                            'path': f"{path_prefix}.{k}" if path_prefix else str(k),
                            'key': str(k),
                            'lines': 1
                        })
                count += self.count_value_lines(v, is_removed, details, 
                                            f"{path_prefix}.{k}" if path_prefix else str(k))
        elif isinstance(value, list):
            if details is not None:
                details['list_items'] += len(value)
            for idx, item in enumerate(value):
                count += self.count_value_lines(item, is_removed, details, 
                                            f"{path_prefix}[{idx}]")
        elif isinstance(value, str):
            # Count multi-line strings as multiple lines
            lines = value.split('\n')
            count += len(lines)
            if details is not None:
                details['string_lines'] += len(lines)
                if len(lines) > 1:
                    details['multiline_strings'] += 1
                details['items'].append({
                    'type': 'string',
                    'path': path_prefix,
                    'value': value,
                    'lines': len(lines),
                    'is_multiline': len(lines) > 1
                })
        elif value is not None:
            # Count any other non-null value as one line
            count += 1
            if details is not None:
                details['primitive_values'] += 1
                details['items'].append({
                    'type': type(value).__name__,
                    'path': path_prefix,
                    'value': value,
                    'lines': 1
                })
            
        return count

    def count_diff_lines(self, diff_result, verbose=True):
        """
        Count the number of actual lines that represent changes in the diff.
        Returns a tuple: (added_lines, removed_lines, modified_lines, report)
        """
        added_lines = 0
        removed_lines = 0
        modified_lines = 0
        
        # Detailed reporting structure
        report = {
            'additions': {'total': 0, 'by_resource': {}, 'details': []},
            'removals': {'total': 0, 'by_resource': {}, 'details': []},
            'modifications': {'total': 0, 'by_resource': {}, 'details': []}
        }
        
        # Count resources_extra (added lines)
        self.logger.debug("="*80)
        self.logger.debug("ANALYZING ADDITIONS (resources_extra)")
        self.logger.debug("="*80)

        for resource_type, resources in diff_result.get('resources_extra', {}).items():
            resource_added = 0
            if isinstance(resources, list):
                for resource in resources:
                    if isinstance(resource, dict) and 'value' in resource:
                        details = {
                            'dict_keys': 0, 'list_items': 0, 
                            'string_lines': 0, 'multiline_strings': 0, 
                            'primitive_values': 0, 'items': []
                        }
                        lines = self.count_value_lines(resource['value'], details=details, 
                                                    path_prefix=f"{resource_type}")
                        added_lines += lines
                        resource_added += lines
                        
                        # Extract component and analyze severity
                        path = resource.get('path', 'N/A')
                        component = self._extract_component_from_path(path)
                        issue_type = "extra"  # This is an addition
                        
                        severity = analyze_component_severity(
                            component=component,
                            issue_type=issue_type,
                            attribute=None,
                            reference_value= None,
                            analyzed_value= resource["value"]
                        )
                        
                        report['additions']['details'].append({
                            'resource': resource_type,
                            'path': path,
                            'lines': lines,
                            'breakdown': {k: v for k, v in details.items() if k != 'items'},
                            'items': details['items'],
                            'severity': severity.to_dict()
                        })
                        
        
                        self.logger.debug(f"[{resource_type}] ADDITION")
                        self.logger.debug(f"Path: {resource.get('path', 'N/A')}")
                        self.logger.debug(f"Total lines added: {lines}")
                        if details['items']:
                            self.logger.debug(f"Items:")
                            for item in details['items']:
                                if item['type'] == 'string':
                                    self.logger.debug(f"• {item['path']}: \"{item['value']}\" ({item['lines']} lines)")
                                else:
                                    self.logger.debug(f"• {item['path']}: {item.get('value', item.get('key', 'N/A'))} ({item['lines']} lines)")
            
            if resource_added > 0:
                report['additions']['by_resource'][resource_type] = resource_added
        
        # Count resources_missing (removed lines)
        self.logger.debug("="*80)
        self.logger.debug("ANALYZING REMOVALS (resources_missing)")
        self.logger.debug("="*80)

        for resource_type, resources_data in diff_result.get('resources_missing', {}).items():
            resource_removed = 0
            
            # Handle the special case where the entire resource is missing (like redis-cart)
            if isinstance(resources_data, dict) and 'value' in resources_data:
                details = {
                    'dict_keys': 0, 'list_items': 0, 
                    'string_lines': 0, 'multiline_strings': 0, 
                    'primitive_values': 0, 'items': []
                }
                lines = self.count_value_lines(resources_data['value'], is_removed=True, 
                                            details=details, path_prefix=f"{resource_type}")
                removed_lines += lines
                resource_removed += lines
                
                # Extract component and analyze severity
                path = resources_data.get('path', 'N/A')
                component = self._extract_component_from_path(path)
                issue_type, attribute = get_issue_type(path, resources_data.get('value'))
                
                severity = analyze_component_severity(
                    component=component,
                    issue_type=issue_type,
                    attribute=attribute,
                    reference_value=resources_data.get('value'),
                    analyzed_value=None
                )
                
                report['removals']['details'].append({
                    'resource': resource_type,
                    'path': path,
                    'lines': lines,
                    'type': 'complete_resource',
                    'breakdown': {k: v for k, v in details.items() if k != 'items'},
                    'items': details['items'],
                    'severity': severity.to_dict()
                })
                

                self.logger.debug(f"[{resource_type}] COMPLETE RESOURCE REMOVED")
                self.logger.debug(f"  Path: {resources_data.get('path', 'N/A')}")
                self.logger.debug(f"  Total lines removed: {lines}")

                if details['items']:
                    self.logger.debug(f"Items:")
                    for item in details['items']:
                        if item['type'] == 'string':
                            self.logger.debug(f"• {item['path']}: \"{item['value']}\" ({item['lines']} lines)")
                        else:
                            self.logger.debug(f"• {item['path']}: {item.get('value', item.get('key', 'N/A'))} ({item['lines']} lines)")
                    
            elif isinstance(resources_data, list):
                # This is a list of missing items
                for resource in resources_data:
                    if isinstance(resource, dict) and 'value' in resource:
                        # The 'value' here is typically a dict with an index: actual_value structure
                        for idx, actual_value in resource['value'].items():
                            details = {
                                'dict_keys': 0, 'list_items': 0, 
                                'string_lines': 0, 'multiline_strings': 0, 
                                'primitive_values': 0, 'items': []
                            }
                            lines = self.count_value_lines(actual_value, is_removed=True, 
                                                        details=details, 
                                                        path_prefix=f"{resource_type}[{idx}]")
                            removed_lines += lines
                            resource_removed += lines
                            
                            # Extract component and analyze severity
                            path = resource.get('path', 'N/A')
                            component = self._extract_component_from_path(path)
                            issue_type, attribute = get_issue_type(path, actual_value)
                            
                            severity = analyze_component_severity(
                                component=component,
                                issue_type=issue_type,
                                attribute=attribute,
                                reference_value=actual_value,
                                analyzed_value= None
                            )
                            
                            report['removals']['details'].append({
                                'resource': resource_type,
                                'path': path,
                                'index': idx,
                                'lines': lines,
                                'type': 'indexed_item',
                                'breakdown': {k: v for k, v in details.items() if k != 'items'},
                                'items': details['items'],
                                'severity': severity.to_dict()
                            })
                            
            
                            self.logger.debug(f"[{resource_type}] INDEXED ITEM REMOVED")
                            self.logger.debug(f"  Path: {resource.get('path', 'N/A')}")
                            self.logger.debug(f"  Index: {idx}")
                            self.logger.debug(f"  Total lines removed: {lines}")

                            if details['items']:
                                self.logger.debug(f"Items:")
                                for item in details['items']:
                                    if item['type'] == 'string':
                                        self.logger.debug(f"• {item['path']}: \"{item['value']}\" ({item['lines']} lines)")
                                    else:
                                        self.logger.debug(f"• {item['path']}: {item.get('value', item.get('key', 'N/A'))} ({item['lines']} lines)")
        
            if resource_removed > 0:
                report['removals']['by_resource'][resource_type] = resource_removed
        
        # Count resource_differences (modified lines)
        self.logger.debug("="*80)
        self.logger.debug("ANALYZING MODIFICATIONS (resource_differences)")
        self.logger.debug("="*80)
        
        for resource_type, differences in diff_result.get('resource_differences', {}).items():
            resource_modified = 0
            if isinstance(differences, list):
                for diff in differences:
                    if isinstance(diff, dict) and 'value' in diff:
                        details = {
                            'dict_keys': 0, 'list_items': 0, 
                            'string_lines': 0, 'multiline_strings': 0, 
                            'primitive_values': 0, 'items': []
                        }
                        lines = self.count_value_lines(diff['value'], details=details, 
                                                    path_prefix=f"{resource_type}")
                        modified_lines += lines
                        resource_modified += lines
                        
                        # Extract component and analyze severity
                        path = diff.get('path', 'N/A')
                        component = self._extract_component_from_path(path)
                        issue_type = "value_difference"
                        
                        # Get reference value if available
                        reference_value = diff.get('reference_value', None)
                        
                        severity = analyze_component_severity(
                            component=component,
                            issue_type=issue_type,
                            attribute=None,
                            reference_value=reference_value,
                            analyzed_value=diff.get("analyzed_value", None)
                        )
                        
                        report['modifications']['details'].append({
                            'resource': resource_type,
                            'path': path,
                            'lines': lines,
                            'breakdown': {k: v for k, v in details.items() if k != 'items'},
                            'items': details['items'][:5],
                            'severity': severity.to_dict()
                        })
                        
        
                        self.logger.debug(f"[{resource_type}] MODIFICATION")
                        self.logger.debug(f"  Path: {diff.get('path', 'N/A')}")
                        self.logger.debug(f"  Total lines modified: {lines}")                            
                        if details['items']:
                            self.logger.debug(f"Items:")
                            for item in details['items']:
                                if item['type'] == 'string':
                                    self.logger.debug(f"• {item['path']}: \"{item['value']}\" ({item['lines']} lines)")
                                else:
                                    self.logger.debug(f"• {item['path']}: {item.get('value', item.get('key', 'N/A'))} ({item['lines']} lines)")

            if resource_modified > 0:
                report['modifications']['by_resource'][resource_type] = resource_modified
        
        # Update totals
        report['additions']['total'] = added_lines
        report['removals']['total'] = removed_lines
        report['modifications']['total'] = modified_lines
        
        return added_lines, removed_lines, modified_lines, report

    def analyze_diff_for_levenshtein(self, diff_data, verbose=True) -> Dict[str, Any]:
        """
        Comprehensive analysis of the diff for Levenshtein similarity calculation
        """
        # Detailed line counting
        added_lines, removed_lines, modified_lines, report = self.count_diff_lines(diff_data, verbose=verbose)
        
        self.logger.info("="*80)
        self.logger.info(" "*20 + "FINAL SUMMARY")
        self.logger.info("="*80)
        self.logger.info(f"Overall Line Counts:")
        self.logger.info(f"  Added lines:    {added_lines:>8,}")
        self.logger.info(f"  Removed lines:  {removed_lines:>8,}")
        self.logger.info(f"  Modified lines: {modified_lines:>8,}")
        self.logger.info(f"  {'-'*40}")
        self.logger.info(f"  Total changes:  {added_lines + removed_lines + modified_lines:>8,}")
        
        # Show breakdown by resource type
        self.logger.debug(f"{'-'*80}")
        self.logger.debug("Breakdown by Resource Type:")
        self.logger.debug(f"{'-'*80}")
        
        all_resources = set()
        all_resources.update(report['additions']['by_resource'].keys())
        all_resources.update(report['removals']['by_resource'].keys())
        all_resources.update(report['modifications']['by_resource'].keys())
        
        for resource in sorted(all_resources):
            adds = report['additions']['by_resource'].get(resource, 0)
            removes = report['removals']['by_resource'].get(resource, 0)
            mods = report['modifications']['by_resource'].get(resource, 0)
            total = adds + removes + mods
            
            if total > 0:
                self.logger.debug(f"[{resource}]")
                if adds > 0:
                    self.logger.debug(f"  + Added:    {adds:>6,} lines")
                if removes > 0:
                    self.logger.debug(f"  - Removed:  {removes:>6,} lines")
                if mods > 0:
                    self.logger.debug(f"  ~ Modified: {mods:>6,} lines")
                self.logger.debug(f"  = Total:    {total:>6,} lines")
                
        # For Levenshtein distance calculation
        total_operations = added_lines + removed_lines + modified_lines
        
        return {
            'added_lines': added_lines,
            'removed_lines': removed_lines, 
            'modified_lines': modified_lines,
            'total_operations': total_operations,
            'detailed_report': report,
            'resources_affected': len(all_resources)
        }

    def export_diff_report(self, result, levenshtein_similarity,cluster_total_lines, output_file='diff_report.json'):
        """Export the detailed diff report to a JSON file for further analysis"""
        result["levenshtein_similarity"] = levenshtein_similarity
        result["cluster_lines"] = cluster_total_lines
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        self.logger.info(f"Detailed report successfully exported to: {output_file}")

    def _generate_cluster_for_levenshtein(self, manifests_path: str) -> Dict[str, Any]:
        """Generate a cluster object from the manifests."""
        if not os.path.isdir(manifests_path):
            raise NotADirectoryError(
                f"Manifests path is not a directory: {manifests_path}"
            )
        cluster = {}
        for root, dir, files in os.walk(manifests_path):
            for file in files:
                if file.endswith(".yaml") or file.endswith(".yml"):
                    if "skaffold" in file or "kustomization" in file:
                        continue  # Skip skaffold files
                    with open(os.path.join(root, file), "r") as f:
                        try:
                            documents = yaml.safe_load_all(
                                f
                            )  # This handles multiple documents
                            for resource in documents:
                                if resource and isinstance(resource, dict):
                                    resource_type = resource.get("kind", "").lower()
                                
                                    # Get microservice name from labels or resource name
                                    microservice_name = self._get_microservice_name(
                                        resource
                                    )

                                    cluster.setdefault(microservice_name, {})
                                    # Store resource by type
                                    cluster[microservice_name][resource_type] = resource
                        except yaml.YAMLError as e:
                            raise ValueError(f"Error parsing YAML file {file}: {e}")
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
        for _, resources in cluster.items():
            for _, resource in resources.items():
                if "spec" in resource and "template" in resource["spec"]:
                    pod_spec = resource["spec"]["template"].get("spec", {})
                    if "containers" in pod_spec:
                        for container in pod_spec["containers"]:
                            if "env" in container:
                                container["env"].sort(key=lambda x: x.get("name", ""))
                            if "ports" in container:
                                container["ports"].sort(
                                    key=lambda x: x.get("containerPort", 0)
                                )
                            if "volumeMounts" in container:
                                container["volumeMounts"].sort(
                                    key=lambda x: x.get("name", "")
                                )
                elif "env" in resource:
                    resource["env"].sort(key=lambda x: x.get("name", ""))

    def _structure_diff(
        self, analyzed_cluster: Dict[str, Dict], reference_cluster: Dict[str, Dict]
    ) -> Dict[str, Any]:
        """Validate microservices by comparing a target manifests with a reference."""
        diff = jsondiff.diff(reference_cluster, analyzed_cluster, syntax="explicit")
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
                        self.logger.debug(f"Extra resource found: {resource}")
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
                        self.logger.debug(f"Missing resource found: {microservice}")
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
        reference_cluster: Dict[str, Any],
    ):
        """Process diff recursively."""
        for key, value in diff.items():

            if key is symbols.insert:
                # Analyzed cluster has extra fields that reference doesn't have
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        summary["resources_extra"][microservice].append(
                            {
                                "path": f"{path}//{sub_key}",
                                "value": sub_value  # Changed: Remove wrapping in dict
                            }
                        )
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, tuple):
                            # List of index indicating the extra items
                            summary["resources_extra"][microservice].append(
                                {"path": path, "value": item[1]}
                            )
                        else:
                            summary["resources_extra"][microservice].append(
                                {"path": path, "value": item}
                            )
                else:
                    summary["resources_extra"][microservice].append(
                        {"path": path, "value": value}
                    )
            elif key is symbols.delete:
                # Analyzed cluster is missing fields that reference has
                for diff_key in value:
                    content = self._get_manifest_value(
                        reference_cluster, path.split("//")[:], diff_key
                    )

                    summary["resources_missing"][microservice].append(
                        {
                            "path": f"{path}//{diff_key}",
                            "value": content,  # This is already a dict with {key: value}
                        }
                    )

            elif key is symbols.update:
                # Both have the field but with different values/structure
                if isinstance(value, dict):
                    self.logger.debug(f"Analyzing update key {value}")
                    self._process_diff(
                        microservice, value, summary, path, reference_cluster
                    )
                else:
                    self.logger.warning(f"Update non processed {value}")

            else:
                # Regular field name - continue recursion
                current_path = f"{path}//{key}"
                if isinstance(value, dict):
                    self._process_diff(
                        microservice, value, summary, current_path, reference_cluster
                    )
                else:
                    # Store the actual changed value, not just the analyzed value
                    summary["resource_differences"][microservice].append(
                        {
                            "path": current_path,
                            "value": value,  # Changed: Store just the value for counting
                            "reference_value": self._get_value_by_path(
                                reference_cluster, current_path.split("//")[:]
                            ),
                            "analyzed_value": value,
                        }
                    )

    def _get_value_by_path(self, data: Dict[str, Any], path: List[str]) -> Any:
        """Retrieve a value from a nested dictionary using a list of keys as the path."""
        current = data
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current.get(key, None)
            elif isinstance(current, list):
                if key.isdigit() and int(key) < len(current):
                    current = current[int(key)]  # type: ignore
                elif key in current:
                    index = current.index(key)
                    current = current[index]  # type: ignore
        self.logger.debug(f"Retrieved value by path {path}: {current}")
        return current

    def get_key_by_path(self, data: Dict[str, Any], path: List[str]) -> Any:
        """Retrieve a key from a nested dictionary using a list of keys as the path."""
        current = data
        for key in path[:-1]:
            if isinstance(current, dict) and key in current:
                current = current.get(key, None)
            elif isinstance(current, list):
                if key.isdigit() and int(key) < len(current):
                    current = current[int(key)]  # type: ignore
                elif key in current:
                    index = current.index(key)
                    current = current[index]  # type: ignore
        self.logger.debug(f"Retrieved key by path {path}: {current}")
        return (
            list(current.keys())[0] if isinstance(current, dict) and current else None
        )

    def _get_manifest_value(
        self, cluster: Dict[str, Any], path: List[str], diff_key: str | int
    ) -> Any:
        """Retrieve the list of elements deleted on the original manifest using the keys provided by the diff_keys parameter.
        We compose a list of dicts with the shape {key: manifest_value} and return it
        """
        value_at_path = self._get_value_by_path(cluster, path)
        
        # Handle case where value_at_path is a list
        if isinstance(value_at_path, list):
            # If diff_key is an integer or numeric string, use it as an index
            if isinstance(diff_key, int):
                diff = {diff_key: value_at_path[diff_key] if diff_key < len(value_at_path) else None}
            elif isinstance(diff_key, str) and diff_key.isdigit():
                idx = int(diff_key)
                diff = {diff_key: value_at_path[idx] if idx < len(value_at_path) else None}
            else:
                # If diff_key is not numeric, return the whole list item that matches
                diff = {diff_key: value_at_path}
        elif isinstance(value_at_path, dict):
            # Original behavior for dicts
            diff = {diff_key: value_at_path.get(diff_key)}
        else:
            # For other types, just return as-is
            diff = {diff_key: value_at_path}

        self.logger.debug(f"path {path}, diff_key: {diff_key}, diff: {diff}")
        return diff

    def _extract_component_from_path(self, path: str) -> str:
        """Extract the main component name from a path."""
        if not path:
            return "unknown"

        path_parts = path.split("//")

        # Common component mappings
        component_map = [
            "env",
            "ports",
            "image",
            "volume",
            "command",
            "workingDir",
            "readinessProbe",
            "livenessProbe",
            "resources",
            "securityContext",
            "selector",
            "annotations",
            "replicas",
            "serviceAccount",
            "matchLabels",
            "spec",
            "labels",
            "metadata",
            "containers",
            "spec",
            "terminationGracePeriodSeconds",
            "serviceAccountName",
            "restartPolicy",
        ]
        resource_list = [
            "deployment",
            "service",
            "configmap",
            "secret",
            "statefulset",
            "persistentvolumeclaim",
        ]

        if len(path_parts) == 1:
            return "microservice"

        if len(path_parts) == 2 and path_parts[-1].lower() in resource_list:
            return path_parts[-1]

        # Look for known components in the path
        for part in reversed(path_parts):
            for value in component_map:
                if value.lower() == part.lower():
                    return value
                if str.isdigit(part):
                    continue

        return "configuration"

    def manifest_similarity(self, candidate: str, reference: str) -> float:
        """
        Normalized Levenshtein ratio between canonicalized manifests.
        Returns a float in [0, 1] where 1 = identical.
        """

        if not candidate or not reference:
            return 0.0
        return Levenshtein.ratio(candidate, reference)

    def count_cluster_lines(self, cluster: Dict[str, Any]) -> int:
        """
        Count total lines in a cluster produced by _generate_cluster_for_levenshtein.

        Returns a summary dict:
          - total_lines: int
          - microservices_count: int
          - by_microservice: { ms_name: { total_lines, by_resource: {rtype: {...} } } }
        """
        total = 0
        by_microservice: Dict[str, Any] = {}

        for ms_name, resources in (cluster or {}).items():
            ms_total = 0

            if not isinstance(resources, dict):
                # unexpected shape: treat whole object as one resource
                details = {
                    'dict_keys': 0, 'list_items': 0,
                    'string_lines': 0, 'multiline_strings': 0,
                    'primitive_values': 0, 'items': []
                }
                lines = self.count_value_lines(resources, details=details, path_prefix=str(ms_name))
                ms_total += lines
            else:
                for rtype, resource in resources.items():
                    details = {
                        'dict_keys': 0, 'list_items': 0,
                        'string_lines': 0, 'multiline_strings': 0,
                        'primitive_values': 0, 'items': []
                    }
                    lines = self.count_value_lines(resource, details=details, path_prefix=f"{ms_name}//{rtype}")
                    ms_total += lines
            
            total += ms_total

        return total

    def generate_severity_report(self, diff_report: dict, path: str = ""):
        report: dict  = diff_report.get("detailed_report", {})
        header = ["Stage", "Microservice", "Issue Type", "Path", "Reference Value", "Analyzed Value", "Severity Level", "Severity Description", "Reviewed Level", "Comments"]
        
        rows = []
        
        for change_type in ["additions", "removals", "modifications"]:
            for detail in report.get(change_type, {}).get("details", []):
                severity_info = detail.get("severity", {})
                rows.append([
                    change_type[:-1].capitalize(),
                    detail.get("resource", "N/A"),
                    severity_info.get("issue_type", "N/A"),
                    detail.get("path", "N/A"),
                    severity_info.get("reference_value", "N/A"),
                    severity_info.get("analyzed_value", "N/A"),
                    severity_info.get("severity", "N/A"),
                    severity_info.get("description", "N/A"),
                    severity_info.get("reviewed_level", "N/A"),
                    severity_info.get("comments", "N/A"),
                ])

        csv_lines = [header] + rows
        
        save_csv(csv_lines, path)