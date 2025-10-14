import logging
import os
from typing import Any, Optional, List, Dict

class SkaffoldConfigBuilder:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def build_template(self, microservices: List[Dict[str, Any]], manifests_path: str) -> Dict[str, Any]:
        """Generate a Skaffold configuration file."""

        # First, generate the kustomization file to include all manifests

        # Create the Skaffold config with kustomize support
        skaffold_config: Dict[str, Any] = {
            "apiVersion": "skaffold/v3",
            "kind": "Config",
            "metadata": {"name": "app"},
            "build": {"platforms": ["linux/amd64"], "artifacts": [], "local": {"useDockerCLI": True, "useBuildkit": True}},
            # Use kustomize for manifests
            "manifests": {"kustomize": {"paths": [manifests_path]}},
            "deploy": {"kubectl": {}},
        }

        # Add artifacts for each service
        for service in microservices:
            service_name = service.get("name", "").lower()
            if service_name == "app" or "metadata" not in service or "dockerfile_path" not in service["metadata"] or not service["metadata"]["dockerfile_path"]:
                continue
            context_path = f"{service['metadata']['dockerfile_path']}"

            artifact = {"image": service_name, "context": context_path}

            skaffold_config["build"]["artifacts"].append(artifact)

        return skaffold_config

    def build_kustomization_template(self, output_dir: str):
        """Generate a kustomization.yaml file for the manifests in the output directory."""

        self.logger.info(f"Generating kustomization file in {output_dir}")

        # Find all YAML files in the deployments and services subdirectories
        resources = set()  # Use a set instead of a list to prevent duplicates
        k8s_folder = os.getenv("K8S_MANIFESTS_PATH", "k8s")

        # Add deployments
        deployments_dir_rel = f"{k8s_folder}/deployment"
        deployments_dir = os.path.join(output_dir, deployments_dir_rel)

        if os.path.exists(deployments_dir):
            # Iterate through all files in the deployments directory
            for file in os.listdir(deployments_dir):
                if file.endswith(".yaml"):
                    # We save the relative path to the file
                    resources.add(f"{deployments_dir_rel}/{file}")

        # Add services
        services_dir_rel = f"{k8s_folder}/service"
        services_dir = os.path.join(output_dir, services_dir_rel)
        if os.path.exists(services_dir):
            for file in os.listdir(services_dir):
                if file.endswith(".yaml"):
                    resources.add(f"{services_dir_rel}/{file}")

        # Add config maps
        configmaps_dir_rel = f"{k8s_folder}/config_map"
        configmaps_dir = os.path.join(output_dir, configmaps_dir_rel)
        if os.path.exists(configmaps_dir):
            for file in os.listdir(configmaps_dir):
                if file.endswith(".yaml"):
                    resources.add(f"{configmaps_dir_rel}/{file}")
        
        # Add secrets
        secrets_dir_rel = f"{k8s_folder}/secret"
        secrets_dir = os.path.join(output_dir, secrets_dir_rel)
        if os.path.exists(secrets_dir):
            for file in os.listdir(secrets_dir):
                if file.endswith(".yaml"):
                    resources.add(f"{secrets_dir_rel}/{file}")

        # Add any stateful sets
        statefulsets_dir_rel = f"{k8s_folder}/stateful_set"
        statefulsets_dir = os.path.join(output_dir, statefulsets_dir_rel)
        if os.path.exists(statefulsets_dir):
            for file in os.listdir(statefulsets_dir):
                if file.endswith(".yaml"):
                    resources.add(f"{statefulsets_dir_rel}/{file}")

        # Add PVCs
        pvcs_dir_rel = f"{k8s_folder}/persistent_volume_claim"
        pvcs_dir = os.path.join(output_dir, pvcs_dir_rel)
        if os.path.exists(pvcs_dir):
            for file in os.listdir(pvcs_dir):
                if file.endswith(".yaml"):
                    resources.add(f"{pvcs_dir_rel}/{file}")

        # Add service accounts
        service_accounts_dir_rel = f"{k8s_folder}/service_account"
        service_accounts_dir = os.path.join(output_dir, service_accounts_dir_rel)
        if os.path.exists(service_accounts_dir):
            self.logger.info(f"Adding service accounts from {service_accounts_dir}")
            for file in os.listdir(service_accounts_dir):
                if file.endswith(".yaml"):
                    resources.add(f"{service_accounts_dir_rel}/{file}")

        # Add any file in the k8s folder that is not a directory
        parent_dir = os.path.join(output_dir, k8s_folder)
        os.makedirs(parent_dir, exist_ok=True)
        for file in os.listdir(parent_dir):
            if file.endswith(".yaml") and not os.path.isdir(os.path.join(parent_dir, file)):
                # We save the relative path to the file
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