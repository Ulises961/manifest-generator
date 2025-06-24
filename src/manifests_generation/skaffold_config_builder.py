import logging
import os
from typing import Any, Optional, List, Dict

class SkaffoldConfigBuilder:
    def __init__(self, manual_manifests_path: str, k8s_manifests_path: str):
        self.logger = logging.getLogger(__name__)
        self.manual_manifests_path = manual_manifests_path
        self.k8s_manifests_path = k8s_manifests_path
        
    def build_template(self, microservices: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a Skaffold configuration file."""

        # First, generate the kustomization file to include all manifests

        # Create the Skaffold config with kustomize support
        skaffold_config: Dict[str, Any] = {
            "apiVersion": "skaffold/v3",
            "kind": "Config",
            "metadata": {"name": "app"},
            "build": {"platforms": ["linux/amd64"], "artifacts": []},
            # Use kustomize for manifests
            "manifests": {"kustomize": {"paths": [self.manual_manifests_path]}},
            "deploy": {"kubectl": {}},
        }

        # Add artifacts for each service
        for service in microservices:
            service_name = service.get("name", "").lower()
            context_path = f"{service['metadata']['dockerfile']}"

            artifact = {"image": service_name, "context": context_path}

            skaffold_config["build"]["artifacts"].append(artifact)

        return skaffold_config

    def build_kustomization_template(self, output_dir: Optional[str] = None):
        """Generate a kustomization.yaml file for the manifests in the output directory."""
        output_dir = output_dir or self.k8s_manifests_path

        self.logger.info(f"Generating kustomization file in {output_dir}")

        # Find all YAML files in the deployments and services subdirectories
        resources = set()  # Use a set instead of a list to prevent duplicates
        k8s_folder = os.getenv("K8S_MANIFESTS_PATH", "k8s")

        # Add deployments
        deployments_dir = os.path.join(output_dir, "deployments")
        deployments_dir_rel = f"{k8s_folder}/deployments"
        if os.path.exists(deployments_dir):
            for file in os.listdir(deployments_dir):
                if file.endswith(".yaml"):
                    resources.add(f"{deployments_dir_rel}/{file}")

        # Add services
        services_dir = os.path.join(output_dir, "services")
        services_dir_rel = f"{k8s_folder}/services"
        if os.path.exists(services_dir):
            for file in os.listdir(services_dir):
                if file.endswith(".yaml"):
                    resources.add(f"{services_dir_rel}/{file}")

        # Add config maps
        config_map_dir_rel = k8s_folder
        if os.path.exists(os.path.join(output_dir, "config_map.yaml")):
            resources.add(f"{config_map_dir_rel}/config_map.yaml")

        # Add secrets
        secrets_dir_rel = k8s_folder
        if os.path.exists(os.path.join(output_dir, "secrets.yaml")):
            resources.add(f"{secrets_dir_rel}/secrets.yaml")

        # Add any stateful sets
        statefulsets_dir = os.path.join(output_dir, "stateful_sets")
        statefulsets_dir_rel = f"{k8s_folder}/stateful_sets"
        if os.path.exists(statefulsets_dir):
            for file in os.listdir(statefulsets_dir):
                if file.endswith(".yaml"):
                    resources.add(f"{statefulsets_dir_rel}/{file}")

        # Add PVCs
        pvcs_dir = os.path.join(output_dir, "pvcs")
        pvcs_dir_rel = f"{k8s_folder}/pvcs"
        if os.path.exists(pvcs_dir):
            for file in os.listdir(pvcs_dir):
                if file.endswith(".yaml"):
                    resources.add(f"{pvcs_dir_rel}/{file}")

        # Add root level files
        for file in os.listdir(output_dir):
            if (
                file.endswith(".yaml")
                and os.path.isfile(os.path.join(output_dir, file))
                and file != "kustomization.yaml"
            ):
                resources.add(f"{k8s_folder}/{file}")

        # Create the kustomization.yaml content
        kustomization = {
            "apiVersion": "kustomize.config.k8s.io/v1beta1",
            "kind": "Kustomization",
            "metadata": {"name": "manifests"},
            "resources": sorted(list(resources)),  # Convert set back to sorted list
            "labels": [{"pairs": {"app.kubernetes.io/managed-by": "kustomize"}}],
        }

        return kustomization