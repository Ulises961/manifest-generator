import os
from typing import Any, Dict, cast
from embeddings.embeddings_engine import EmbeddingsEngine
from embeddings.service_classifier import ServiceClassifier
from utils.file_utils import load_file, remove_none_values
from caseutil import to_kebab
import yaml


class ManifestBuilder:
    """Manifest builder for microservices."""

    def __init__(self, embeddings_engine: EmbeddingsEngine) -> None:
        """Initialize the tree builder with the manifest templates."""
        self._config_map_template = self._get_config_map_template()
        self.deployment_template = self._get_deployment_template()
        self._service_template = self._get_service_template()
        self._stateful_set_template = self._get_stateful_set_template()
        self._pvc_template = self._get_pvc_template()
        self.service_classifier = ServiceClassifier(embeddings_engine)


        self.target_path = os.getenv("TARGET_PATH", "target/charts")
        self.manifests_path = os.path.join(self.target_path, os.getenv("MANUAL_MANIFESTS_PATH", "manual_manifests"))
        self.values_file_path = os.path.join(self.target_path, os.getenv("VALUES_FILE_PATH", "values.yaml"))

        os.makedirs(os.path.dirname(self.target_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.manifests_path), exist_ok=True)
        os.makedirs(os.path.dirname(self.values_file_path), exist_ok=True)


    def get_template(self, template_name: str) -> Dict[str, Any]:
        """Get the template by name."""
        templates = {
            "config_map": self._config_map_template,
            "deployment": self.deployment_template,
            "service": self._service_template,
            "stateful_set": self._stateful_set_template,
            "pvc": self._pvc_template,
        }

        assert template_name in templates, f"Template {template_name} not found"
        return templates[template_name]

    def _load_template(self, path: str) -> dict:
        """Load a template from the given path."""
        template = load_file(path)
        return cast(dict, template)

    def _get_config_map_template(self) -> dict:
        """Get the config map template."""
        return self._load_template(
            os.path.join(
                os.path.dirname(__file__),
                os.getenv(
                    "CONFIG_MAP_TEMPLATE_PATH", "resources/k8s_templates/configmap.json"
                ),
            )
        )

    def _get_deployment_template(self) -> dict:
        """Get the deployment template."""
        return self._load_template(
            os.path.join(
                os.path.dirname(__file__),
                os.getenv(
                    "DEPLOYMENT_TEMPLATE_PATH",
                    "resources/k8s_templates/deployment.json",
                ),
            )
        )

    def _get_service_template(self) -> dict:
        """Get the service template."""
        return self._load_template(
            os.path.join(
                os.path.dirname(__file__),
                os.getenv(
                    "SERVICES_TEMPLATE_PATH", "resources/k8s_templates/services.json"
                ),
            )
        )

    def _get_stateful_set_template(self) -> dict:
        """Get the stateful set template."""
        return self._load_template(
            os.path.join(
                os.path.dirname(__file__),
                os.getenv(
                    "STATEFULSET_TEMPLATE_PATH",
                    "resources/k8s_templates/statefulset.json",
                ),
            )
        )

    def _get_pvc_template(self) -> dict:
        """Get the PVC template."""
        return self._load_template(
            os.path.join(
                os.path.dirname(__file__),
                os.getenv("PVC_TEMPLATE_PATH", "resources/k8s_templates/pvc.json"),
            )
        )

    def generate_manifests(self, microservice: Dict[str, Any]) -> None:
        """Generate manifests for the microservice and its dependencies."""
        if microservice.get("workload", None):
            if microservice["workload"] == "StatefulSet":
                self.build_stateful_set_yaml(microservice)
            elif microservice["workload"] == "Deployment":
                self.build_deployment_yaml(microservice)
        else:
            self.build_deployment_yaml(microservice)

        if microservice.get("ports", None):
            self.build_service_yaml(microservice)

        if microservice.get("persistent_volumes", None):
            for pvc in microservice["persistent_volumes"]:
                self.build_pvc_yaml(pvc)

        if microservice.get("secrets", None):
            for secret in microservice["secrets"]:
                self.build_secrets_yaml(secret)

        if microservice.get("env", None):
            for env in microservice["env"]:
                if env.get("config", None):
                    self.build_config_map_yaml(env)

    def build_secrets_yaml(self, secret: dict) -> None:
        """Build a YAML file from the template and data."""
        # Check if the values.yaml file exists
        values_file_path = os.path.join(
            self.values_file_path,
        )
        secret_name = to_kebab(secret["name"])

        # Prepare the secret entry
        secret_entry = {
            f"{secret_name}": {
                "name": secret_name,
                "password": secret["value"],
            }
        }

        # Remove all None values from the secret entry
        secret_entry = remove_none_values(secret_entry)

        if not os.path.exists(values_file_path):
            self._save_yaml(secret_entry, self.values_file_path)

        else:
            # Load existing values.yaml content
            with open(values_file_path, "r") as file:
                existing_data = yaml.safe_load(file) or {}

            # Update or add the secret entry
            existing_data.setdefault("secrets", {})
            existing_data["secrets"].update(secret_entry)

            # Write the updated content back to the values.yaml file
            self._save_yaml(existing_data, self.values_file_path)

        # Prepare the Kubernetes Secret template
        template = self.get_template("config_map")
        template["kind"] = "Secret"
        template["metadata"]["name"] = "{{ .Values.secrets." + secret_name + ".name }}"
        template["type"] = "Opaque"
        template["data"] = {
            "password": "{{ .Values.secrets." + secret_name + ".password }}"
        }

        # Remove all None values from the template
        template = remove_none_values(template)

        # Convert the template to YAML string
        secrets_path = os.path.join(
            self.manifests_path,
            "secrets",
        )

        os.path.join(secrets_path, f"{secret_name}-secret.yaml")

        self._save_yaml(
            template, os.path.join(secrets_path, f"{secret_name}-secret.yaml")
        )

    def build_config_map_yaml(self, config_map: dict) -> None:
        """Build a YAML file from the template and data."""
        config_map_name = to_kebab(config_map["name"])

        # Prepare the config map entry
        config_map_entry = {
            f"config-{config_map_name}": {
                "name": config_map_name,
                "config": config_map["config"],
            }
        }

        config_map_entry = remove_none_values(config_map_entry)

        if not os.path.exists(self.values_file_path):
            # Create the values.yaml file if it doesn't exist
            self._save_yaml(config_map_entry, self.values_file_path)
        else:
            # Load existing values.yaml content
            with open(self.values_file_path, "r") as file:
                existing_data = yaml.safe_load(file) or {}

            # Update or add the config map entry
            existing_data.setdefault("config", {})
            existing_data["config"][f"config-{config_map_name}"] = config_map_entry

            # Write the updated content back to the values.yaml file
            self._save_yaml(existing_data, self.values_file_path)

        # Remove all None values from the config map entry
        config_map_entry = remove_none_values(config_map_entry)

        # Prepare the Kubernetes ConfigMap template
        template = self.get_template("config_map")
        template["kind"] = "ConfigMap"
        template["metadata"]["name"] = f"config-{config_map_name}"
        template["data"] = {
            "config": f"{{{{ .Values.config.{config_map_name}.config }}}}"
        }
        # Convert the template to YAML string
        config_map_path = os.path.join(
            self.manifests_path,
            "config_maps",
        )

        os.path.join(config_map_path, f"{config_map_name}-config_map.yaml")

        self._save_yaml(
            template,
            os.path.join(config_map_path, f"{config_map_name}-config_map.yaml"),
        )

    def build_deployment_yaml(self, deployment: dict) -> None:
        """Build a YAML file from the template and data."""

        service_name = to_kebab(deployment["name"])

        deployment_entry = {
            "name": service_name,
            "labels": deployment["labels"],
            "command": deployment["command"],
            "args": deployment["args"] if "args" in deployment else None,
            "env": deployment["env"] if "env" in deployment else None,
            "volumes": deployment["volumes"] if "volumes" in deployment else None,
            "volume_mounts": (
                deployment["volume_mounts"] if "volume_mounts" in deployment else None
            ),
            "ports": deployment["ports"] if "ports" in deployment else None,
            "workdir": deployment["workdir"] if "workdir" in deployment else None,
            "liveness_probe": (
                deployment["liveness_probe"] if "liveness_probe" in deployment else None
            ),
            "user": deployment["user"] if "user" in deployment else None,
        }

        if "secrets" in deployment:
            for secret in deployment["secrets"]:
                deployment_entry["env"].append(
                    {
                        "name": secret["name"],
                        "valueFrom": {
                            "secretKeyRef": {
                                "name": f"{{{{ .Values.secrets.{to_kebab(secret['name'])}.name }}}}",
                                "key": "password",
                            }
                        },
                    }
                )

        deployment_entry = remove_none_values(deployment_entry)

        # Prepare the deployment entry for values.yaml
        if not os.path.exists(self.values_file_path):
            # Create the values.yaml file if it doesn't exist
            self._save_yaml(deployment_entry, self.values_file_path)
        else:
            # Load existing values.yaml content
            with open(self.values_file_path, "r") as file:
                existing_data = yaml.safe_load(file) or {}

            # Update or add the deployment entry
            existing_data.setdefault("deployment", {})
            existing_data["deployment"][f"deployment-{service_name}"] = deployment
            # Write the updated content back to the values.yaml file
            self._save_yaml(existing_data, self.values_file_path)

        # Prepare the Kubernetes Deployment template
        deployment_values = f"Values.deployment.{service_name}"
        template = self.get_template("deployment")
        template["metadata"]["name"] = "{{ " + deployment_values + ".name }}"
        template["metadata"]["labels"] = "{{ " + deployment_values + ".labels }}"
        if "annotations" in deployment:
            template["metadata"]["annotations"] = "{{ " + deployment_values + ".annotations }}"
        template["spec"]["selector"][
            "matchLabels"
        ] = "{{ " + deployment_values + ".labels }}"
        template["spec"]["template"]["metadata"][
            "labels"
        ] = "{{ " + deployment_values + ".labels }}"
        template["spec"]["template"]["spec"]["containers"][0][
            "name"
        ] = "{{ " + deployment_values +".name }}"

        template["spec"]["template"]["spec"]["containers"][0][
            "command"
        ] = "{{ " + deployment_values + ".command }}"
        template["spec"]["template"]["spec"]["containers"][0][
            "args"
        ] = "{{ " + deployment_values + ".args }}"

        if "user" in deployment:
            template["spec"]["template"]["spec"]["containers"][0]["securityContext"] = {
                "runAsUser": "{{ " + deployment_values + ".user }}"
            }

        # Load volumes and their mounts
        if "volumes" in deployment:
            template["spec"]["template"]["spec"]["containers"][0][
                "volumeMounts"
            ] = "{{ " + deployment_values + ".volume_mounts }}"
            template["spec"]["template"]["spec"][
                "volumes"
            ] = "{{ " + deployment_values + ".volumes }}"

        if "ports" in deployment:
            template["spec"]["template"]["spec"]["containers"][0][
                "ports"
            ] = "{{ " + deployment_values + ".ports }}"

        if "workdir" in deployment:
            template["spec"]["template"]["spec"]["containers"][0][
                "workingDir"
            ] = "{{ " + deployment_values + ".workdir }}"

        if "liveness_probe" in deployment:
            template["spec"]["template"]["spec"]["containers"][0][
                "livenessProbe"
            ] = "{{ " + deployment_values + ".liveness_probe }}"

        if "env" in deployment:
            template["spec"]["template"]["spec"]["containers"][0][
                "env"
            ] = "{{ " + deployment_values + ".env }}"
        # Remove all None values from the template
        template = remove_none_values(template)

        # Convert the template to YAML string
        deployment_path = os.path.join(
            self.manifests_path,
            "deployments",
        )

        os.path.join(deployment_path, f"{deployment['name']}-deployment.yaml")

        self._save_yaml(
            template,
            os.path.join(deployment_path, f"{deployment['name']}-deployment.yaml"),
        )

    def build_stateful_set_yaml(self, stateful_set: dict) -> None:
        """Build a YAML file from the template and data."""

        stateful_set_name = to_kebab(stateful_set["name"])

        # Prepare the stateful set entry
        stateful_set_entry = {
            "name": stateful_set_name,
            "labels": stateful_set["labels"],
            "command": stateful_set["command"],
            "args": stateful_set["args"] if "args" in stateful_set else None,
            "env": stateful_set["env"] if "env" in stateful_set else None,
            "volumes": stateful_set["volumes"] if "volumes" in stateful_set else None,
            "volume_mounts": (
                stateful_set["volume_mounts"]
                if "volume_mounts" in stateful_set
                else None
            ),
            "ports": stateful_set["ports"] if "ports" in stateful_set else None,
            "workdir": stateful_set["workdir"] if "workdir" in stateful_set else None,
            "liveness_probe": (
                stateful_set["liveness_probe"]
                if "liveness_probe" in stateful_set
                else None
            ),
            "user": stateful_set["user"] if "user" in stateful_set else None,
        }

        if stateful_set["secrets"] is not None:
            for secret in stateful_set["secrets"]:
                stateful_set_entry["env"].append(
                    {
                        "name": secret["name"],
                        "valueFrom": {
                            "secretKeyRef": {
                                "name": f"{{{{ .Values.secrets.{to_kebab(secret['name'])}.name }}}}",
                                "key": "password",
                            }
                        },
                    }
                )

        stateful_set_entry = remove_none_values(stateful_set_entry)

        # Prepare the stateful set entry for values.yaml
        if not os.path.exists(self.values_file_path):
            # Create the values.yaml file if it doesn't exist
            self._save_yaml(stateful_set_entry, self.values_file_path)
        else:
            # Load existing values.yaml content
            with open(self.values_file_path, "r") as file:
                existing_data = yaml.safe_load(file) or {}

            # Update or add the stateful set entry
            existing_data.setdefault("stateful-set", {})
            existing_data["stateful-set"][
                f"stateful-set-{stateful_set_name}"
            ] = stateful_set_entry

            # Write the updated content back to the values.yaml file
            self._save_yaml(existing_data, self.values_file_path)

        # Prepare the Kubernetes StatefulSet template
        stateful_set_values = f"Values.stateful-set.{stateful_set_name}"
        template = self.get_template("statefullset")
        template["metadata"]["name"] = "{{ " + stateful_set_values + ".name }}"
        template["metadata"]["labels"] = "{{ " + stateful_set_values + ".labels }}"
        template["spec"]["selector"]["matchLabels"] = (
            "{{ " + stateful_set_values + ".labels }}"
        )

        template["spec"]["template"]["metadata"]["labels"] = (
            "{{ " + stateful_set_values + ".labels }}"
        )

        template["spec"]["template"]["spec"]["containers"][0]["name"] = (
            "{{ " + stateful_set_values + ".name }}"
        )

        template["spec"]["template"]["spec"]["containers"][0]["command"] = (
            "{{ " + stateful_set_values + ".command }}"
        )

        template["spec"]["template"]["spec"]["containers"][0]["args"] = (
            "{{ " + stateful_set_values + ".args }}"
        )

        if "user" in stateful_set:
            template["spec"]["template"]["spec"]["containers"][0]["securityContext"] = {
                "runAsUser": "{{ " + stateful_set_values + ".user }}"
            }

        template["spec"]["template"]["spec"]["containers"][0]["env"] = (
            "{{ " + stateful_set_values + ".env }}"
        )

        if "volumes" in stateful_set:
            template["spec"]["template"]["spec"]["containers"][0]["volumeMounts"] = (
                "{{ " + stateful_set_values + ".volume_mounts }}"
            )

            template["spec"]["template"]["spec"]["volumes"] = (
                "{{ " + stateful_set_values + ".volumes }}"
            )

        if "ports" in stateful_set:
            template["spec"]["template"]["spec"]["containers"][0]["ports"] = (
                "{{ " + stateful_set_values + ".ports }}"
            )

        if "workdir" in stateful_set:
            template["spec"]["template"]["spec"]["containers"][0]["workingDir"] = (
                "{{ " + stateful_set_values + ".workdir }}"
            )
        if "liveness_probe" in stateful_set:
            template["spec"]["template"]["spec"]["containers"][0]["livenessProbe"] = (
                "{{ " + stateful_set_values + ".liveness_probe }}"
            )
        # Remove all None values from the template
        template = remove_none_values(template)
        # Convert the template to YAML string
        stateful_set_path = os.path.join(
            os.path.dirname(__file__),
            self.target_path,
            self.manifests_path,
            "stateful_sets",
        )

        os.path.join(stateful_set_path, f"{stateful_set['name']}-stateful_set.yaml")

        self._save_yaml(
            template,
            os.path.join(
                stateful_set_path, f"{stateful_set['name']}-stateful_set.yaml"
            ),
        )

    def build_service_yaml(self, service: dict) -> None:
        """Build a YAML file from the template and data."""

        # Check if the values.yaml file exists
        service_name = to_kebab(service["name"])
        # Prepare the service entry
        service_entry = {
            "name": service_name,
            "labels": service["labels"],
            "ports": service["ports"],
            "target_port": service["service-ports"],
            "protocol": service["protocol"],
            "type": service["type"],
        }

        service_entry = remove_none_values(service_entry)

        # Prepare the service entry for values.yaml
        if not os.path.exists(self.values_file_path):
            # Create the values.yaml file if it doesn't exist
            self._save_yaml(service_entry, self.values_file_path)
        else:
            # Load existing values.yaml content
            with open(self.values_file_path, "r") as file:
                existing_data = yaml.safe_load(file) or {}

            # Update or add the service entry
            existing_data.setdefault(f"service", {})
            existing_data["service"][f"service-{service_name}"] = service_entry

            # Write the updated content back to the values.yaml file
            self._save_yaml(existing_data, self.values_file_path)

        # Prepare the Kubernetes Service template
        service_values = f"Values.service.{service_name}"
        template = self.get_template("service")
        template["metadata"]["name"] = "{{ " + service_values + ".name }}"
        template["metadata"]["labels"] = "{{ " + service_values + ".labels }}"
        template["spec"]["selector"] = "{{ " + service_values + ".labels }}"
        template["spec"]["ports"][0]["port"] = "{{ " + service_values + ".port }}"
        template["spec"]["ports"][0]["targetPort"] = (
            "{{ " + service_values + ".target_port }}"
        )
        template["spec"]["ports"][0]["protocol"] = (
            "{{ " + service_values + ".protocol }}"
        )
        template["spec"]["ports"][0]["name"] = "{{ " + service_values + ".name }}"
        template["spec"]["type"] = "{{ " + service_values + ".type }}"
        # Remove all None values from the template
        template = remove_none_values(template)

        # Convert the template to YAML string
        service_path = os.path.join(
            self.manifests_path,
            "services",
        )

        os.path.join(service_path, f"{service['name']}-service.yaml")
        self._save_yaml(
            template, os.path.join(service_path, f"{service['name']}-service.yaml")
        )

    def build_pvc_yaml(self, pvc: dict) -> None:
        """Build a YAML file from the template and data."""
        pvc_name = to_kebab(pvc["name"])
        # Prepare the PVC entry
        pvc_entry = {
            "name": pvc_name,
            "labels": pvc.get("labels", []),
            "storage_class": pvc.get("storage_class", None),
            "access_modes": pvc.get("access_modes", None),
            "resources": pvc.get("resources", None),
        }

        # Remove all None values from the PVC entry
        pvc_entry = remove_none_values(pvc_entry)

        # Prepare the PVC entry for values.yaml
        if not os.path.exists(self.values_file_path):
            # Create the values.yaml file if it doesn't exist
            self._save_yaml(pvc_entry, self.values_file_path)
        else:
            # Load existing values.yaml content
            with open(self.values_file_path, "r") as file:
                existing_data = yaml.safe_load(file) or {}

            # Update or add the PVC entry
            existing_data.setdefault("pvc", {})
            existing_data["pvc"][f"pvc-{pvc_name}"] = pvc_entry

            # Write the updated content back to the values.yaml file
            self._save_yaml(existing_data, self.values_file_path)

        # Prepare the Kubernetes PVC template
        pvc_values = f"Values.pvc.{pvc_name}"
        template = self.get_template("pvc")
        template["metadata"]["name"] = "{{ " + pvc_values + ".name }}"
        template["metadata"]["labels"] = "{{ " + pvc_values + ".labels }}"
        template["spec"]["storageClassName"] = "{{ " + pvc_values + ".storage_class }}"
        template["spec"]["accessModes"] = "{{ " + pvc_values + ".access_modes }}"
        template["spec"]["resources"]["requests"]["storage"] = (
            "{{ " + pvc_values + ".resources }}"
        )

        # Remove all None values from the template
        template = remove_none_values(template)

        # Convert the template to YAML string
        pvc_path = os.path.join(
            self.manifests_path,
            "pvcs",
        )

        os.path.join(pvc_path, f"{pvc['name']}-pvc.yaml")
        self._save_yaml(template, os.path.join(pvc_path, f"{pvc['name']}-pvc.yaml"))

    def _save_yaml(self, template: dict, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as file:
            yaml.dump(template, file)
        print(f"YAML file saved to {path}")
