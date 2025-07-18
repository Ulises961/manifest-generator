import logging
import os
from typing import Any, Dict, Tuple

import yaml

from embeddings.embeddings_engine import EmbeddingsEngine


class ManifestsValidator:
    def __init__(self, embeddings_engine: EmbeddingsEngine):
        self.logger = logging.getLogger(__name__)
        self.embeddings_engine = embeddings_engine
    def validate(self, llm_manifests_path: str, heuristics_manifests_path: str):
        # Implement validation logic here
        heuristics_cluster = self._generate_cluster(heuristics_manifests_path)
        llm_cluster = self._generate_cluster(llm_manifests_path)
        self._validate_microservices(llm_cluster, heuristics_cluster)

    def _generate_cluster(self, manifests_path: str) -> Any:
        """Generate a cluster object from the manifests."""
        if not os.path.exists(manifests_path):
            raise FileNotFoundError(f"Manifests path does not exist: {manifests_path}")
        if not os.path.isdir(manifests_path):
            raise NotADirectoryError(f"Manifests path is not a directory: {manifests_path}")
        
        cluster = {}
        supporting_resources = {}
        
        # First pass: collect all resources
        for root, dir, files in os.walk(manifests_path):
            for file in files:
                if file.endswith('.yaml') or file.endswith('.yml'):
                    with open(os.path.join(root, file), 'r') as f:
                        try:
                            documents = yaml.safe_load_all(f)  # This handles multiple documents
                            for resource in documents:
                                if resource and isinstance(resource, dict):
                                    resource_type = resource.get('kind', '').lower()
                                    resource_name = resource.get('metadata', {}).get('name', 'unknown')
                                    
                                    # Get microservice name from labels or resource name
                                    microservice_name = self._get_microservice_name(resource)
                                    
                                    if resource_type in ['deployment', 'statefulset', 'pod', 'job', 'daemonset', 'service', 'ingress', 'persistentvolumeclaim', 'persistentvolume', 'serviceaccount']:
                                        cluster.setdefault(microservice_name, {})
                                        
                                        # Store resource by type
                                        cluster[microservice_name][resource_type] = resource
                                        
                                    elif resource_type in ['configmap', 'secret']:
                                        # Supporting resources - store separately for merging
                                        supporting_resources[resource_name] = resource
                        except yaml.YAMLError as e:
                            raise ValueError(f"Error parsing YAML file {file}: {e}")
        
        # Second pass: merge supporting resources into primary resources
        for microservice_name, resources in cluster.items():
            for resource_name, resource in resources.items():
                self._merge_supporting_resources(resource, supporting_resources)
        
        return cluster

    def _merge_supporting_resources(self, resource: Dict[str, Any], supporting_resources: Dict[str, Any]):
        """Merge supporting resources into the primary resource."""
        resource_type = resource.get('kind', '').lower()
        
        if resource_type in ['deployment', 'statefulset', 'daemonset']:
            # Merge into pod template
            pod_spec = resource.get('spec', {}).get('template', {}).get('spec', {})
            self._merge_pod_supporting_resources(pod_spec, supporting_resources)
        elif resource_type in ['pod', 'job']:
            # Merge directly into pod spec
            pod_spec = resource.get('spec', {})
            self._merge_pod_supporting_resources(pod_spec, supporting_resources)

    def _merge_pod_supporting_resources(self, pod_spec: Dict[str, Any], supporting_resources: Dict[str, Any]):
        """Merge supporting resources into pod spec."""
        containers = pod_spec.get('containers', [])
        
        for container in containers:
            # Merge ConfigMaps and Secrets into env vars
            self._merge_env_vars(container, supporting_resources)


    def _merge_env_vars(self, container: Dict[str, Any], supporting_resources: Dict[str, Any]):
        """Merge ConfigMap and Secret references into actual env vars."""
        if 'env' not in container:
            container['env'] = []
        
        # Handle envFrom (ConfigMap/Secret references)
        env_from = container.get('envFrom', [])
        for env_source in env_from:
            if 'configMapRef' in env_source:
                cm_name = env_source['configMapRef']['name']
                if cm_name in supporting_resources:
                    cm_data = supporting_resources[cm_name].get('data', {})
                    for key, value in cm_data.items():
                        container['env'].append({'name': key, 'value': value})
            
            elif 'secretRef' in env_source:
                secret_name = env_source['secretRef']['name']
                if secret_name in supporting_resources:
                    secret_data = supporting_resources[secret_name].get('data', {})
                    for key, value in secret_data.items():
                        container['env'].append({'name': key, 'value': value})
        
        # Handle individual env var references
        for env_var in container.get('env', []):
            if 'valueFrom' in env_var:
                value_from = env_var['valueFrom']
                if 'configMapKeyRef' in value_from:
                    cm_name = value_from['configMapKeyRef']['name']
                    key = value_from['configMapKeyRef']['key']
                    if cm_name in supporting_resources:
                        cm_data = supporting_resources[cm_name].get('data', {})
                        env_var['value'] = cm_data.get(key, '')
                        del env_var['valueFrom']
                
                elif 'secretKeyRef' in value_from:
                    secret_name = value_from['secretKeyRef']['name']
                    key = value_from['secretKeyRef']['key']
                    if secret_name in supporting_resources:
                        secret_data = supporting_resources[secret_name].get('data', {})
                        env_var['value'] = secret_data.get(key, '')
                        del env_var['valueFrom']
        
        # Remove envFrom since we've merged everything
        if 'envFrom' in container:
            del container['envFrom']

    def _validate_microservices(self, llm_cluster: Dict[str, Dict], heuristics_cluster: Dict[str, Dict]):
        """Validate microservices by comparing LLM-generated manifests with heuristics."""
        
        # First we check that all microservices in the heuristics cluster are present in the LLM cluster
        missing_microservices = set(heuristics_cluster.keys()) - set(llm_cluster.keys())

        summary = {"missing_resources": [], "differences": {}, "similarities": {}}
        missing_specs = []
        analized_microservices = {}
        possible_similar_microservices = {}

        # Now we compare each microservice's resources
        for name, heuristics_resource in heuristics_cluster.items():
            llm_resource: Dict[str, Any] = llm_cluster.get(name, {})
            if llm_resource == {}:
                # Explore possible similar microservice names among the not found ones
                for llm_name in missing_microservices:
                    if self.embeddings_engine.compare_words(name, llm_name) > 0.8:
                        self.logger.warning(f"Possible similar microservice found: {llm_name}")
                        possible_similar_microservices.setdefault(name, []).append(llm_resource)
                        is_similar = self._validate_resources(heuristics_resource, llm_resource, summary, f"{name}")
                        summary.update({"is_similar": is_similar})
                        analized_microservices[name]["summary"] = summary

                    else:
                        missing_microservices.add(llm_name)
                        self.logger.warning(f"Microservice {name} not found in LLM manifests.")
                        summary["missing_resources"].append((name, heuristics_resource))
            else:
                is_similar = self._validate_resources(heuristics_resource, llm_resource, summary, f"{name}")
                summary.update({"is_similar": is_similar})
                analized_microservices[name]["summary"] = summary

        print("All microservices validated successfully.")

    def _validate_resources(self, heuristics_resource: Dict[str, Any], llm_resource: Dict[str, Any],  summary: Dict[str, Any], analyzed_resource_path: str) -> bool:
        """Validate resources by comparing heuristics and LLM-generated manifests."""
        is_similar = True
        for key, heuristics_spec in heuristics_resource.items():
            llm_spec = llm_resource.get(key, None)
            if not llm_spec:
                summary["missing_resources"].append({key: heuristics_spec}) #type: ignore
                is_similar = False
            else:
                if isinstance(heuristics_spec, dict) and isinstance(llm_spec, dict):
                    # Recursively validate nested specs
                    is_similar &= self._validate_resources(heuristics_spec, llm_spec, summary, f"{analyzed_resource_path}.{key}")
                if isinstance(heuristics_spec, list) and isinstance(llm_spec, list):
                    for item in heuristics_spec:
                        if item not in llm_spec:
                            summary["missing_resources"].append({f"{analyzed_resource_path}.{key}": item})
                            is_similar = False
                        else:
                            is_similar &= self._validate_resources(item, llm_spec[llm_spec.index(item)], summary, analyzed_resource_path + f".{key}")
                # Either string or int comparison
                elif heuristics_spec != llm_spec:
                    self.logger.warning(f"Spec mismatch for {key}: {heuristics_spec} != {llm_spec}")
                    summary["differences"].update({f"{analyzed_resource_path}.{key}": heuristics_spec})
                    is_similar = False
        # If we reach here, the resource is valid
        return is_similar
    
    def _get_microservice_name(self, resource: Dict[str, Any]) -> str:
        """Extract the microservice name from the resource."""
        # Try to get the microservice name from labels or metadata
        name = resource.get('metadata', {}).get('name', 'unknown')
        labels = resource.get('metadata', {}).get('labels', {})
        name = labels.get('app', labels.get('name', name))
        if not name:
            name = labels.get('microservice', 'unknown')
        return name