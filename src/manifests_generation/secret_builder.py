from copy import deepcopy
import os
from typing import Any, List, cast, Dict
import yaml
from utils.file_utils import load_json_file, remove_none_values


class SecretBuilder:
    def __init__(self, k8s_manifests_path: str = "k8s"):
        self.k8s_manifests_path = k8s_manifests_path

    def _get_configmap_template(self) -> Dict[str, Any]:
        """Get the config map template."""
        template = load_json_file(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                os.getenv(
                    "CONFIG_MAP_TEMPLATE_PATH", "resources/k8s_templates/configmap.json"
                ),
            )
        )
        return cast(Dict[str, Any], deepcopy(template))

    def build_template(self, secret: dict) -> Dict[str, Any]:
        """Build a YAML file from the template and data."""
        # Convert the template to YAML string
        secrets_path = os.path.join(
            self.k8s_manifests_path,
            "secrets.yaml",
        )

        if not os.path.exists(secrets_path):
            # Prepare the Kubernetes ConfigMap template
            template = self._get_configmap_template()
            template["kind"] = "Secret"
            template["metadata"]["name"] = "secrets"
            template["metadata"]["labels"] = {"environment": "production"}
            template["type"] = "Opaque"
            template["data"] = {secret["name"]: secret["value"]}
            template = remove_none_values(template)

            return cast(Dict[str, Any], template)

        else:
            # Load existing config map content
            with open(secrets_path, "r") as file:
                existing_data = yaml.safe_load(file) or {}

            # Update or add the secret entry
            existing_data.setdefault("data", {})
            existing_data["data"].update({secret["name"]: secret["value"]})
            return cast(Dict[str, Any], existing_data)
