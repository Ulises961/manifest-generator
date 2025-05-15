import logging
import os
from typing import Any, Dict, List, cast
from embeddings.embeddings_engine import EmbeddingsEngine
from utils.file_utils import load_file, remove_none_values
from caseutil import to_snake
import yaml


class ManifestBuilder:
    """Manifest builder for microservices."""

    def __init__(self) -> None:
        """Initialize the tree builder with the manifest templates."""
        self.logger = logging.getLogger(__name__)
        self._config_map_template = self._get_config_map_template()
        self.deployment_template = self._get_deployment_template()
        self._service_template = self._get_service_template()
        self._stateful_set_template = self._get_stateful_set_template()
        self._pvc_template = self._get_pvc_template()

        self.target_path = os.getenv("TARGET_PATH", "target")
        self.manifests_path = os.path.join(
            self.target_path, os.getenv("MANIFESTS_PATH", "manifests")
        )

        self.manual_manifests_path = os.path.join(
            self.manifests_path, os.getenv("MANUAL_MANIFESTS_PATH", "manual")
        )

        os.makedirs(os.path.dirname(self.target_path), exist_ok=True)

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
                "..",
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
                "..",
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
                "..",
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
                "..",
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
                "..",
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
                self.build_config_map_yaml(env)

    def build_secrets_yaml(self, secret: dict) -> None:
        """Build a YAML file from the template and data."""

        secrets_path = os.path.join(
            self.manual_manifests_path,
            "secrets.yaml",
        )

        secret.setdefault("templates", {secret["name"]: []})
        secret["templates"][secret["name"]].append(secrets_path)
        

        if not os.path.exists(secrets_path):
            # Prepare the Kubernetes Secret template
            template = self.get_template("config_map")
            template["kind"] = "Secret"
            template["metadata"]["name"] = "secrets"
            template["metadata"]["labels"] = {"environment": "production"}
            template["type"] = "Opaque"
            template["data"] = {secret["name"]: secret["value"]}

            # Remove all None values from the template
            template = remove_none_values(template)

            self._save_yaml(template, secrets_path)

            self.logger.info(f"Secret created: {secrets_path}")
        else:
            # Load existing secrets content
            with open(secrets_path, "r") as file:
                existing_data = yaml.safe_load(file) or {}

            # Update or add the secret entry
            existing_data.setdefault("data", {})
            existing_data["data"].update({secret["name"]: secret["value"]})



            # Write the updated content back to the secrets file
            self._save_yaml(existing_data, secrets_path)
            self.logger.info(f"Secret updated: {secrets_path}")

    def build_config_map_yaml(self, config_map: dict) -> None:
        """Build a YAML file from the template and data."""
        # Convert the template to YAML string
        config_map_path = os.path.join(
            self.manual_manifests_path,
            "config_map.yaml",
        )

        if not os.path.exists(config_map_path):
            # Prepare the Kubernetes ConfigMap template
            template = self.get_template("config_map")
            template["kind"] = "ConfigMap"
            template["metadata"]["name"] = f"config"
            template["metadata"]["labels"] = {"environment": "production"}
            template["data"] = {config_map["name"]: config_map["value"]}

            self._save_yaml(
                template,
                config_map_path,
            )

        else:
            # Load existing config map content
            with open(config_map_path, "r") as file:
                existing_data = yaml.safe_load(file) or {}

            # Update or add the config map entry
            existing_data.setdefault("data", {})
            existing_data["data"].update({config_map["name"]: config_map["value"]})

            # Write the updated content back to the config map file
            self._save_yaml(existing_data, config_map_path)

            config_map.setdefault("templates", {config_map["name"]: []})
            config_map["templates"][config_map["name"]].append(config_map_path)
                        
            self.logger.info(f"Config map updated: {config_map_path}")

    def build_deployment_yaml(self, deployment: dict) -> None:
        """Build a YAML file from the template and data."""

        deployment_entry: Dict[str, Any] = {
            "name": deployment["name"],
            "labels": deployment["labels"],
            "command": deployment["command"],
            "args": deployment.get("args"),
            "volumes": deployment.get("volumes"),
            "volume_mounts": deployment.get("volume_mounts"),
            "ports": {"containerPort": port for port in deployment.get("ports", [])},
            "workdir": deployment.get("workdir"),
            "liveness_probe": deployment.get("liveness_probe"),
            "user": deployment.get("user"),
        }

        deployment_entry = remove_none_values(deployment_entry)

        template = self.get_template("deployment")
        template["metadata"]["name"] = deployment_entry["name"]
        template["metadata"]["labels"] = deployment_entry["labels"]

        if "annotations" in deployment:
            template["metadata"]["annotations"] = deployment["annotations"]

        template["spec"]["selector"]["matchLabels"] = deployment_entry["labels"]
        template["spec"]["template"]["metadata"]["labels"] = deployment_entry["labels"]
        template["spec"]["template"]["spec"]["containers"][0]["name"] = (
            deployment_entry["name"]
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

        if "ports" in deployment_entry:
            template["spec"]["template"]["spec"]["containers"][0]["ports"] = deployment_entry["ports"]

        if "workdir" in deployment:
            template["spec"]["template"]["spec"]["containers"][0]["workingDir"] = deployment_entry["workdir"]

        if "liveness_probe" in deployment:
            template["spec"]["template"]["spec"]["containers"][0]["livenessProbe"] = deployment_entry["liveness_probe"]

        if "env" in deployment:
            env_vars = []
            for entry in deployment["env"]:
                if entry.get("key") == "password":
                    env_vars.append(
                        {
                            "name": entry["name"],
                            "valueFrom": {
                                "secretKeyRef": {
                                    "name": to_snake(entry["name"]),
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
                                    "name": to_snake(entry["name"]),
                                    "key": entry["name"],
                                }
                            },
                        }
                    )

            template["spec"]["template"]["spec"]["containers"][0]["env"] = env_vars

        # Remove all None values from the template
        template = remove_none_values(template)

        # Convert the template to YAML string
        deployment_path = os.path.join(
            self.manual_manifests_path,
            "deployments",
            f"{deployment['name']}-deployment.yaml"
        )

        deployment.setdefault("templates", {deployment["name"]:[]})
        deployment["templates"][deployment["name"]].append(deployment_path)        
        self._save_yaml(
            template,
            deployment_path
        )

    def build_stateful_set_yaml(self, stateful_set: dict) -> None:
        """Build a YAML file from the template and data."""

        # Prepare the stateful set entry
        stateful_set_entry = {
            "name": stateful_set["name"],
            "labels": stateful_set["labels"],
            "command": stateful_set["command"],
            "args": stateful_set.get("args", None),
            "volumes": stateful_set.get("volumes", None),
            "volume_mounts": stateful_set.get("volume_mounts", None),
            "ports": stateful_set.get("ports", None),
            "workdir": stateful_set.get("workdir", None),
            "liveness_probe": stateful_set.get("liveness_probe", None),
            "user": stateful_set.get("user", None),
        }

        stateful_set_entry = remove_none_values(stateful_set_entry)

        template = self.get_template("statefullset")
        template["metadata"]["name"] = stateful_set_entry["name"]
        template["metadata"]["labels"] = stateful_set_entry["labels"]

        if "annotations" in stateful_set:
            template["metadata"]["annotations"] = stateful_set["annotations"]
        template["spec"]["selector"]["matchLabels"] = stateful_set_entry["labels"]

        template["spec"]["template"]["metadata"]["labels"] = stateful_set_entry["labels"]

        template["spec"]["template"]["spec"]["containers"][0]["name"] = stateful_set_entry["name"]
        template["spec"]["template"]["spec"]["containers"][0]["command"] = stateful_set_entry["command"]

        if "args" in stateful_set:
            template["spec"]["template"]["spec"]["containers"][0]["args"] = stateful_set_entry["args"]

        if "user" in stateful_set:
            template["spec"]["template"]["spec"]["containers"][0]["securityContext"] = {
                "runAsUser": stateful_set_entry["user"]
            }

        if "volumes" in stateful_set:
            template["spec"]["template"]["spec"]["containers"][0]["volumeMounts"] = stateful_set_entry[
                "volume_mounts"
            ]

            template["spec"]["template"]["spec"]["volumes"] = stateful_set_entry[
                "volumes"
            ]

        if "ports" in stateful_set:
            template["spec"]["template"]["spec"]["containers"][0]["ports"] = stateful_set_entry[
                "ports"
            ]

        if "workdir" in stateful_set:
            template["spec"]["template"]["spec"]["containers"][0]["workingDir"] = stateful_set_entry["workdir"]

        if "liveness_probe" in stateful_set:
            template["spec"]["template"]["spec"]["containers"][0]["livenessProbe"] =  stateful_set_entry["liveness_probe"]

        if "env" in stateful_set:
            env_vars = []
            for entry in stateful_set["env"]:
                if entry.get("key") == "password":
                    env_vars.append(
                        {
                            "name": entry["name"],
                            "valueFrom": {
                                "secretKeyRef": {
                                    "name": to_snake(entry["name"]),
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
                                    "name": to_snake(entry["name"]),
                                    "key": entry["name"],
                                }
                            },
                        }
                    )

            template["spec"]["template"]["spec"]["containers"][0]["env"] = env_vars
        # Remove all None values from the template
        template = remove_none_values(template)
        # Convert the template to YAML string
        stateful_set_path = os.path.join(
            self.manual_manifests_path,
            "stateful_sets",
            f"{stateful_set['name']}-stateful_set.yaml"
        )

        stateful_set.setdefault("templates", {stateful_set["name"]: []})
        stateful_set["templates"][stateful_set["name"]].append(stateful_set_path)

        self._save_yaml(
            template,
            stateful_set_path
        )

    def build_service_yaml(self, service: dict) -> None:
        """Build a YAML file from the template and data."""

        port_mappings = self._get_port_mappings(service)

        # Prepare the service entry
        service_entry = {
            "name": service["name"],
            "labels": service["labels"],
            "ports": port_mappings,
            "type": service.get("type", "ClusterIP"),
        }

        service_entry = remove_none_values(service_entry)


        template = self.get_template("service")
        template["metadata"]["name"] = service_entry["name"]
        template["metadata"]["labels"] = service_entry["labels"]

        template["spec"]["selector"] = service_entry["labels"]

        template["spec"]["ports"] = service_entry["ports"]

        template["spec"]["type"] = service_entry["type"]
        # Remove all None values from the template
        template = remove_none_values(template)

        # Convert the template to YAML string
        service_path = os.path.join(
            self.manual_manifests_path,
            "services",
            f"{service['name']}-service.yaml"
        )

        service.setdefault("templates", {service["name"]: []})
        service["templates"][service["name"]].append(service_path)

        self._save_yaml(
            template, 
            service_path
        )

    def build_pvc_yaml(self, pvc: dict) -> None:
        """Build a YAML file from the template and data."""
        # Prepare the PVC entry
        pvc_entry = {
            "name": pvc["name"],
            "labels": pvc.get("labels", []),
            "storage_class": pvc.get("storage_class", None),
            "access_modes": pvc.get("access_modes", None),
            "resources": pvc.get("resources", None),
        }

        # Remove all None values from the PVC entry
        pvc_entry = remove_none_values(pvc_entry)

        template = self.get_template("pvc")
        template["metadata"]["name"] = pvc_entry["name"]
        template["metadata"]["labels"] = pvc_entry["labels"]

        template["spec"]["storageClassName"] =pvc_entry["storage_class"]
        template["spec"]["accessModes"] = pvc_entry["access_modes"]
        template["spec"]["resources"]["requests"]["storage"] = pvc_entry["resources"]
        # Remove all None values from the template
        template = remove_none_values(template)

        # Convert the template to YAML string
        pvc_path = os.path.join(
            self.manual_manifests_path,
            "pvcs",
            f"{pvc['name']}-pvc.yaml")

        pvc.setdefault("templates", {pvc["name"]: []})
        pvc["templates"][pvc["name"]].append(pvc_path)

        self._save_yaml(template, pvc_path)

    def _get_port_mappings(self, service_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate port mappings between service ports and container ports.

        Args:
            service_info: Service information from ontology
            container_ports: Container ports detected from Dockerfile (optional)

        Returns:
            List of port mapping dictionaries
        """

        container_ports = service_info.get("ports", [])
        service_ports = service_info.get("service-ports", [])
        protocol = service_info.get("protocol", "TCP")

        # If we have different numbers of ports, we need to be careful
        if len(service_ports) != len(container_ports):
            # Special case: Service ports are a subset of container ports
            if all(port in container_ports for port in service_ports):
                return [
                    {
                        "port": sport,
                        "targetPort": sport,
                        "name": f"port-{sport}",
                        "protocol": protocol,
                    }
                    for sport in service_ports
                ]
            # For mismatched ports, use common port conventions
            return self._map_ports_by_convention(
                service_ports, container_ports, protocol
            )

        # Simple 1:1 mapping when port counts match
        return [
            {
                "port": sport,
                "targetPort": cport,
                "name": self._get_port_name(sport),
                "protocol": protocol,
            }
            for sport, cport in zip(service_ports, container_ports)
        ]

    def _map_ports_by_convention(
        self, service_ports: List[int], container_ports: List[int], protocol: str
    ) -> List[Dict[str, Any]]:
        """Map ports using common conventions."""
        mappings = []

        # Common port conventions
        conventions = {
            80: [8080, 3000, 4200, 5000, 8000],
            443: [8443, 8080, 3000],
        }

        # Try to map each service port
        for sport in service_ports:
            # Direct match
            if sport in container_ports:
                mappings.append(
                    {
                        "port": sport,
                        "targetPort": sport,
                        "name": self._get_port_name(sport),
                        "protocol": protocol,
                    }
                )
                continue

            # Look for conventional mappings
            mapped = False
            for standard, alternatives in conventions.items():
                if sport == standard and any(
                    alternative in container_ports for alternative in alternatives
                ):
                    # Find the first matching alternative
                    for alternative in alternatives:
                        if alternative in container_ports:
                            mappings.append(
                                {
                                    "port": sport,
                                    "targetPort": alternative,
                                    "name": self._get_port_name(sport),
                                    "protocol": protocol,
                                }
                            )
                            mapped = True
                            break
                    if mapped:
                        break

            # No mapping found, use the service port directly
            if not mapped:
                mappings.append(
                    {
                        "port": sport,
                        "targetPort": sport,
                        "name": f"port-{sport}",
                        "protocol": protocol,
                    }
                )

        return mappings

    def _get_port_name(self, port):
        """Get a canonical name for well-known ports."""
        port_names = {80: "http", 443: "https"}
        return port_names.get(port, f"port-{port}")

   
    def _save_yaml(self, template: dict, path: str) -> None:
        """Save the template as a YAML file."""

        # Create a custom dumper that handles Helm templates correctly
        class NoAliasDumper(yaml.SafeDumper):
            def ignore_aliases(self, _):
                return True


        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, "w") as file:
            yaml.dump(
                template,
                file,
                Dumper=NoAliasDumper,
                sort_keys=False,
                default_flow_style=False,
            )
        print(f"YAML file saved to {path}")
