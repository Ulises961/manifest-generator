import logging
import os
from re import L
import re
from typing import Dict, Any, List, Optional
from embeddings.secret_classifier import SecretClassifier
from embeddings.volumes_classifier import VolumesClassifier
from parsers.env_parser import EnvParser
from tree.node import Node
from tree.node_types import NodeType
from embeddings.label_classifier import LabelClassifier


class ComposeMapper:
    def __init__(
        self,
        secret_classifier: SecretClassifier,
        volumes_classifier: VolumesClassifier,
        label_classifier: LabelClassifier,
    ):
        self.logger = logging.getLogger(__name__)
        self._env_parser = EnvParser(secret_classifier)
        self._volumes_classifier = volumes_classifier
        self._label_classifier = label_classifier

    def _enrich_microservice_with_compose_info(
        self, service_config: Dict[str, Any], microservice_node: Node, compose_dir: str, compose_dict: Dict[str, Any]
    ):
        """Enrich the microservice node with information from the docker-compose service configuration."""
        # Extract environment variables
        env_vars = service_config.get("environment", {})
        if isinstance(env_vars, list):
            env_vars = {
                var.split("=")[0]: var.split("=")[1] for var in env_vars if "=" in var
            }
            for var in env_vars:
                env_node = self._env_parser.create_env_node(var, env_vars[var])
                env_node.parent = microservice_node
                microservice_node.add_child(env_node)
        elif isinstance(env_vars, dict):
            for var, value in env_vars.items():
                env_node = self._env_parser.create_env_node(var, value)
                env_node.parent = microservice_node
                microservice_node.add_child(env_node)
        # Extract env_file
        env_files = service_config.get("env_file", [])
        if isinstance(env_files, str):
            env_files = [env_files]
        for env_file in env_files:
            nodes = self._env_parser.parse(os.path.join(compose_dir, env_file))
            for node in nodes:
                node.parent = microservice_node
                microservice_node.add_child(node)
        # Extract ports
        ports = service_config.get("ports", [])
        for port in ports:
            if isinstance(port, int):
                port = str(port)
            elif isinstance(port, dict):
                port = port.get("target", "")
            elif not isinstance(port, str):
                continue
            if "/" in port:
                port = port.split("/")[0]
            
            port_node = Node(
                name="SERVICE_PORT", type=NodeType.SERVICE_PORT_MAPPING, value=port, parent=microservice_node
            )
            if ":" in port:
                host_port, container_port = port.split(":", 1)
                port_node.metadata["host_port"] = host_port
                port_node.metadata["container_port"] = container_port
            else:
                port_node.metadata["container_port"] = port
            microservice_node.add_child(port_node)

        if "expose" in service_config:
            exposed_ports = service_config.get("expose", [])
            for port in exposed_ports:
                if isinstance(port, int):
                    port = str(port)
                elif not isinstance(port, str):
                    continue
                if "/" in port:
                    port = port.split("/")[0]
                
                expose_node = Node(
                    name="CONTAINER_PORT", type=NodeType.CONTAINER_PORT, value=port, parent=microservice_node
                )
                expose_node.metadata["container_port"] = port
                microservice_node.add_child(expose_node)
        # Extract volumes
        self._extract_volumes(service_config, microservice_node, compose_dir, compose_dict)

        # Extract command
        command = service_config.get("command", None)
        if command:
            command_node = Node(
                name="CMD", type=NodeType.CMD, value=command, parent=microservice_node
            )
            microservice_node.add_child(command_node)

        # Extract labels
        labels = service_config.get("labels", [])
        for label in labels:
            if "=" in label:
                key, value = label.split("=", 1)
                is_label = self.decide_label(key)
                label_node = Node(
                    name="LABEL",
                    value=f"{key}={value}",
                    type=NodeType.LABEL if is_label else NodeType.ANNOTATION,
                    parent=microservice_node,
                )
                microservice_node.add_child(label_node)
            elif isinstance(labels, dict):
                for key, value in labels.items():
                    is_label = self.decide_label(key)
                    label_node = Node(
                        name="LABEL",
                        value=f"{key}={value}",
                        type=NodeType.LABEL if is_label else NodeType.ANNOTATION,
                        parent=microservice_node,
                    )
                    microservice_node.add_child(label_node)

        # Extract image
        image = service_config.get("image", None)
        if image:
            image_node = Node(
                name="IMAGE", type=NodeType.IMAGE, value=image, parent=microservice_node
            )
            microservice_node.add_child(image_node)
            microservice_node.metadata["dockerfile"] = None  # No Dockerfile if image is used
            microservice_node.metadata["dockerfile_path"] = None  # No Dockerfile if image is used

        # Extract dependencies
        depends_on = service_config.get("depends_on", [])
        if isinstance(depends_on, dict):
            for dependency, condition in depends_on.items():
                dependency_node = Node(
                    name="DEPENDENCY",
                    type=NodeType.DEPENDENCY,
                    value=dependency,
                    parent=microservice_node,
                )
                condition_node = Node(
                    name="CONDITION",
                    type=NodeType.CONDITION,
                    value=condition,
                    parent=microservice_node,
                )
                dependency_node.add_child(condition_node)
                microservice_node.add_child(dependency_node)
        elif isinstance(depends_on, list):
            for dependency in depends_on:
                dependency_node = Node(
                    name="DEPENDENCY",
                    type=NodeType.DEPENDENCY,
                    value=dependency,
                    parent=microservice_node,
                )
                microservice_node.add_child(dependency_node)

        # Extract restart policy
        restart = service_config.get("restart", None)
        if restart:
            restart_node = Node(
                name="RESTART",
                type=NodeType.RESTART,
                value=restart,
                parent=microservice_node,
            )
            microservice_node.add_child(restart_node)

        # Extract healthcheck
        healthcheck = service_config.get("healthcheck", None)
        if healthcheck:
            healthcheck_node = Node(
                name="HEALTHCHECK",
                type=NodeType.HEALTHCHECK,
                value=str(healthcheck),
                parent=microservice_node,
            )
            microservice_node.add_child(healthcheck_node)

        # Extract networks
        networks = service_config.get("networks", [])
        for network in networks:
            network_node = Node(
                name=network,
                type=NodeType.NETWORK,
                value=network,
                parent=microservice_node,
            )
            microservice_node.add_child(network_node)
            # Add labels to correctly allow communication between microservices
            label_node = Node(
                name="LABEL",
                value=f"tier-{network}={network}",
                type=NodeType.LABEL,
                parent=microservice_node,
            )
            microservice_node.add_child(label_node)

        # Extract entrypoint
        entrypoint = service_config.get("entrypoint", None)
        if entrypoint:
            entrypoint_node = Node(
                name="ENTRYPOINT",
                type=NodeType.ENTRYPOINT,
                value=entrypoint,
                parent=microservice_node,
            )
            microservice_node.add_child(entrypoint_node)

        # Extract config and secrets if any
        for config_type in ["configs", "secrets"]:
            items = service_config.get(config_type, [])
            for item in items:
                item_node = Node(
                    name=config_type[:-1].upper(),
                    type=NodeType[config_type[:-1].upper()],
                    value=item,
                    parent=microservice_node,
                )
                microservice_node.add_child(item_node)

    def _extract_volumes(self, service_config: Dict[str, Any], microservice_node: Node, compose_dir: str, compose_dict: Dict[str, Any]):
        """Extract and process volume configurations from docker-compose service."""
        volumes = service_config.get("volumes", [])
    
        for volume in volumes:
            volume_mount = self._create_volume_mount(volume, microservice_node, compose_dir, compose_dict)
            if volume_mount:
                microservice_node.add_child(volume_mount)

    def _create_volume_mount(self, volume, microservice_node: Node, compose_dir: str, compose_dict: Dict[str, Any]) -> Optional[Node]:
        """Create a volume mount node from volume configuration."""
        if isinstance(volume, dict):
            volume = self._handle_dict_volume(volume, microservice_node, compose_dir, compose_dict)
            if volume is None:
                self.logger.warning(f"Unsupported volume configuration: {volume}")
                return None
            return volume
        else:
            return self._handle_string_volume(volume, microservice_node, compose_dir, compose_dict)

    def _handle_dict_volume(self, volume: Dict[str, Any], microservice_node: Node, compose_dir: str, compose_dict: Dict[str, Any]) -> Optional[Node]:
        """Handle volume configuration defined as a dictionary."""
        external: Optional[str] = volume.get("source", None)
        internal: Optional[str] = volume.get("target", None)
        type_: Optional[str] = volume.get("type", None)

        if type_ == "volume" and internal and external and external in compose_dict.get("volumes", {}):
            return self._create_persistent_volume_mount(external, internal, microservice_node)
        elif type_ == "bind" and external and internal:
            return self._create_bind_volume_mount(external, internal, microservice_node, compose_dir)
        
        return None

    def _handle_string_volume(self, volume: str, microservice_node: Node, compose_dir: str, compose_dict: Dict[str, Any]) -> Node:
        """Handle volume configuration defined as a string."""
        # Parse volume string: "external_path:internal_path" or "internal_path"
        external, internal = volume.split(":", 1) if ":" in volume else (None, volume)
        
        volume_mount = Node(
            name="VOLUME_MOUNT",
            type=NodeType.VOLUME_MOUNT,
            value=internal,
            parent=microservice_node,
        )
        
        if external:
            if external in compose_dict.get("volumes", {}):
                volume_mount.is_persistent = True
                volume_mount.name = external
            else:
                self._setup_bind_mount(volume_mount, external, compose_dir)
        
        return volume_mount

    def _create_persistent_volume_mount(self, external: str, internal: str, microservice_node: Node) -> Node:
        """Create a persistent volume mount node."""
        volume_mount = Node(
            name=external,
            type=NodeType.VOLUME_MOUNT,
            value=internal,
            parent=microservice_node,
        )
        volume_mount.is_persistent = True
        volume_mount.is_directory = False
        volume_mount.is_file = False
        return volume_mount

    def _create_bind_volume_mount(self, external: str, internal: str, microservice_node: Node, compose_dir: str) -> Node:
        """Create a bind volume mount node."""
        volume_mount = Node(
            name="VOLUME_MOUNT",
            type=NodeType.VOLUME_MOUNT,
            value=internal,
            parent=microservice_node,
        )
        volume_mount.is_directory = True
        
        self._setup_bind_mount(volume_mount, external, compose_dir)
        return volume_mount

    def _setup_bind_mount(self, volume_mount: Node, external: str, compose_dir: str):
        """Set up bind mount configuration and create volume node."""
        # Clean external path
        external = external.replace("./", "").replace("~", "")
        external_dir = os.path.join(compose_dir, external)
        
        # Create volume node
        volume_node = Node(
            name=external,
            type=NodeType.VOLUME,
            value=external_dir,
            parent=volume_mount,
        )
        
        # Check if it's a file
        if os.path.isfile(external_dir):
            volume_mount.is_file = True
            volume_mount.is_directory = False
        else:
            volume_mount.is_directory = True
            volume_mount.is_file = False

        volume_mount.add_child(volume_node)

    def decide_label(self, label_key: str) -> bool:
        classified_label = self._label_classifier.classify_label(label_key)
        return classified_label == "label"
