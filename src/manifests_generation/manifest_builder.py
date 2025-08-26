import logging
import os
from typing import Any, Dict, List, Optional, Tuple, cast
from overrides.overrider import Overrider

from manifests_generation.skaffold_config_builder import SkaffoldConfigBuilder
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
        self._skaffold_builder = SkaffoldConfigBuilder()

 
    def generate_skaffold_config(self, microservices: List[Dict[str, Any]], output_dir: Optional[str]) -> str:
        """Generate a Skaffold configuration file."""

        output_dir = output_dir or self.manual_manifests_path

        skaffold_config = self._skaffold_builder.build_template(microservices, output_dir)
   
        self.generate_kustomization_file(output_dir)

        # Write the Skaffold config
        skaffold_path = os.path.join(output_dir, "skaffold.yaml")
        self._save_yaml(skaffold_config, skaffold_path)

        self.logger.info(f"Generated Skaffold configuration at {skaffold_path}")

        return skaffold_path

    def generate_kustomization_file(self, output_dir: Optional[str] = None):
        """Generate a kustomization.yaml file for the manifests in the output directory."""
        output_dir = output_dir or self.k8s_manifests_path
        kustomization = self._skaffold_builder.build_kustomization_template(output_dir)

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
                width=1000,  # Prevent automatic line wrapping
                default_flow_style=False,
            )
        self.logger.debug(f"YAML file saved to {path}")


