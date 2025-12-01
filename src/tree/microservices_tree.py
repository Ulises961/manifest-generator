from calendar import c
from gc import collect
from math import e
import os
import traceback
from typing import Any, Dict, Optional, List, Tuple, cast

import docker
from sympy import root
from embeddings.volumes_classifier import VolumesClassifier
from parsers.env_parser import EnvParser
from tree.command_mapper import CommandMapper
from embeddings.embeddings_engine import EmbeddingsEngine

from embeddings.label_classifier import LabelClassifier
from embeddings.secret_classifier import SecretClassifier
from embeddings.service_classifier import ServiceClassifier

from tree.node_types import NodeType
from tree.node import Node
from parsers.bash_parser import BashScriptParser
from tree.compose_mapper import ComposeMapper
import logging

from utils.docker_utils import parse_key_value_string
from utils.file_utils import load_yaml_file


class MicroservicesTree:
    def __init__(
        self,
        embeddings_engine: EmbeddingsEngine,
        secret_classifier: SecretClassifier,
        service_classifier: ServiceClassifier,
        label_classifier: LabelClassifier,
        volumes_classifier: VolumesClassifier,
        compose_mapper: ComposeMapper,
    ):
        self.logger = logging.getLogger(__name__)
        self.embeddings_engine: EmbeddingsEngine = embeddings_engine
        self.secret_classifier = secret_classifier
        self.service_classifier = service_classifier
        self.env_parser: EnvParser = EnvParser(secret_classifier)
        self.command_parser: CommandMapper = CommandMapper(
            label_classifier, self.env_parser, volumes_classifier
        )

        self.bash_parser: BashScriptParser = BashScriptParser(
            secret_classifier, self.env_parser, embeddings_engine
        )
        self.compose_mapper = compose_mapper

        self.file_extensions = {
            "markdown": [".md", ".markdown"],
            "yaml": [".yml", ".yaml"],
            "text": [".txt"],
            "config": [".ini", ".cfg", ".conf", ".toml"],
            "dockerfile": ["Dockerfile"],
            "bash": [".sh"],
            "env": [".env"],
        }

    def build(self, root_path: str) -> Tuple[Node, Dict[str,Any]]:
        root_node = Node(name=os.path.basename(root_path), type=NodeType.ROOT)
        collected_files: Dict[str,Any] = {}

        self.logger.info(f"Scanning directory: {root_path}")

        compose_files = []
        # Scan for docker-compose files
        for file in os.listdir(root_path):
            if file.endswith(("compose.yaml", "compose.yml")):
                compose_files.append(file)
            else:
               self._process_contextual_file(file, os.path.join(root_path, file), root_node, 500, collected_files)


        if len(compose_files) > 0:
            for compose_file in compose_files:
                self.logger.info(f"Found compose file: {compose_file}")
                self.build_tree_from_compose(
                    os.path.join(root_path, compose_file), root_node, collected_files
                )    
        else:
            # Only scan top-level directories
            for item in os.listdir(root_path):
                item_path = os.path.join(root_path, item)
                if os.path.isdir(item_path):
                    if str(item).startswith("."):
                        self.logger.debug(f"Skipping hidden directory: {item}")
                        continue
                    else:
                        self.logger.info(f"Scanning directory: {item_path}")
                        self._scan_helper(item_path, root_node, item, None, collected_files)

            self.logger.info(
                f"Finished scanning directory: {root_path}, found {len(root_node.children)} microservices."
            )

        return root_node, collected_files

    def _scan_helper(
        self,
        path: str,
        parent: Node,
        dir_name: str,
        preferred_name: Optional[str] = None,
        collected_files: Optional[Dict[str,Any]] = None,
    ) -> None:
        """Scan the directory for microservices and find Dockerfile."""

        # Only check files in the current directory, not recursively
        files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]

        # Check if there's a Dockerfile in this directory
        dockerfile_found = False
        microservice_node = None

        for file in files:
            if file.startswith("."):
                self.logger.warning(f"Skipping hidden file: {file}")
                continue

            if file in self.file_extensions["dockerfile"] or file == "Dockerfile":
                dockerfile_found = True
                dockerfile_path = os.path.join(path, file)
                if collected_files is not None:
                    with open(dockerfile_path, "r") as f:
                        dockerfile_content = f.read()
                    collected_files.update({dir_name: {"name": dir_name, "type": "dockerfile", "content": dockerfile_content, "metadata": {"dockerfile": dockerfile_path, "dockerfile_path": path}}})
                # Generate a new node parent
                if preferred_name is not None:
                    # Use the preferred name if provided
                    dir_name = preferred_name

                microservice_node = Node(
                    name=dir_name,
                    type=NodeType.MICROSERVICE,
                    parent=parent,
                    metadata={"dockerfile_path": path, "dockerfile": file},
                )

                # Add the microservice node to the parent node
                parent.add_child(microservice_node)

                self.logger.debug(
                    f"Adding microservice node: {microservice_node.name} to parent: {parent.name}"
                )
                # Parse Dockerfile and add commands as children to the microservice node
                self._enrich_microservice_with_dockerfile(
                    os.path.join(path, file), microservice_node
                )

                break  # Stop looking for more Dockerfiles in this directory
            
        # Only process environment files and scripts if a Dockerfile was found
        if dockerfile_found and microservice_node is not None:

            # Attach relevant context files to the microservice node
            for file in files:
                self._process_contextual_file(
                    file, os.path.join(path, file), microservice_node
                )

            # Parse bash script if present in EntryPoint or CMD
            self.bash_parser.determine_startup_command(path, files, microservice_node)

        # If we didn't find a Dockerfile, check one level of subdirectories
        if not dockerfile_found:
            subdirs = [
                d
                for d in os.listdir(path)
                if os.path.isdir(os.path.join(path, d)) and not d.startswith(".")
            ]
            for subdir in subdirs:
                subdir_path = os.path.join(path, subdir)
                self.logger.debug(f"Scanning sub-directory: {subdir_path}")
                # Use a subdirectory name that combines parent and child for clarity
                self._scan_helper(subdir_path, parent, subdir, preferred_name=dir_name)

    def build_tree_from_compose(self, compose_file_path: str, parent: Node, collected_files: Dict[str, Any]) -> None:
        """Build the microservices tree from a Docker Compose file."""
        self.logger.info(
            f"Building microservices tree from compose: {compose_file_path}"
        )

        try:
            compose_dict = load_yaml_file(compose_file_path)
        except Exception as e:
            self.logger.error(f"Failed to parse compose file {compose_file_path}: {e}")
            return
        
        collected_files.update({"app": {"name": "app", "type": "docker-compose", "content": compose_dict}})

        for service_name, service_config in compose_dict.get("services", {}).items():
            build_config = service_config.get("build", None)

            if isinstance(build_config, dict):
                build_context = build_config.get("context", None)
                dockerfile = build_config.get("dockerfile", "Dockerfile")
                target = build_config.get("target", None)  # Add this line
            elif isinstance(build_config, str):
                if build_config.startswith("./"):
                    build_config = build_config.replace("./", "")
                elif build_config.startswith("."):
                    build_config = build_config.replace(".", "")            
                build_context = build_config
                dockerfile = "Dockerfile"
                target = None  # Add this line
            else:
                build_context = None
                dockerfile = None
                target = None  # Add this line

            dockerfile_path = None
            dockerfile_dir = None
            if build_context is not None and dockerfile:
                build_context = build_context.replace("./", "")
                dockerfile_path = os.path.join(
                    os.path.dirname(compose_file_path), build_context, dockerfile
                )

                dockerfile_dir = os.path.join(
                    os.path.dirname(compose_file_path), build_context)

                if os.path.exists(dockerfile_path):
                    with open(dockerfile_path, "r") as f:
                        dockerfile_content = f.read()
                    collected_files.update({service_name: {"name": service_name, "type": "dockerfile", "content": dockerfile_content, "metadata": {"dockerfile": dockerfile_path, "dockerfile_path": dockerfile_dir}}})

            microservice_node = Node(
                name=service_name,
                type=NodeType.MICROSERVICE,
                parent=parent,
                metadata={
                    "dockerfile_path": dockerfile_dir,
                    "compose_file": compose_file_path,
                },
            )

            if dockerfile:
                microservice_node.metadata["dockerfile"] = dockerfile
            
            if target:  # Add this block
                microservice_node.metadata["target"] = target

            parent.add_child(microservice_node)
            self.logger.info(f"Added microservice from compose: {service_name}")

            # Enrich node with compose attributes regardless of Dockerfile presence
            self.compose_mapper._enrich_microservice_with_compose_info(
                service_config, microservice_node, os.path.dirname(compose_file_path), compose_dict
            )

            if dockerfile_path and os.path.isfile(dockerfile_path):
                self._enrich_microservice_with_dockerfile(
                    dockerfile_path, microservice_node
                )
            else:
                self.logger.warning(
                    f"No Dockerfile for service {service_name} (expected at {dockerfile_path})."
                )

        networks = compose_dict.get("networks", None)
        if networks and len(networks) > 1:
            for network in networks:
                network_node = Node(
                    name=network,
                    type=NodeType.NETWORK,
                    value=network,
                    parent=parent,
                )
                parent.add_child(network_node)

        volumes = compose_dict.get("volumes", None)
        if volumes:
            for volume in volumes:
                volume_node = Node(
                    name=volume,
                    type=NodeType.VOLUME_CLAIM,
                    value=volume,
                    parent=parent,
                )
                parent.add_child(volume_node)

    def prepare_microservice(self, node: Node) -> Dict[str, Any]:
        """Generate manifests for the given microservice node."""
        # Generate manifests for the microservice
        microservice: Dict[str, Any] = {"name": node.name}
        microservice.setdefault("labels", {"app": node.name})
        microservice.setdefault(
            "metadata", node.metadata if node.metadata is not None else {}
        )
        microservice.setdefault("image", node.name.lower())
        microservice.setdefault("env", [])
        microservice.setdefault("volume_mounts", [])
        microservice.setdefault("volumes", [])

        if len(image := node.get_children_by_type(NodeType.IMAGE)) > 0:
            # There's a unique image child
            microservice["image"] = image[0].value
        
        if len(labels := node.get_children_by_type(NodeType.LABEL)) > 0:

            for label in labels:
                parsed_labels = parse_key_value_string(cast(str, label.value))
                microservice["labels"].update(parsed_labels)  # type: ignore

        if len(annotations := node.get_children_by_type(NodeType.ANNOTATION)) > 0:
            microservice.setdefault("annotations", {})
            for annotation in annotations:
                parsed_annotations = parse_key_value_string(cast(str, annotation.value))
                microservice["annotations"].update(parsed_annotations)  # type: ignore

        if (
            len(
                entrypoint := node.get_children_by_type(
                    NodeType.ENTRYPOINT, must_be_active=True
                )
            )
            > 0
        ):
            self.logger.debug(
                f"Processing entrypoint for microservice: {node.name}, value: {entrypoint[0].value}"
            )
            # There's a unique entrypoint
            microservice["command"] = entrypoint[0].value

        if len(cmd := node.get_children_by_type(NodeType.CMD, must_be_active=True)) > 0:
            # There's a unique command. Possibly none
            microservice["args"] = cmd[0].value

        microservice.setdefault("ports", [])

        if (
            len(
                ports := node.get_children_by_type(
                    NodeType.CONTAINER_PORT, must_be_active=True
                )
            )
            > 0
        ):
            microservice["ports"] = [int(cast(str, port.value)) for port in ports if port.value.isdigit()]# type: ignore
            microservice["service-ports"] = [
                int(cast(str, port.value)) for port in ports if port.value.isdigit()# type: ignore
            ]
            microservice["type"] = "ClusterIP"
            microservice["protocol"] = "TCP"
            microservice["workload"] = "Deployment"

        if len(service_ports := node.get_children_by_type(NodeType.SERVICE_PORT_MAPPING)) > 0:
            microservice["service-ports"] = []
            for port in service_ports:
                port_mapping = str(port.value)
                if ":" in port_mapping:
                    values = port_mapping.split(":")
                    host_port, container_port = values[-2], values[-1]
                    microservice["ports"].append(int(container_port))
                    microservice["service-ports"].append(int(host_port))

        if (
            len(
                healthcheck := node.get_children_by_type(
                    NodeType.HEALTHCHECK, must_be_active=True
                )
            )
            > 0
        ):
            # There's a unique healthcheck
            microservice["liveness_probe"] = {
                "exec": {"command": healthcheck[0].value},
            }

            for flag, value in healthcheck[0].metadata.items():
                microservice["liveness_probe"].update({flag: value})

        if (
            len(
                env_vars := node.get_children_by_type(NodeType.ENV, must_be_active=True)
            )
            > 0
        ):
            microservice.setdefault("env", [])
            for env in env_vars:
                self.logger.debug(f"processing env var: {env.name}")
                microservice["env"].append(
                    {"name": env.name, "key": "config", "value": env.value}
                )  # type: ignore
        if (
            len(
                secrets := node.get_children_by_type(
                    NodeType.SECRET, must_be_active=True
                )
            )
            > 0
        ):
            # If the env var is a secret, add it to the secrets list
            microservice.setdefault("secrets", [])
            for secret in secrets:
                microservice["secrets"].append(
                    {"name": secret.name, "key": "password", "value": secret.value}
                )  # type: ignore
        if (
            len(
                volumes_mounts := node.get_children_by_type(
                    NodeType.VOLUME_MOUNT, must_be_active=True
                )
            )
            > 0
        ):
            for index, volume_mount in enumerate(volumes_mounts):
                microservice.setdefault("volume_mounts", [])
                microservice["volume_mounts"].append(
                    {"name": f"{volume_mount.name}" if volume_mount.name != volume_mount.type else f"volume-{index}", "mountPath": volume_mount.value}
                )

                microservice.setdefault("volumes", [])
                volume_to_add: Dict[str, Any] = {"name": f"{volume_mount.name}" if volume_mount.name != volume_mount.type else f"volume-{index}"}
                if volume_mount.is_persistent:
                    # Add volume
                    volume_to_add["persistentVolumeClaim"] = {
                        "claimName": f"{volume_mount.name}" if volume_mount.name != volume_mount.type else f"volume-{index}",
                    }
                    
                    # If the volume_mount is persistent, add it to the persistent volumes list
                    microservice.setdefault("persistent_volumes", [])
                    microservice["persistent_volumes"].append(
                        {
                            "name": f"{volume_mount.name}" if volume_mount.name != volume_mount.type else f"volume-{index}",
                            "labels": {
                                "app": microservice["labels"]["app"],
                                "storage-type": "persistent",
                            },
                            "storage_class": "standard",
                            "access_modes": ["ReadWriteOnce"],
                        }
                    )  # type: ignore

                elif volume_mount.is_directory:
                    volume_to_add["hostPath"] = {
                        "path": volume_mount.children[0].value,
                        "type": "Directory",
                    }
                elif volume_mount.is_file:
                    volume_to_add["hostPath"] = {
                        "path": volume_mount.children[0].value,
                        "type": "File",
                    }
                else:
                    volume_to_add["emptyDir"] = {}
                microservice["volumes"].append(volume_to_add)

        if len(workdirs := node.get_children_by_type(NodeType.WORKDIR)) > 0:
            # There's a unique child working dir
            microservice.setdefault("workdir", None)
            microservice["workdir"] = workdirs[0].value

        # Enrich microservice
        container_ports = microservice.get("ports", [])
        service_extra_info = self.service_classifier.decide_service(
            node.name, container_ports
        )

        if service_extra_info:
            # Only use ontology ports if not set in the container configuration
            if microservice["ports"] == []:
                container_ports = [int(port) for port in service_extra_info["ports"]]
                microservice["ports"] = container_ports

                # Set service ports fallback to the container ports
                microservice["service-ports"] = service_extra_info.get(
                    "servicePorts", container_ports
                )
            microservice["workload"] = service_extra_info["workload"]
            microservice["protocol"] = service_extra_info["protocol"]
            microservice["type"] = service_extra_info.get("serviceType", "ClusterIP")
            microservice["labels"].update(service_extra_info["labels"])


        if len(restart := node.get_children_by_type(NodeType.RESTART)) > 0:
            if "no" == restart[0].value:
                microservice["restart_policy"] = "Never"
                # Remove workload information, let the model decide
                microservice["workload"] = None
            else:
                microservice["restart_policy"] = restart[0].value
        
        if len(dependencies := node.get_children_by_type(NodeType.DEPENDENCY)) > 0:
            microservice.setdefault("depends_on", {"deps": []})
            
            for dependency in dependencies:
                dep = {"service": dependency.value, "conditions": [child.value for child  in dependency.children]}
                microservice["depends_on"]["deps"].append(dep)

        self.logger.info(
            f"Microservice {microservice} prepared for manifest generation"
        )
        
        return microservice

    def print_tree(self, node: Node, level: int = 0) -> None:
        """Recursively print the tree structure.
        Example:\n
            root (ROOT)
            |-- microservice1 
            |    |-- ENV_VAR value (ENV)
            |    |-- CMD value (CMD)
            |-- microservice2
                |-- LABEL version=1.0 (LABEL)   
        """
        if level == 0:
            indent = ""
            print(f"{indent}{node.name} ({node.type})")
        else:
            indent = ""
            for i in range(level - 1):
                if i == 0:
                    indent = " " * ((i + 1) * 4) + "|"
                else:
                    indent += " "
            if node.value is not None:
                if level > 1:
                    indent = indent + " " * (level * 2) + "|"
                    print(f"{indent}-- {node.name} {node.value} ({node.type})")
                else:
                    indent = indent + " " * (level * 4) + "|"
                    print(f"{indent}-- {node.name}")
            else:
                indent = indent + " " * (level * 4) + "|"
                print(f"{indent}-- {node.name}")

        for child in node.children:
            self.print_tree(child, level + 1)

    def _enrich_microservice_with_dockerfile(
        self, dockerfile_path: str, microservice_node: Node
    ) -> None:
        """Parse and populate the microservice node with information gathered from the dockerfile"""
        commands = self.command_parser.parse_dockerfile(dockerfile_path)

        for command in commands:
            # Classify the command
            nodes: List[Node] = self.command_parser.generate_node_from_command(
                command, microservice_node
            )

            for node in nodes:
                if node.type == NodeType.WORKDIR:
                    # Keep the latest one
                    for child in microservice_node.children:
                        if child.type == NodeType.WORKDIR:
                            self.logger.debug(
                                f"Removing old WORKDIR node: {child.name}"
                            )
                            microservice_node.children.remove(child)
                if node.type == NodeType.ENTRYPOINT:
                    # Keep the latest one
                    for child in microservice_node.children:
                        if child.type == NodeType.ENTRYPOINT:
                            self.logger.debug(
                                f"Removing old ENTRYPOINT node: {child.name}"
                            )
                            microservice_node.children.remove(child)
                if node.type == NodeType.CMD:
                    # Keep the latest one
                    for child in microservice_node.children:
                        if child.type == NodeType.CMD:
                            self.logger.debug(f"Removing old CMD node: {child.name}")
                            microservice_node.children.remove(child)

                if node.metadata == {} or node.metadata.get("status", "active") == "active":
                    self.logger.debug(
                        f"Adding command node: {node.name} with metadata: {node.metadata}"
                    )
                    microservice_node.add_child(node)

    def _process_contextual_file(
        self, file_name: str, file_path: str, node: Node, max_file_size_kb: int = 500, collected_files: Optional[Dict] = None
    ) -> None:
        name, ext = os.path.splitext(file_name)
        for file_type, extensions in self.file_extensions.items():
            if ext in extensions:
                # Check if the file is a config file
                if file_type == ".env":
                    # Parse the config file and add it to the node
                    config_nodes = self.env_parser.parse(file_path)
                    node.add_children(config_nodes)
                else:
                    try:
                        # Context files are added to the collected files only if below size limit
                        file_size_kb = os.path.getsize(file_path) / 1024
                        if file_size_kb > max_file_size_kb:
                            self.logger.warning(
                                f"Skipping file {file_name} due to size {file_size_kb:.2f}KB exceeding limit of {max_file_size_kb}KB."
                            )
                            return
                        with open(file_path, "r") as f:
                            content = f.read()
                        if collected_files is not None:
                            # Add the contextual file to the collected files
                            collected_files.update({file_name: {"name": file_name, "type": "contextual", "content": content, "metadata": {"path": file_path}}})
                        self.logger.debug(
                            f"Added contextual file node: {file_name} of type {file_type} to microservice {node.name}"
                        )
                    except Exception as e:
                        self.logger.error(
                            f"Failed to read or process file {file_name}: {e}"
                        )
                

    def prepare_network_policy(self, node: Node) -> Dict[str, Any]:
        """Generate manifests for the given network policy node. Currently not used but placeholder for future extensions."""
        network_policy: Dict[str, Any] = {
            "type": "NetworkPolicy",
            "name": node.name,
        }
        self.logger.info(f"Network policy {network_policy} prepared for manifest generation")
        return network_policy