from copy import deepcopy
import os
from typing import Any, List, cast, Dict

from utils.file_utils import load_json_file, remove_none_values


class DeploymentBuilder:
    def _get_deployment_template(self) -> Dict[str, Any]:
        """Get the deployment template."""
        template = load_json_file(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                os.getenv(
                    "DEPLOYMENT_TEMPLATE_PATH",
                    "resources/k8s_templates/deployment.json",
                ),
            )
        )
        return cast(Dict[str, Any], deepcopy(template))

    def build_template(self, deployment: dict) -> Dict[str, Any]:
        """Build a YAML file from the template and data."""

        deployment_entry: Dict[str, Any] = {
            "name": deployment["name"],
            "labels": deployment["labels"],
            "command": deployment["command"],
            "args": deployment.get("args"),
            "image": deployment["image"],
            "volumes": deployment.get("volumes"),
            "volume_mounts": deployment.get("volume_mounts"),
            "ports": {"containerPort": port for port in deployment.get("ports", [])},
            "workdir": deployment.get("workdir"),
            "liveness_probe": deployment.get("liveness_probe"),
            "user": deployment.get("user"),
        }


        template = self._get_deployment_template()
        template["metadata"]["name"] = deployment_entry["name"]
        template["metadata"]["labels"] = deployment_entry["labels"]

        if "annotations" in deployment:
            template["metadata"]["annotations"] = deployment["annotations"]

        template["spec"]["selector"]["matchLabels"] = {
            "app.kubernetes.io/name": deployment_entry["labels"]["app.kubernetes.io/name"]
        }
        template["spec"]["template"]["metadata"]["labels"] = deployment_entry["labels"]
        template["spec"]["template"]["spec"]["containers"][0]["name"] = (
            deployment_entry["name"]
        )

        template["spec"]["template"]["spec"]["containers"][0]["image"] = (
            deployment_entry["image"]
        )

        template["spec"]["template"]["spec"]["containers"][0]["command"] = (
            deployment_entry["command"]
        )

        if "args" in deployment:
            template["spec"]["template"]["spec"]["containers"][0]["args"] = (
                deployment_entry["args"]
            )
        if "user" in deployment:
            template["spec"]["template"]["spec"]["containers"][0]["securityContext"] = {
                "runAsUser": deployment_entry["user"]
            }

        # Load volumes and their mounts
        if "volumes" in deployment:
            template["spec"]["template"]["spec"]["containers"][0]["volumeMounts"] = (
                deployment_entry["volume_mounts"]
            )

            template["spec"]["template"]["spec"]["volumes"] = deployment_entry[
                "volumes"
            ]

        if "ports" in deployment_entry and len(deployment_entry["ports"].keys()) > 0:
            template["spec"]["template"]["spec"]["containers"][0]["ports"] = [
                deployment_entry["ports"]
            ]

        if "workdir" in deployment:
            template["spec"]["template"]["spec"]["containers"][0]["workingDir"] = (
                deployment_entry["workdir"]
            )

        if "liveness_probe" in deployment:
            template["spec"]["template"]["spec"]["containers"][0]["livenessProbe"] = (
                deployment_entry["liveness_probe"]
            )

        if "env" in deployment:
            env_vars = []
            for entry in deployment["env"]:
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
