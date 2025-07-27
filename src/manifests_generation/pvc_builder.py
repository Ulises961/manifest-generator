from copy import deepcopy
import os
from typing import Any, List, cast, Dict
import yaml
from utils.file_utils import load_json_file, remove_none_values


class PVCBuilder:

    def _get_pvc_template(self) -> Dict[str, Any]:
        """Get the PVC template."""
        template = load_json_file(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                os.getenv("PVC_TEMPLATE_PATH", "resources/k8s_templates/pvc.json"),
            )
        )
        return cast(Dict[str, Any], deepcopy(template))

    def build_template(self, pvc: dict) -> Dict[str, Any]:
        """Build a YAML file from the template and data."""
        # Prepare the PVC entry
        pvc_entry = {
            "name": pvc["name"],
            "labels": pvc.get("labels", []),
            "storage_class": pvc.get("storage_class", None),
            "access_modes": pvc.get("access_modes", None),
            "resources": pvc.get("resources", None),
        }

        template = self._get_pvc_template()
        template["metadata"]["name"] = pvc_entry["name"]
        template["metadata"]["labels"] = pvc_entry["labels"]

        template["spec"]["storageClassName"] = pvc_entry["storage_class"]
        template["spec"]["accessModes"] = pvc_entry["access_modes"]
        template["spec"]["resources"]["requests"]["storage"] = pvc_entry["resources"]

        # Remove all None values from the template
        template = remove_none_values(template)
        return cast(Dict[str, Any], template)
