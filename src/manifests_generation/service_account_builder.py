from copy import deepcopy
import os
from typing import Any, List, cast, Dict
import yaml
from utils.file_utils import load_json_file, remove_none_values


class ServiceAccountBuilder:

    def _get_service_account_template(self) -> Dict[str, Any]:
        """Get the ServiceAccount template."""
        template = load_json_file(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                os.getenv("SERVICE_ACCOUNT_TEMPLATE_PATH", "resources/k8s_templates/service_account.json"),
            )
        )
        return cast(Dict[str, Any], deepcopy(template))

    def build_template(self, service_account: dict) -> Dict[str, Any]:
        """Build a YAML file from the template and data."""
        # Prepare the ServiceAccount entry
        service_account_entry = {
            "name": service_account["name"],
            "namespace": service_account.get("namespace", None),
        }

        template = self._get_service_account_template()
        template["metadata"]["name"] = service_account_entry["name"]
        template["metadata"]["namespace"] = service_account_entry["namespace"]

        # Remove all None values from the template
        template = remove_none_values(template)
        return cast(Dict[str, Any], template)
