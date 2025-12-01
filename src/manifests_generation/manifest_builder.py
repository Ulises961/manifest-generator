import logging
import os
from typing import Any, Dict, List, Optional, Tuple, cast
from overrides.overrider import Overrider

from manifests_generation.skaffold_config_builder import SkaffoldConfigBuilder
import yaml


class ManifestBuilder:
    """Manifest builder for microservices."""

    def __init__(self, overrider: Optional[Overrider] = None) -> None:
        """Initialize the tree builder with the manifest templates."""
        
        self.logger = logging.getLogger(__name__)

        self.target_path = os.getenv("OUTPUT_DIR", "output")
        self.overrider = overrider
        self._skaffold_builder = SkaffoldConfigBuilder()

 
    def generate_skaffold_config(self, microservices: List[Dict[str, Any]], output_dir: str) -> str:
        """Generate a Skaffold configuration file."""

        skaffold_config = self._skaffold_builder.build_template(microservices, output_dir)
        self.generate_kustomization_file(output_dir)

        # Write the Skaffold config
        skaffold_path = os.path.join(output_dir, "skaffold.yaml")
        self._save_yaml(skaffold_config, skaffold_path)

        self.logger.info(f"Generated Skaffold configuration at {skaffold_path}")

        return skaffold_path

    def generate_kustomization_file(self, output_dir: str):
        """Generate a kustomization.yaml file for the manifests in the output directory."""
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


