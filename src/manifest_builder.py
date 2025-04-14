import os
from utils.file_utils import load_file, remove_none_values
from caseutil import to_kebab
import yaml

class ManifestBuilder:
    """Manifest builder for microservices."""

    def __init__(self):
        """Initialize the tree builder with the manifest templates."""
        self._config_map_template = self._get_config_map_template()
        self.deployment_template = self._get_deployment_template()
        self._service_template = self._get_service_template()
        self._stateful_set_template = self._get_stateful_set_template()
        self._pvc_template = self._get_pvc_template()

    def get_template(self, template_name: str) -> dict:
        """Get the template by name."""
        templates = {
            "config_map": self._config_map_template,
            "deployment": self.deployment_template,
            "service": self._service_template,
            "stateful_set": self._stateful_set_template,
            "pvc": self._pvc_template,
        }
        return templates.get(template_name)

    def _load_template(self, path: str) -> dict:
        """Load a template from the given path."""
        return load_file(path)

    def _get_config_map_template(self) -> dict:
        """Get the config map template."""
        return self._load_template(
            os.path.join(
                os.path.dirname(__file__), os.getenv("CONFIG_MAP_TEMPLATE_PATH")
            )
        )

    def _get_deployment_template(self) -> dict:
        """Get the deployment template."""
        return self._load_template(
            os.path.join(
                os.path.dirname(__file__), os.getenv("DEPLOYMENT_TEMPLATE_PATH")
            )
        )

    def _get_service_template(self) -> dict:
        """Get the service template."""
        return self._load_template(
            os.path.join(os.path.dirname(__file__), os.getenv("SERVICES_TEMPLATE_PATH"))
        )

    def _get_stateful_set_template(self) -> dict:
        """Get the stateful set template."""
        return self._load_template(
            os.path.join(
                os.path.dirname(__file__), os.getenv("STATEFULSET_TEMPLATE_PATH")
            )
        )

    def _get_pvc_template(self) -> dict:
        """Get the PVC template."""
        return self._load_template(
            os.path.join(os.path.dirname(__file__), os.getenv("PVC_TEMPLATE_PATH"))
        )

    def build_secrets_yaml(self, secret: dict) -> str:
        """Build a YAML file from the template and data."""
        # Check if the values.yaml file exists
        values_file_path = os.getenv("VALUES_FILE_PATH")
        service_name = to_kebab(secret["service"])
        secret_name = to_kebab(secret["name"])

        # Prepare the secret entry
        secret_entry = {
            f"secret-{secret_name}": {
                "name": secret_name,
                "password": secret["password"],
            }
        }

        if not os.path.exists(values_file_path):
            # Create the values.yaml file if it doesn't exist

            with open(values_file_path, "w") as file:
                yaml.dump({f"secrets": secret_entry}, file)
        else:
            # Load existing values.yaml content
            with open(values_file_path, "r") as file:
                existing_data = yaml.safe_load(file) or {}

            # Update or add the secret entry
            existing_data["secrets"][f"secret-{secret_name}"] = existing_data.get(
                f"secret-{secret_name}", {}
            )
            existing_data["secrets"][f"secret-{secret_name}"].update(secret_entry)

            # Write the updated content back to the values.yaml file
            with open(values_file_path, "w") as file:
                yaml.dump(existing_data, file)

        # Prepare the Kubernetes Secret template
        secret_values = f"Values.secrets.secret-{secret_name}"
        template = self.get_template("config_map")
        template["kind"] = "Secret"
        template["metadata"]["name"] = f"{{{secret_values}.name}}"
        template["type"] = "Opaque"
        template["data"] = {
            f"password: {{{secret_values}.password}}"
        }  # Store as a dictionary

        # Remove all None values from the template
        template = remove_none_values(template)

        # Convert the template to YAML string
        secrets_path = os.path.join(
            os.path.dirname(__file__),
            os.getenv("TARGET_PATH"),
            os.getenv("MANUAL_MANIFESTS_PATH"),
            "secrets",
        )
        os.makedirs(secrets_path, exist_ok=True)
        os.path.join(secrets_path, f"{secret_name}-secret.yaml")
        self._save_yaml(
            template, os.path.join(secrets_path, f"{secret_name}-secret.yaml")
        )

    def build_config_map_yaml(self, config_map: dict) -> str:
        """Build a YAML file from the template and data."""
        # Check if the values.yaml file exists
        values_file_path = os.getenv("VALUES_FILE_PATH")
        service_name = to_kebab(config_map["service"])
        config_map_name = to_kebab(config_map["name"])

        # Prepare the config map entry
        config_map_entry = {
            f"config-{config_map_name}": {
                "name": config_map_name,
                "config": config_map["config"],
            }
        }

        if not os.path.exists(values_file_path):
            # Create the values.yaml file if it doesn't exist
            with open(values_file_path, "w") as file:
                yaml.dump({f"configs": config_map_entry}, file)
        else:
            # Load existing values.yaml content
            with open(values_file_path, "r") as file:
                existing_data = yaml.safe_load(file) or {}

            # Update or add the config map entry
            existing_data["config"][f"config-{config_map_name}"] = existing_data.get(
                f"config-{config_map_name}", {}
            )
            existing_data["config"][f"config-{config_map_name}"].update(
                config_map_entry
            )

            # Write the updated content back to the values.yaml file
            with open(values_file_path, "w") as file:
                yaml.dump(existing_data, file)

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
            os.path.dirname(__file__),
            os.getenv("TARGET_PATH"),
            os.getenv("MANUAL_MANIFESTS_PATH"),
            "config_maps",
        )
        os.makedirs(config_map_path, exist_ok=True)
        os.path.join(config_map_path, f"{config_map_name}-config_map.yaml")
        self._save_yaml(
            template,
            os.path.join(config_map_path, f"{config_map_name}-config_map.yaml"),
        )
        # Save the YAML file
        print(f"ConfigMap YAML file saved to {config_map_path}")
        # return config_map_path

    def build_deployment_yaml(self, deployment: dict) -> str:
        """Build a YAML file from the template and data."""

        # Check if the values.yaml file exists
        values_file_path = os.getenv("VALUES_FILE_PATH")
        service_name = to_kebab(deployment["service"])
        deployment_name = to_kebab(deployment["name"])

        # Prepare the deployment entry
        deployment_entry = {
            "name": service_name,
            "labels": {deployment["labels"]},
            "command": deployment["command"],
            "args": deployment["args"],
            "env": deployment["env"],
            "volumes": deployment["volumes"],
            "volume_mounts": deployment["volume_mounts"],
            "ports": deployment["ports"],
            "workdir": deployment["workdir"],
            "liveness_probe": deployment["liveness_probe"],
            "security_context": {"runAsUser": deployment["user"]},
        }

        # Prepare the deployment entry for values.yaml
        if not os.path.exists(values_file_path):
            # Create the values.yaml file if it doesn't exist
            with open(values_file_path, "w") as file:
                yaml.dump({f"deployment-{service_name}": deployment_entry}, file)
        else:
            # Load existing values.yaml content
            with open(values_file_path, "r") as file:
                existing_data = yaml.safe_load(file) or {}

            # Update or add the deployment entry
            existing_data[f"deployment-{service_name}"] = existing_data.get(
                f"deployment-{service_name}", {}
            )
            existing_data[f"deployment-{service_name}"].update(deployment_entry)

            # Write the updated content back to the values.yaml file
            with open(values_file_path, "w") as file:
                yaml.dump(existing_data, file)

        # Prepare the Kubernetes Deployment template
        deployment_values = f"Values.deployment.{deployment_name}"
        template = self.get_template("deployment")
        template["metadata"]["name"] = f"{{ {deployment_values}.name }}"
        template["metadata"]["labels"] = f"{{ {deployment_values}.labels }}"
        template["spec"]["selector"][
            "matchLabels"
        ] = f"{{ {deployment_values}.labels }}"
        template["spec"]["template"]["metadata"][
            "labels"
        ] = f"{{ {deployment_values}.labels }}"
        template["spec"]["template"]["spec"]["containers"][0][
            "name"
        ] = f"{{ {deployment_values}.name }}"

        template["spec"]["template"]["spec"]["containers"][0][
            "command"
        ] = f"{{ {deployment_values}.command }}"
        template["spec"]["template"]["spec"]["containers"][0][
            "args"
        ] = f"{{ {deployment_values}.args }}"

        if deployment["user"] is not None:
            template["spec"]["template"]["spec"]["containers"][0]["securityContext"] = {
                "runAsUser": f"{{ {deployment_values}.user }}"
            }

        template["spec"]["template"]["spec"]["containers"][0][
            "env"
        ] = f"{{ {deployment_values}.env }}"

        if deployment["volumes"] is not None:
            template["spec"]["template"]["spec"]["containers"][0][
                "volumeMounts"
            ] = f"{{ {deployment_values}.volume_mounts }}"
            template["spec"]["template"]["spec"][
                "volumes"
            ] = f"{{ {deployment_values}.volumes }}"

        if deployment["ports"] is not None:
            template["spec"]["template"]["spec"]["containers"][0][
                "ports"
            ] = f"{{ {deployment_values}.ports }}"

        if deployment["workdir"] is not None:
            template["spec"]["template"]["spec"]["containers"][0][
                "workingDir"
            ] = f"{{ {deployment_values}.workdir }}"

        if deployment["liveness_probe"] is not None:
            template["spec"]["template"]["spec"]["containers"][0][
                "livenessProbe"
            ] = f"{{ {deployment_values}.liveness_probe }}"

        # Remove all None values from the template
        template = remove_none_values(template)

        # Convert the template to YAML string
        deployment_path = os.path.join(
            os.path.dirname(__file__),
            os.getenv("TARGET_PATH"),
            os.getenv("MANUAL_MANIFESTS_PATH"),
            "deployments",
        )
        os.makedirs(deployment_path, exist_ok=True)
        os.path.join(deployment_path, f"{deployment['name']}-deployment.yaml")
        self._save_yaml(
            template,
            os.path.join(deployment_path, f"{deployment['name']}-deployment.yaml"),
        )

    def build_service_yaml(self, service: dict) -> str:
        """Build a YAML file from the template and data."""

        # Check if the values.yaml file exists
        values_file_path = os.getenv("VALUES_FILE_PATH")
        service_name = to_kebab(service["name"])
        # Prepare the service entry
        service_entry = {
            "name": service_name,
            "labels": {service["labels"]},
            "port": service["port"],
            "target_port": service["target_port"],
            "protocol": service["protocol"],
            "type": service["type"],
        }
        # Prepare the service entry for values.yaml
        if not os.path.exists(values_file_path):
            # Create the values.yaml file if it doesn't exist
            with open(values_file_path, "w") as file:
                yaml.dump({f"service-{service_name}": service_entry}, file)
        else:
            # Load existing values.yaml content
            with open(values_file_path, "r") as file:
                existing_data = yaml.safe_load(file) or {}

            # Update or add the service entry
            existing_data[f"service-{service_name}"] = existing_data.get(
                f"service-{service_name}", {}
            )
            existing_data[f"service-{service_name}"].update(service_entry)

            # Write the updated content back to the values.yaml file
            with open(values_file_path, "w") as file:
                yaml.dump(existing_data, file)

        # Prepare the Kubernetes Service template
        service_values = f"Values.service.{service_name}"
        template = self.get_template("service")
        template["metadata"]["name"] = f"{{ {service_values}.name }}"
        template["metadata"]["labels"] = f"{{{service_values}.labels }}"
        template["spec"]["selector"] = f"{{ {service_values}.labels }}"
        template["spec"]["ports"][0]["port"] = f"{{ {service_values}.port }}"
        template["spec"]["ports"][0][
            "targetPort"
        ] = f"{{ {service_values}.target_port }}"
        template["spec"]["ports"][0]["protocol"] = f"{{ {service_values}.protocol }}"
        template["spec"]["ports"][0]["name"] = f"{{ {service_values}.name }}"
        template["spec"]["type"] = f"{{ {service_values}.type }}"
        # Remove all None values from the template
        template = remove_none_values(template)

        # Convert the template to YAML string
        service_path = os.path.join(
            os.path.dirname(__file__),
            os.getenv("TARGET_PATH"),
            os.getenv("MANUAL_MANIFESTS_PATH"),
            "services",
        )
        os.makedirs(service_path, exist_ok=True)
        os.path.join(service_path, f"{service['name']}-service.yaml")
        self._save_yaml(
            template, os.path.join(service_path, f"{service['name']}-service.yaml")
        )

    def build_stateful_set_yaml(self, stateful_set: dict) -> str:
        """Build a YAML file from the template and data."""

        # Check if the values.yaml file exists
        values_file_path = os.getenv("VALUES_FILE_PATH")
        stateful_set_name = to_kebab(stateful_set["name"])

        # Prepare the stateful set entry
        stateful_set_entry = {
            "name": stateful_set_name,
            "labels": {stateful_set["labels"]},
            "command": stateful_set["command"],
            "args": stateful_set["args"],
            "env": stateful_set["env"],
            "volumes": stateful_set["volumes"],
            "volume_mounts": stateful_set["volume_mounts"],
            "ports": stateful_set["ports"],
            "workdir": stateful_set["workdir"],
            "liveness_probe": stateful_set["liveness_probe"],
            "security_context": {"runAsUser": stateful_set["user"]},
        }

        # Prepare the stateful set entry for values.yaml
        if not os.path.exists(values_file_path):
            # Create the values.yaml file if it doesn't exist
            with open(values_file_path, "w") as file:
                yaml.dump(
                    {f"stateful-set-{stateful_set_name}": stateful_set_entry}, file
                )
        else:
            # Load existing values.yaml content
            with open(values_file_path, "r") as file:
                existing_data = yaml.safe_load(file) or {}

            # Update or add the stateful set entry
            existing_data[f"stateful-set-{stateful_set_name}"] = existing_data.get(
                f"stateful-set-{stateful_set_name}", {}
            )
            existing_data[f"stateful-set-{stateful_set_name}"].update(
                stateful_set_entry
            )

            # Write the updated content back to the values.yaml file
            with open(values_file_path, "w") as file:
                yaml.dump(existing_data, file)

        # Prepare the Kubernetes StatefulSet template
        stateful_set_values = f"Values.stateful-set.{stateful_set_name}"
        template = self.get_template("statefullset")
        template["metadata"]["name"] = f"{{ {stateful_set_values}.name }}"
        template["metadata"]["labels"] = f"{{{stateful_set_values}.labels }}"
        template["spec"]["selector"][
            "matchLabels"
        ] = f"{{ {stateful_set_values}.labels }}"

        template["spec"]["template"]["metadata"][
            "labels"
        ] = f"{{ {stateful_set_values}.labels }}"

        template["spec"]["template"]["spec"]["containers"][0][
            "name"
        ] = f"{{ {stateful_set_values}.name }}"

        template["spec"]["template"]["spec"]["containers"][0][
            "command"
        ] = f"{{ {stateful_set_values}.command }}"

        template["spec"]["template"]["spec"]["containers"][0][
            "args"
        ] = f"{{ {stateful_set_values}.args }}"

        if stateful_set["user"] is not None:
            template["spec"]["template"]["spec"]["containers"][0]["securityContext"] = {
                "runAsUser": f"{{ {stateful_set_values}.user }}"
            }
        template["spec"]["template"]["spec"]["containers"][0][
            "env"
        ] = f"{{ {stateful_set_values}.env }}"

        if stateful_set["volumes"] is not None:
            template["spec"]["template"]["spec"]["containers"][0][
                "volumeMounts"
            ] = f"{{ {stateful_set_values}.volume_mounts }}"

            template["spec"]["template"]["spec"][
                "volumes"
            ] = f"{{ {stateful_set_values}.volumes }}"

        if stateful_set["ports"] is not None:
            template["spec"]["template"]["spec"]["containers"][0][
                "ports"
            ] = f"{{ {stateful_set_values}.ports }}"
            
        if stateful_set["workdir"] is not None:
            template["spec"]["template"]["spec"]["containers"][0][
                "workingDir"
            ] = f"{{ {stateful_set_values}.workdir }}"
        if stateful_set["liveness_probe"] is not None:
            template["spec"]["template"]["spec"]["containers"][0][
                "livenessProbe"
            ] = f"{{ {stateful_set_values}.liveness_probe }}"
        # Remove all None values from the template
        template = remove_none_values(template)
        # Convert the template to YAML string
        stateful_set_path = os.path.join(
            os.path.dirname(__file__),
            os.getenv("TARGET_PATH"),
            os.getenv("MANUAL_MANIFESTS_PATH"),
            "stateful_sets",
        )
        os.makedirs(stateful_set_path, exist_ok=True)
        os.path.join(stateful_set_path, f"{stateful_set['name']}-stateful_set.yaml")
        self._save_yaml(
            template,
            os.path.join(
                stateful_set_path, f"{stateful_set['name']}-stateful_set.yaml"
            ),
        )
        # Save the YAML file
        print(f"StatefulSet YAML file saved to {stateful_set_path}")

    def build_pvc_yaml(self, pvc: dict) -> str:
        """Build a YAML file from the template and data."""

        # Check if the values.yaml file exists
        values_file_path = os.getenv("VALUES_FILE_PATH")
        pvc_name = to_kebab(pvc["name"])
        # Prepare the PVC entry
        pvc_entry = {
            "name": pvc_name,
            "labels": {pvc["labels"]},
            "storage_class": pvc["storage_class"],
            "access_modes": pvc["access_modes"],
            "resources": pvc["resources"],
        }
        # Prepare the PVC entry for values.yaml
        if not os.path.exists(values_file_path):
            # Create the values.yaml file if it doesn't exist
            with open(values_file_path, "w") as file:
                yaml.dump({f"pvc-{pvc_name}": pvc_entry}, file)
        else:
            # Load existing values.yaml content
            with open(values_file_path, "r") as file:
                existing_data = yaml.safe_load(file) or {}

            # Update or add the PVC entry
            existing_data[f"pvc-{pvc_name}"] = existing_data.get(f"pvc-{pvc_name}", {})
            existing_data[f"pvc-{pvc_name}"].update(pvc_entry)

            # Write the updated content back to the values.yaml file
            with open(values_file_path, "w") as file:
                yaml.dump(existing_data, file)

        # Prepare the Kubernetes PVC template
        pvc_values = f"Values.pvc.{pvc_name}"
        template = self.get_template("pvc")
        template["metadata"]["name"] = f"{{ {pvc_values}.name }}"
        template["metadata"]["labels"] = f"{{{pvc_values}.labels }}"
        template["spec"]["storageClassName"] = f"{{ {pvc_values}.storage_class }}"
        template["spec"]["accessModes"] = f"{{ {pvc_values}.access_modes }}"
        template["spec"]["resources"]["requests"][
            "storage"
        ] = f"{{ {pvc_values}.resources }}"

        # Remove all None values from the template
        template = remove_none_values(template)

        # Convert the template to YAML string
        pvc_path = os.path.join(
            os.path.dirname(__file__),
            os.getenv("TARGET_PATH"),
            os.getenv("MANUAL_MANIFESTS_PATH"),
            "pvcs",
        )
        os.makedirs(pvc_path, exist_ok=True)
        os.path.join(pvc_path, f"{pvc['name']}-pvc.yaml")
        self._save_yaml(template, os.path.join(pvc_path, f"{pvc['name']}-pvc.yaml"))

    def _save_yaml(self, template: dict, path: str) -> None:
        with open(path, "w") as file:
            yaml.dump(template, file)
        print(f"YAML file saved to {path}")
