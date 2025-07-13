import logging
import os
from typing import Any, Dict, List, Optional, Tuple, cast
from manifests_generation.configmap_builder import ConfigMapBuilder
from manifests_generation.deployment_builder import DeploymentBuilder
from overrides.overrider import Overrider
from manifests_generation.pvc_builder import PVCBuilder
from manifests_generation.secret_builder import SecretBuilder
from manifests_generation.service_builder import ServiceBuilder
from manifests_generation.skaffold_config_builder import SkaffoldConfigBuilder
from manifests_generation.statefulset_builder import StatefulSetBuilder
import yaml


class ManifestBuilder:
    """Manifest builder for microservices."""

    def __init__(self, overrider: Overrider) -> None:
        """Initialize the tree builder with the manifest templates."""
        
        self.logger = logging.getLogger(__name__)

        self.target_path = os.getenv("OUTPUT_DIR", "output")
        self.manifests_path = os.path.join(
            self.target_path, os.getenv("MANIFESTS_PATH", "manifests")
        )

        self.manual_manifests_path = os.path.join(
            self.manifests_path, os.getenv("MANUAL_MANIFESTS_PATH", "manual")
        )

        self.k8s_manifests_path = os.path.join(
            self.manual_manifests_path, os.getenv("K8S_MANIFESTS_PATH", "k8s")
        )

        os.makedirs(os.path.dirname(self.k8s_manifests_path), exist_ok=True)

        self.overrider = overrider
        self._configmap_builder = ConfigMapBuilder(self.k8s_manifests_path)
        self._servicebuilder = ServiceBuilder()
        self._deployment_builder = DeploymentBuilder()
        self.statefulset_builder = StatefulSetBuilder()
        self.pvc_builder = PVCBuilder()
        self._secret_builder = SecretBuilder(self.k8s_manifests_path)
        self.skaffold_builder = SkaffoldConfigBuilder()

    def generate_manifests(self, microservice: Dict[str, Any]) -> None:
        """Generate manifests for the microservice and its dependencies."""
        
        microservice.setdefault("manifests", {})

        if microservice.get("workload", None):
            if microservice["workload"] == "StatefulSet":
                saved = self.build_stateful_set_yaml(microservice)

                microservice["manifests"].update({"stateful_set": saved})

            elif microservice["workload"] == "Deployment":
                saved = self.build_deployment_yaml(microservice)

                microservice["manifests"].update({"deployment": saved})
        else:
            saved = self.build_deployment_yaml(microservice)
            microservice["manifests"].update({"deployment": saved})

        if microservice.get("ports", None):
            saved = self.build_service_yaml(microservice)
            microservice["manifests"].update({"service": saved})

        if microservice.get("persistent_volumes", None):
            for pvc in microservice["persistent_volumes"]:
                saved = self.build_pvc_yaml(pvc)
                microservice["manifests"].update({"pvc": saved})

        if microservice.get("secrets", None):
            for secret in microservice["secrets"]:
                saved = self.build_secrets_yaml(secret)
                microservice["manifests"].update({"secret": saved})
                self._save_yaml(saved[1], saved[0])

        if microservice.get("env", None):
            for env in microservice["env"]:
                saved = self.build_config_map_yaml(env)
                microservice["manifests"].update({"config_map": saved})
                self._save_yaml(saved[1], saved[0])

        # Apply overrides to the microservice manifests
        self.overrider.apply_configuration_overrides(microservice, microservice['name'])

        # Save templates
        for (path,manifest) in microservice['manifests'].values():
            self._save_yaml(manifest, path)

        # Store the overriden values for later reference
        microservice["overrides"] = self.overrider.get_microservice_overrides(microservice['name'])
    
    def build_secrets_yaml(self, secret: dict) -> Tuple[str, Dict[str, Any]]:
        """Build a YAML file from the template and data."""

        secrets_path = os.path.join(
            self.k8s_manifests_path,
            "secrets.yaml",
        )

        template = self._secret_builder.build_template(secret)

        self.logger.debug(f"Secret updated: {secrets_path}")

        return secrets_path, cast(Dict[str, Any], template)

    def build_config_map_yaml(self, config_map: dict) -> Tuple[str, Dict[str, Any]]:
        """Build a YAML file from the template and data."""

        # Prepare the Kubernetes ConfigMap template
        template = self._configmap_builder.build_template(config_map)

        # Write the updated content back to the config map file
        config_map_path = os.path.join(
            self.k8s_manifests_path,
            "config_map.yaml",
        )

        self.logger.debug(f"Config map updated: {config_map_path}")

        return config_map_path,cast(Dict[str, Any], template)

    def build_deployment_yaml(self, deployment: dict) -> Tuple[str, Dict[str, Any]]:
        """Build a YAML file from the template and data."""

        template = self._deployment_builder.build_template(deployment)
        # Convert the template to YAML string
        deployment_path = os.path.join(
            self.k8s_manifests_path,
            "deployment",
            f"{deployment['name']}.yaml",
        )

        return deployment_path, cast(Dict[str, Any], template)

    def build_stateful_set_yaml(self, stateful_set: dict) -> Tuple[str, Dict[str, Any]]:
        """Build a YAML file from the template and data."""

        # Prepare the stateful set entry
        template = self.statefulset_builder.build_template(stateful_set)
        # Convert the template to YAML string
        stateful_set_path = os.path.join(
            self.k8s_manifests_path,
            "stateful_set",
            f"{stateful_set['name']}.yaml",
        )

        return stateful_set_path, cast(Dict[str, Any], template)

    def build_service_yaml(self, service: dict) -> Tuple[str, Dict[str, Any]]:
        """Build a YAML file from the template and data."""

        template = self._servicebuilder.build_template(service)
        # Convert the template to YAML string
        service_path = os.path.join(
            self.k8s_manifests_path, "service", f"{service['name']}.yaml"
        )

        return service_path, cast(Dict[str, Any], template)

    def build_pvc_yaml(self, pvc: dict) -> Tuple[str, Dict[str, Any]]:
        """Build a YAML file from the template and data."""
        
        template = self.pvc_builder.build_template(pvc)

        # Convert the template to YAML string
        pvc_path = os.path.join(
            self.k8s_manifests_path, "pvc", f"{pvc['name']}.yaml"
        )

        return pvc_path, cast(Dict[str, Any], template)

    def generate_skaffold_config(self, microservices: List[Dict[str, Any]], output_dir: Optional[str]) -> str:
        """Generate a Skaffold configuration file."""

        output_dir = output_dir or self.manual_manifests_path

        skaffold_config = self.skaffold_builder.build_template(microservices, output_dir)
   
        self.generate_kustomization_file(output_dir)

        # Write the Skaffold config
        skaffold_path = os.path.join(output_dir, "skaffold.yaml")
        self._save_yaml(skaffold_config, skaffold_path)

        self.logger.info(f"Generated Skaffold configuration at {skaffold_path}")

        return skaffold_path

    def generate_kustomization_file(self, output_dir: Optional[str] = None):
        """Generate a kustomization.yaml file for the manifests in the output directory."""
        output_dir = output_dir or self.k8s_manifests_path
        kustomization = self.skaffold_builder.build_kustomization_template(output_dir)

        # Write the kustomization file
        kustomization_path = os.path.join(
            output_dir, "kustomization.yaml"
        )
        self._save_yaml(kustomization, kustomization_path)

        self.logger.info(f"Generated kustomization file at {kustomization_path}")

        return kustomization_path

    def _save_yaml(self, template: dict, path: str) -> None:
        """Save the template as a YAML file."""

        # Create a custom dumper that handles Helm templates correctly
        class NoAliasDumper(yaml.SafeDumper):
            def ignore_aliases(self, _):  # type: ignore
                return True

        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, "w") as file:
            yaml.dump(
                template,
                file,
                Dumper=NoAliasDumper,
                sort_keys=False,
                default_flow_style=False,
            )
        self.logger.debug(f"YAML file saved to {path}")


