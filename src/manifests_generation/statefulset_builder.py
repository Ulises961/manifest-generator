from copy import deepcopy
import os
from typing import Any, List, cast, Dict
from utils.file_utils import load_json_file, remove_none_values


class StatefulSetBuilder:
    def _get_stateful_set_template(self) -> dict:
        """Get the stateful set template."""
        template = load_json_file(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                os.getenv(
                    "STATEFULSET_TEMPLATE_PATH",
                    "resources/k8s_templates/statefulset.json",
                ),
            )
        )
        return cast(Dict[str, Any], deepcopy(template))

    def build_template(self, stateful_set: dict) -> Dict[str, Any]:
        """Build a YAML file from the template and data."""

        # Prepare the stateful set entry
        stateful_set_entry = {
            "name": stateful_set["name"],
            "labels": stateful_set["labels"],
            "image": stateful_set["name"],
            "command": stateful_set["command"],
            "args": stateful_set.get("args", None),
            "volumes": stateful_set.get("volumes", None),
            "volume_mounts": stateful_set.get("volume_mounts", None),
            "ports": stateful_set.get("ports", None),
            "workdir": stateful_set.get("workdir", None),
            "liveness_probe": stateful_set.get("liveness_probe", None),
            "user": stateful_set.get("user", None),
            "service_account": stateful_set["name"]
        }

        template = self._get_stateful_set_template()

        template["metadata"]["name"] = stateful_set_entry["name"]
        template["metadata"]["labels"] = stateful_set_entry["labels"]

        if "annotations" in stateful_set:
            template["metadata"]["annotations"] = stateful_set["annotations"]
        template["spec"]["selector"]["matchLabels"] = stateful_set_entry["labels"]

        template["spec"]["template"]["metadata"]["labels"] = stateful_set_entry[
            "labels"
        ]

        if "ports" in stateful_set:
            template["spec"]["template"]["spec"]["serviceAccountName"] = (
                stateful_set_entry["service_account"]
            )
            
        template["spec"]["template"]["spec"]["containers"][0]["name"] = (
            stateful_set_entry["name"]
        )

        template["spec"]["template"]["spec"]["containers"][0]["image"] = (
            stateful_set_entry["image"]
        )

        template["spec"]["template"]["spec"]["containers"][0]["command"] = (
            stateful_set_entry["command"]
        )

        if "args" in stateful_set:
            template["spec"]["template"]["spec"]["containers"][0]["args"] = (
                stateful_set_entry["args"]
            )

        if "user" in stateful_set:
            template["spec"]["template"]["spec"]["containers"][0]["securityContext"] = {
                "runAsUser": stateful_set_entry["user"]
            }

        if "volumes" in stateful_set:
            template["spec"]["template"]["spec"]["containers"][0]["volumeMounts"] = (
                stateful_set_entry["volume_mounts"]
            )

            template["spec"]["template"]["spec"]["volumes"] = stateful_set_entry[
                "volumes"
            ]

        if "ports" in stateful_set:
            template["spec"]["template"]["spec"]["containers"][0]["ports"] = stateful_set_entry["ports"]
            

        if "workdir" in stateful_set:
            template["spec"]["template"]["spec"]["containers"][0]["workingDir"] = (
                stateful_set_entry["workdir"]
            )

        if "liveness_probe" in stateful_set:
            template["spec"]["template"]["spec"]["containers"][0]["livenessProbe"] = (
                stateful_set_entry["liveness_probe"]
            )

        if "env" in stateful_set:
            env_vars = []
            for entry in stateful_set["env"]:
                if entry.get("key") == "password":
                    env_vars.append(
                        {
                            "name": entry["name"],
                            "valueFrom": {
                                "secretKeyRef": {
                                    "name": "config",
                                    "key": entry["name"],
                                }
                            },
                        }
                    )
                else:
                    env_vars.append(
                        {
                            "name": entry["name"],
                            "valueFrom": {
                                "configMapKeyRef": {
                                    "name": "config",
                                    "key": entry["name"],
                                }
                            },
                        }
                    )

            template["spec"]["template"]["spec"]["containers"][0]["env"] = env_vars
        # Remove all None values from the template
        template = remove_none_values(template)

        return cast(Dict[str, Any], template)
