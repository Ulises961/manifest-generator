from copy import deepcopy
import os
from typing import Any, cast, Dict
import yaml
from utils.file_utils import load_file

class ConfigMapBuilder:
    def __init__(self, k8s_manifests_path: str = "k8s"):
        self.k8s_manifests_path = k8s_manifests_path

    def _get_configmap_template(self) -> Dict[str, Any]:
        """Get the config map template."""
        template = load_file(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                os.getenv(
                    "CONFIG_MAP_TEMPLATE_PATH", "resources/k8s_templates/configmap.json"
                ),
            )
        )
        return cast(Dict[str, Any], deepcopy(template))
    
    def build_template(self, config_map: dict) -> Dict[str, Any]:
            """Build a YAML file from the template and data."""
            # Convert the template to YAML string
            config_map_path = os.path.join(
                self.k8s_manifests_path,
                "config_map.yaml",
            )

            # Prepare the Kubernetes ConfigMap template
            template = self._get_configmap_template()
            template["kind"] = "ConfigMap"
            template["metadata"]["name"] = f"config"
            template["metadata"]["labels"] = {"environment": "production"}
            template["data"] = {config_map["name"]: config_map["value"]}

            if not os.path.exists(config_map_path):
                return template
            
            else:
                # Load existing config map content
                with open(config_map_path, "r") as file:
                    existing_data = yaml.safe_load(file) or template

                # Update or add the config map entry
                existing_data.setdefault("data", {})
                existing_data["data"].update({config_map["name"]: config_map["value"]})
                return cast(Dict[str, Any],existing_data)
