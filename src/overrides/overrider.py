from enum import Enum
import logging
import traceback
from typing import Any, Dict, List, Optional, Tuple, cast
import yaml

from manifests_generation.pvc_builder import PVCBuilder
from overrides.overrides_validator import OverridesValidator


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
            self.logger.exception(
                f"Configuration file not found: {config_path}. Ignoring overrides.",
                exc_info=True,
                stack_info=True,
            )
            return None

    def apply_configuration_overrides(self, microservice: Dict[str, Any], microservice_name: str) -> Dict[str, Any]:
        """Apply configuration overrides from a YAML file to microservices."""

        if self.override_config is not None:
            # Apply global environment variables

            # Skip if service isn't in the configuration
            if microservice_name not in self.override_config["services"]:
                self.logger.warning(
                    f"Service {microservice_name} not found in overrides configuration. Skipping overrides."
                )
                return microservice

            service_config = self.override_config["services"][microservice_name]

            self.logger.debug(
                f"Applying overrides for service {microservice_name}: {service_config}"
            )
            
            manifests = microservice.get("manifests", {})
            
            if manifests.get("deployment", None) is not None:
                self.override_deployment(microservice, service_config)
            
            if manifests.get("stateful_set", None) is not None:
                self.override_deployment(microservice, service_config)

            if manifests.get("service", None) is not None:
                self.override_service(
                    microservice, service_config
                )
            if manifests.get("pvc", None) is not None:
                self.override_pvc(microservice, service_config)

               
        return microservice

    def override_deployment(self, service: Dict[str, Any], service_config: Dict[str, Any]):
        if self.override_config is not None:
            # Apply global environment variables
            manifests = service.get("manifests",{})
            _, template = manifests.get("deployment", (None,None))
            
            global_env = self.override_config.get("global", {}).get("environment", [])

            # Apply basic service properties
            if "replicas" in service_config:
                if "spec" not in template:
                    template["spec"] = {}
                template["spec"]["replicas"] = service_config["replicas"]

            if "image" in service_config:
                template = self._ensure_container_spec(template)
                template["spec"]["template"]["spec"]["containers"][0]["image"] = (
                    service_config["image"]
                )

            # Apply environment variables
            self._apply_environment_variables(
                template, service_config.get("environment", []), global_env
            )

            # Apply port configurations
            if "ports" in service_config:
                self._apply_port_config(template, service_config["ports"])

            # Apply volume mounts
            if "volumes" in service_config:
                # Use microservice to attach a brand new pvc if needed
                self._apply_volume_mounts(service, service_config["volumes"])

            # Apply resource constraints
            if "resources" in service_config:
                self._apply_resource_constraints(
                    template, service_config["resources"]
                )

            # Apply probes
            if "livenessProbe" in service_config:
                self._apply_probe(
                    template, service_config["livenessProbe"], "livenessProbe"
                )

            if "readinessProbe" in service_config:
                self._apply_probe(
                    template, service_config["readinessProbe"], "readinessProbe"
                )

            # Apply lifecycle hooks
            if "lifecycle" in service_config:
                self._apply_lifecycle(template, service_config["lifecycle"])

            # Apply affinity rules
            if "affinity" in service_config:
                self._apply_affinity(template, service_config["affinity"])

                # Apply volume claims
            if "volumeClaims" in service_config:
                self._apply_volume_claims(
                    template, service_config["volumeClaims"]
                )

            # Apply secret references
            if "secrets" in service_config:
                self._apply_secrets(template, service_config["secrets"])

            # Apply metadata (annotations and labels)
            if "metadata" in service_config:
                    self._apply_metadata(template, service_config["metadata"])

            # Process dependencies and generate dependency graph
            if any(
                "dependencies"
                in self.override_config.get("services", {}).get(microservice_name, {})
                for microservice_name in self.override_config.get("services", {})
            ):
                self._process_dependencies(
                    template, self.override_config["services"]
                )
        return service
    def get_microservice_overrides(self, microservice_name: str) -> Dict[str,Any]:
        """Get the overrides applied to a specific template."""
        if not self.override_config:
            self.logger.warning(
                "No override configuration loaded. Returning empty overrides."
            )
            return {}
        
        if (config := self.override_config["services"].get(microservice_name, None)) is None:
            self.logger.warning(
                f"No overrides found for service {microservice_name}. Returning empty overrides."
            )
            return {}

        self.logger.info(
                f"Returning overrides for service {microservice_name}: {config}"
            )

        return cast(Dict[str, Any], config)
    
    
    def _ensure_container_spec(self, service: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure the container spec structure exists in the service."""
        
        if "spec" not in service:
            service["spec"] = {}
        if "template" not in service["spec"]:
            service["spec"]["template"] = {}
        if "spec" not in service["spec"]["template"]:
            service["spec"]["template"]["spec"] = {}
        if "containers" not in service["spec"]["template"]["spec"]:
            service["spec"]["template"]["spec"]["containers"] = [{}]
        return service
    
    def _apply_environment_variables(
        self,
        service: Dict[str, Any],
        service_env: List[Dict[str, str]],
        global_env: List[Dict[str, str]],
    ):
        """Apply environment variables to a service."""
        if not (service_env or global_env):
            return

        service = service = self._ensure_container_spec(service)
        container = service["spec"]["template"]["spec"]["containers"][0]

        # Initialize env if not exists
        container.setdefault("env", [])

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
        service = service = self._ensure_container_spec(service)
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
        self, microservice: Dict[str, Any], volume_configs: List[Dict[str, Any]]
    ):
        """Apply volume mount configurations to a service."""

        # Retrieve the manifest before starting
        manifests = microservice.get("manifests", {})
        _, template = manifests.get("deployment", (None, None))
        if template is not None and self.override_config is not None:
            template = self._ensure_container_spec(template)
            container = template["spec"]["template"]["spec"]["containers"][0]
            pod_spec = template["spec"]["template"]["spec"]

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
                    # If volume name present as volumeClaim in override config generate a new volume claim and associate it
                    
                    if volume_name in self.override_config.get("volumeClaims", {}):
                        claim = self.override_config["volumeClaims"][volume_name]
                        pvc_builder = PVCBuilder()
                        pvc = pvc_builder.build_template({
                            "name": microservice["name"],
                            "labels": microservice.get("labels", []),
                            "storage_class": claim.get("storageClass", None),
                            "access_modes": claim.get("accessModes", ["ReadWriteOnce"]),
                            "resources": claim.get("resources", {"requests": {"storage": "1Gi"}})
                        })

                        pod_spec["volumes"].append(
                            {
                                "name": volume_name,
                                "persistentVolumeClaim": {"claimName": claim["name"]},
                            }
                        )
                    
                    
                    # Create an emptyDir volume by default
                    pod_spec["volumes"].append({"name": volume_name, "emptyDir": {}})

                 
            

    def _apply_resource_constraints(
        self, service: Dict[str, Any], resources: Dict[str, Any]
    ):
        """Apply resource constraints to a service."""
        service = service = self._ensure_container_spec(service)
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
        service = service = self._ensure_container_spec(service)
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
        service = self._ensure_container_spec(service)
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
        service = self._ensure_container_spec(service)
        pod_spec = service["spec"]["template"]["spec"]

        # Set affinity directly
        pod_spec["affinity"] = affinity_config

    def _apply_volume_claims(
        self, service: Dict[str, Any], volume_claims: List[Dict[str, Any]]
    ):
        """Apply persistent volume claims for a service."""
        microservice_name = service["name"]

        service["persistent_volumes"] = volume_claims
        # Update pod volumes to use PVCs
        service = self._ensure_container_spec(service)
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
                        "persistentVolumeClaim": {"claimName": f"{volume_name}"},
                    }
                    volume_found = True
                    break

            if not volume_found:
                # Add new volume with PVC
                pod_spec["volumes"].append(
                    {
                        "name": volume_name,
                        "persistentVolumeClaim": {"claimName": f"{volume_name}"},
                    }
                )

    def _apply_secrets(self, service: Dict[str, Any], secrets: List[Dict[str, Any]]):
        """Apply secret references to a service."""
        service = self._ensure_container_spec(service)
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
        dependency_graph: Dict[str, Any] = {}

        for microservice_name, config in service_configs.items():
            if "dependencies" in config:
                if microservice_name not in dependency_graph:
                    dependency_graph[microservice_name] = []

                for dep in config["dependencies"]:
                    dependency_graph[microservice_name].append(
                        {
                            "service": dep["service"],
                            "required": dep.get("required", True),
                            "port": dep.get("port"),
                        }
                    )

        # Add init containers for required dependencies
        for microservice_name, deps in dependency_graph.items():

            service = self._ensure_container_spec(service)
            print(service)
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

    def override_service(self, template: Dict[str, Any], service_config: Dict[str, Any]):
        """Apply service-specific overrides."""
        
        # Ensure ports are defined in the service template
        if "spec" not in template:
            template["spec"] = {}
        # Clean slate   
        template["spec"].setdefault("ports", [])

        # Apply port configurations
        if "ports" in service_config:
            for port in service_config.get("ports", []):
                new_port = {
                    "name": port.get("name", f"{port['port']}"),
                    "targetPort": port["containerPort"],
                    "port": port.get("hostPort", port["containerPort"]),
                    "protocol": port.get("protocol", "TCP"),
                }
                template["spec"]["ports"].append(new_port)

    def override_pvc(self, template: Dict[str,Any], service_config: Dict[str, Any]):
        # Find the claim to override in the config
        for claim in service_config.get("volumeClaims", []):
            claim_name = claim["name"]
            # Check if the PVC already exists in the template
            if "spec" not in template:
                template["spec"] = {}
            if "volumeClaimTemplates" not in template["spec"]:
                template["spec"]["volumeClaimTemplates"] = []

            # Check if this PVC already exists
            found = False
            for existing_claim in template["spec"]["volumeClaimTemplates"]:
                if existing_claim["metadata"]["name"] == claim_name:
                    found = True
                    # Update existing claim with new properties
                    existing_claim["spec"]["accessModes"] = claim.get("accessModes", ["ReadWriteOnce"])
                    existing_claim["spec"]["resources"] = {
                        "requests": {
                            "storage": claim.get("storage", "1Gi")
                        }
                    }
                    if "storageClassName" in claim:
                        existing_claim["spec"]["storageClassName"] = claim["storageClassName"]
                    if "selector" in claim:
                        existing_claim["spec"]["selector"] = claim["selector"]
                    if "volumeMode" in claim:
                        existing_claim["spec"]["volumeMode"] = claim["volumeMode"]
                    if "dataSource" in claim:
                        existing_claim["spec"]["dataSource"] = claim["dataSource"]
                    if "dataSourceRef" in claim:
                        existing_claim["spec"]["dataSourceRef"] = claim["dataSourceRef"]
                    # No need to add a new claim, just update the existing one
                    self.logger.debug(f"Updated existing PVC claim: {claim_name}")
                    break

            if not found:
                # Add new PVC claim
                template["spec"]["volumeClaimTemplates"].append({
                    "metadata": {"name": claim_name},
                    "spec": {
                        "storageClassName": claim.get("storageClassName", "standard"),
                        "accessModes": claim.get("accessModes", ["ReadWriteOnce"]),
                        "resources": {
                            "requests": {
                                "storage": claim.get("storage", "1Gi")
                            }
                        }
                    }
                })

