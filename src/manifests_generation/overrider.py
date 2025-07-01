import logging
import traceback
from typing import Any, Dict, List, Optional, cast
import yaml

from validation.overrides_validator import OverridesValidator


class Overrider:
    """
    A class to override the default behavior of a class.
    """

    def __init__(self, config_path: str):
        """
        Initialize the Overrider with a validator for configuration overrides.

        :param overrides_validator: An instance of a validator to validate configuration overrides.
        """
        self.overrides_validator = OverridesValidator()
        self.logger = logging.getLogger(__name__)
        self.override_config = self.get_config(config_path)

    def get_config(self, config_path: str) -> Optional[Dict[str, Any]]:
        try:
            with open(config_path, "r") as file:
                # Load the configuration file
                self.logger.info(f"Loading configuration overrides from {config_path}")
                config = yaml.safe_load(file)

                # Validate the configuration file
                if self.overrides_validator.validate(config):
                    return cast(Dict[str, Any], config)
                else:
                    self.logger.error(
                        f"Configuration overrides validation failed for {config_path}. Please check the file format and content. Ignoring overrides."
                    )
                    return None
        except FileNotFoundError:
            self.logger.error(
                f"Configuration file not found: {config_path}. Ignoring overrides."
            )
            return None

    def apply_overrides(self, microservice: Dict[str, Any]) -> Dict[str, Any]:
        """Apply configuration overrides from a YAML file to microservices."""

        if self.override_config is not None:

            # Apply global environment variables
            global_env = self.override_config.get("global", {}).get(
                "environment", []
            )

            service_name = microservice["name"]

            # Skip if service isn't in the configuration
            if service_name not in self.override_config["services"]:
                return microservice

            service_config = self.override_config["services"][service_name]

            # Apply basic service properties
            if "replicas" in service_config:
                if "spec" not in microservice:
                    microservice["spec"] = {}
                microservice["spec"]["replicas"] = service_config["replicas"]

            if "image" in service_config:
                self._ensure_container_spec(microservice)
                microservice["spec"]["template"]["spec"]["containers"][0][
                    "image"
                ] = service_config["image"]

            # Apply environment variables
            self._apply_environment_variables(
                microservice, service_config.get("environment", []), global_env
            )

            # Apply port configurations
            if "ports" in service_config:
                self._apply_port_config(microservice, service_config["ports"])

            # Apply volume mounts
            if "volumes" in service_config:
                self._apply_volume_mounts(microservice, service_config["volumes"])

            # Apply resource constraints
            if "resources" in service_config:
                self._apply_resource_constraints(
                    microservice, service_config["resources"]
                )

            # Apply probes
            if "livenessProbe" in service_config:
                self._apply_probe(
                    microservice, service_config["livenessProbe"], "livenessProbe"
                )

            if "readinessProbe" in service_config:
                self._apply_probe(
                    microservice, service_config["readinessProbe"], "readinessProbe"
                )

            # Apply lifecycle hooks
            if "lifecycle" in service_config:
                self._apply_lifecycle(microservice, service_config["lifecycle"])

                # Apply affinity rules
                if "affinity" in service_config:
                    self._apply_affinity(microservice, service_config["affinity"])

                # Apply volume claims
                if "volumeClaims" in service_config:
                    self._apply_volume_claims(
                        microservice, service_config["volumeClaims"]
                    )

                # Apply secret references
                if "secrets" in service_config:
                    self._apply_secrets(microservice, service_config["secrets"])

                # Apply metadata (annotations and labels)
                if "metadata" in service_config:
                    self._apply_metadata(microservice, service_config["metadata"])

            # Process dependencies and generate dependency graph
            if any(
                "dependencies"
                in self.override_config.get("services", {}).get(service_name, {})
                for service_name in self.override_config.get("services", {})
            ):
                self._process_dependencies(
                    microservice, self.override_config["services"]
                )

        return microservice


    def _ensure_container_spec(self, service: Dict[str, Any]):
        """Ensure the container spec structure exists in the service."""
        if "spec" not in service:
            service["spec"] = {}
        if "template" not in service["spec"]:
            service["spec"]["template"] = {"spec": {}}
        if "spec" not in service["spec"]["template"]:
            service["spec"]["template"]["spec"] = {}
        if "containers" not in service["spec"]["template"]["spec"]:
            service["spec"]["template"]["spec"]["containers"] = [{}]
        if not service["spec"]["template"]["spec"]["containers"]:
            service["spec"]["template"]["spec"]["containers"] = [{}]

    def _apply_environment_variables(
        self,
        service: Dict[str, Any],
        service_env: List[Dict[str, str]],
        global_env: List[Dict[str, str]],
    ):
        """Apply environment variables to a service."""
        if not (service_env or global_env):
            return

        self._ensure_container_spec(service)
        container = service["spec"]["template"]["spec"]["containers"][0]

        # Initialize env if not exists
        if "env" not in container:
            container["env"] = []

        # Add global environment variables
        for env in global_env:
            # Check if this env var already exists
            found = False
            for i, existing_env in enumerate(container["env"]):
                if existing_env["name"] == env["name"]:
                    container["env"][i]["value"] = env["value"]
                    found = True
                    break

            if not found:
                container["env"].append({"name": env["name"], "value": env["value"]})

        # Add service-specific environment variables (overrides globals)
        for env in service_env:
            found = False
            for i, existing_env in enumerate(container["env"]):
                if existing_env["name"] == env["name"]:
                    container["env"][i]["value"] = env["value"]
                    found = True
                    break

            if not found:
                container["env"].append({"name": env["name"], "value": env["value"]})

    def _apply_port_config(
        self, service: Dict[str, Any], port_configs: List[Dict[str, Any]]
    ):
        """Apply port configurations to a service."""
        self._ensure_container_spec(service)
        container = service["spec"]["template"]["spec"]["containers"][0]

        # Initialize ports if not exists
        if "ports" not in container:
            container["ports"] = []

        # Update or add port configurations
        for port_config in port_configs:
            container_port = port_config["containerPort"]

            # Check if this port already exists
            found = False
            for i, existing_port in enumerate(container["ports"]):
                if existing_port.get("containerPort") == container_port:
                    # Update existing port with overridden values
                    for key, value in port_config.items():
                        container["ports"][i][key] = value
                    found = True
                    break

            if not found:
                # Add new port
                new_port = {"containerPort": container_port}
                if "hostPort" in port_config:
                    new_port["hostPort"] = port_config["hostPort"]
                if "protocol" in port_config:
                    new_port["protocol"] = port_config["protocol"]
                container["ports"].append(new_port)

    def _apply_volume_mounts(
        self, service: Dict[str, Any], volume_configs: List[Dict[str, Any]]
    ):
        """Apply volume mount configurations to a service."""
        self._ensure_container_spec(service)
        container = service["spec"]["template"]["spec"]["containers"][0]
        pod_spec = service["spec"]["template"]["spec"]

        # Initialize volumeMounts if not exists
        if "volumeMounts" not in container:
            container["volumeMounts"] = []

        # Initialize volumes if not exists
        if "volumes" not in pod_spec:
            pod_spec["volumes"] = []

        # Process each volume mount
        for volume_config in volume_configs:
            volume_name = volume_config["name"]

            # Add or update volumeMount in container
            mount_found = False
            for i, existing_mount in enumerate(container["volumeMounts"]):
                if existing_mount["name"] == volume_name:
                    container["volumeMounts"][i]["mountPath"] = volume_config[
                        "mountPath"
                    ]
                    if "subPath" in volume_config:
                        container["volumeMounts"][i]["subPath"] = volume_config[
                            "subPath"
                        ]
                    if "readOnly" in volume_config:
                        container["volumeMounts"][i]["readOnly"] = volume_config[
                            "readOnly"
                        ]
                    mount_found = True
                    break

            if not mount_found:
                new_mount = {
                    "name": volume_name,
                    "mountPath": volume_config["mountPath"],
                }
                if "subPath" in volume_config:
                    new_mount["subPath"] = volume_config["subPath"]
                if "readOnly" in volume_config:
                    new_mount["readOnly"] = volume_config["readOnly"]
                container["volumeMounts"].append(new_mount)

            # Add volume in pod spec if not exists
            volume_found = False
            for existing_volume in pod_spec["volumes"]:
                if existing_volume["name"] == volume_name:
                    volume_found = True
                    break

            if not volume_found:
                # Create an emptyDir volume by default, can be overridden by volumeClaims
                pod_spec["volumes"].append({"name": volume_name, "emptyDir": {}})

    def _apply_resource_constraints(
        self, service: Dict[str, Any], resources: Dict[str, Any]
    ):
        """Apply resource constraints to a service."""
        self._ensure_container_spec(service)
        container = service["spec"]["template"]["spec"]["containers"][0]

        # Initialize resources if not exists
        if "resources" not in container:
            container["resources"] = {}

        # Apply limits
        if "limits" in resources:
            if "limits" not in container["resources"]:
                container["resources"]["limits"] = {}

            for key, value in resources["limits"].items():
                container["resources"]["limits"][key] = value

        # Apply requests
        if "requests" in resources:
            if "requests" not in container["resources"]:
                container["resources"]["requests"] = {}

            for key, value in resources["requests"].items():
                container["resources"]["requests"][key] = value

    def _apply_probe(
        self, service: Dict[str, Any], probe_config: Dict[str, Any], probe_type: str
    ):
        """Apply health probe configuration to a service."""
        self._ensure_container_spec(service)
        container = service["spec"]["template"]["spec"]["containers"][0]

        # Create the probe configuration
        probe = {}

        # Apply httpGet if specified
        if "httpGet" in probe_config:
            probe["httpGet"] = {
                "path": probe_config["httpGet"]["path"],
                "port": probe_config["httpGet"]["port"],
            }

        # Apply timing parameters
        if "initialDelaySeconds" in probe_config:
            probe["initialDelaySeconds"] = probe_config["initialDelaySeconds"]
        if "timeoutSeconds" in probe_config:
            probe["timeoutSeconds"] = probe_config["timeoutSeconds"]

        # Set the probe
        container[probe_type] = probe

    def _apply_lifecycle(
        self, service: Dict[str, Any], lifecycle_config: Dict[str, Any]
    ):
        """Apply lifecycle hooks to a service."""
        self._ensure_container_spec(service)
        container = service["spec"]["template"]["spec"]["containers"][0]

        # Initialize lifecycle if not exists
        container["lifecycle"] = {}

        # Apply postStart hook if specified
        if "postStart" in lifecycle_config:
            container["lifecycle"]["postStart"] = lifecycle_config["postStart"]

        # Apply preStop hook if specified (not in original schema but common)
        if "preStop" in lifecycle_config:
            container["lifecycle"]["preStop"] = lifecycle_config["preStop"]

    def _apply_affinity(self, service: Dict[str, Any], affinity_config: Dict[str, Any]):
        """Apply affinity rules to a service."""
        self._ensure_container_spec(service)
        pod_spec = service["spec"]["template"]["spec"]

        # Set affinity directly
        pod_spec["affinity"] = affinity_config

    def _apply_volume_claims(
        self, service: Dict[str, Any], volume_claims: List[Dict[str, Any]]
    ):
        """Apply persistent volume claims for a service."""
        service_name = service["name"]

        service["persistent_volumes"] = volume_claims
        # Update pod volumes to use PVCs
        self._ensure_container_spec(service)
        pod_spec = service["spec"]["template"]["spec"]

        # Initialize volumes if not exists
        if "volumes" not in pod_spec:
            pod_spec["volumes"] = []

        # Update volumes to use PVC
        for claim in volume_claims:
            volume_name = claim["name"]

            # Check if volume exists
            volume_found = False
            for i, volume in enumerate(pod_spec["volumes"]):
                if volume["name"] == volume_name:
                    # Replace with PVC reference
                    pod_spec["volumes"][i] = {
                        "name": volume_name,
                        "persistentVolumeClaim": {
                            "claimName": f"{volume_name}"
                        },
                    }
                    volume_found = True
                    break

            if not volume_found:
                # Add new volume with PVC
                pod_spec["volumes"].append(
                    {
                        "name": volume_name,
                        "persistentVolumeClaim": {
                            "claimName": f"{volume_name}"
                        },
                    }
                )

    def _apply_secrets(self, service: Dict[str, Any], secrets: List[Dict[str, Any]]):
        """Apply secret references to a service."""
        self._ensure_container_spec(service)
        container = service["spec"]["template"]["spec"]["containers"][0]

        # Initialize env if not exists
        if "env" not in container:
            container["env"] = []

        # Add secret references
        for secret in secrets:
            secret_name = secret["name"]
            key = secret.get("key", secret_name)

            # Add as environment variable
            new_env = {
                "name": secret_name,
                "valueFrom": {
                    "secretKeyRef": {
                        "name": "app-secrets",  # Default secret name, can be customized
                        "key": key,
                    }
                },
            }

            if "optional" in secret:
                new_env["valueFrom"]["secretKeyRef"]["optional"] = secret["optional"]

            # Check if already exists
            found = False
            for i, env in enumerate(container["env"]):
                if env["name"] == secret_name:
                    container["env"][i] = new_env
                    found = True
                    break

            if not found:
                container["env"].append(new_env)

    def _apply_metadata(self, service: Dict[str, Any], metadata: Dict[str, Any]):
        """Apply metadata (annotations and labels) to a service."""
        # Ensure metadata exists
        if "metadata" not in service:
            service["metadata"] = {}

        # Apply annotations
        if "annotations" in metadata:
            if "annotations" not in service["metadata"]:
                service["metadata"]["annotations"] = {}

            for key, value in metadata["annotations"].items():
                service["metadata"]["annotations"][key] = value

        # Apply labels
        if "labels" in metadata:
            if "labels" not in service["metadata"]:
                service["metadata"]["labels"] = {}

            for key, value in metadata["labels"].items():
                service["metadata"]["labels"][key] = value

        # Also apply to pod template if it exists
        if "spec" in service and "template" in service["spec"]:
            template = service["spec"]["template"]

            if "metadata" not in template:
                template["metadata"] = {}

            # Apply annotations to pod template
            if "annotations" in metadata:
                if "annotations" not in template["metadata"]:
                    template["metadata"]["annotations"] = {}

                for key, value in metadata["annotations"].items():
                    template["metadata"]["annotations"][key] = value

            # Apply labels to pod template
            if "labels" in metadata:
                if "labels" not in template["metadata"]:
                    template["metadata"]["labels"] = {}

                for key, value in metadata["labels"].items():
                    template["metadata"]["labels"][key] = value

    def _process_dependencies(
        self, service: Dict[str, Any], service_configs: Dict[str, Dict[str, Any]]
    ):
        """Process service dependencies and apply appropriate configurations."""
        # Build dependency graph
        dependency_graph: Dict[str,Any] = {}

        for service_name, config in service_configs.items():
            if "dependencies" in config:
                if service_name not in dependency_graph:
                    dependency_graph[service_name] = []

                for dep in config["dependencies"]:
                    dependency_graph[service_name].append(
                        {
                            "service": dep["service"],
                            "required": dep.get("required", True),
                            "port": dep.get("port"),
                        }
                    )

        # Add init containers for required dependencies
        for service_name, deps in dependency_graph.items():

            self._ensure_container_spec(service)
            pod_spec = service["spec"]["template"]["spec"]

            # Initialize init containers
            if "initContainers" not in pod_spec:
                pod_spec["initContainers"] = []

            # Add init container for each required dependency
            for dep in deps:
                if dep.get("required", True):
                    dep_name = dep["service"]
                    port = dep.get("port", 80)  # Default to port 80 if not specified

                    init_container = {
                        "name": f"wait-for-{dep_name}",
                        "image": "busybox",
                        "command": [
                            "sh",
                            "-c",
                            f"until nslookup {dep_name}; do echo waiting for {dep_name}; sleep 2; done;",
                        ],
                    }

                    # Check if this init container already exists
                    found = False
                    for container in pod_spec["initContainers"]:
                        if container["name"] == f"wait-for-{dep_name}":
                            found = True
                            break

                    if not found:
                        pod_spec["initContainers"].append(init_container)

                # Add environment variable for the dependency
                if dep.get("port"):
                    dep_name = dep["service"]
                    port = dep["port"]
                    env_var_name = f"{dep_name.upper()}_SERVICE_ADDR"

                    # Ensure container has env section
                    container = service["spec"]["template"]["spec"]["containers"][0]
                    if "env" not in container:
                        container["env"] = []

                    # Check if already exists
                    found = False
                    for i, env in enumerate(container["env"]):
                        if env["name"] == env_var_name:
                            container["env"][i]["value"] = f"{dep_name}:{port}"
                            found = True
                            break

                    if not found:
                        container["env"].append(
                            {"name": env_var_name, "value": f"{dep_name}:{port}"}
                        )
