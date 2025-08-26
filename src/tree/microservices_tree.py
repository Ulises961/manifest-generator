import os
import traceback
from typing import Any, Dict, Optional, List, cast
from embeddings.volumes_classifier import VolumesClassifier
from parsers.env_parser import EnvParser
from tree.attached_file import AttachedFile
from tree.command_mapper import CommandMapper
from embeddings.embeddings_engine import EmbeddingsEngine

from embeddings.label_classifier import LabelClassifier
from embeddings.secret_classifier import SecretClassifier
from embeddings.service_classifier import ServiceClassifier

from tree.node_types import NodeType
from tree.node import Node
from parsers.bash_parser import BashScriptParser
import logging

from utils.docker_utils import parse_key_value_string


class MicroservicesTree:
    def __init__(
        self,
        root_path: str,
        embeddings_engine: EmbeddingsEngine,
        secret_classifier: SecretClassifier,
        service_classifier: ServiceClassifier,
        label_classifier: LabelClassifier,
        volumes_classifier: VolumesClassifier
    ):
        self.logger = logging.getLogger(__name__)
        self.root_path = root_path
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

        self.file_extensions = {
            "markdown": [".md", ".markdown"],
            "json": [".json"],
            "yaml": [".yml", ".yaml"],
            "text": [".txt"],
            "config": [".ini", ".cfg", ".conf", ".toml"],
            "dockerfile": ["Dockerfile"],
            "bash": [".sh"],
            "env": [".env"],
        }

    def build(self) -> Node:
        root_node = Node(name=os.path.basename(self.root_path), type=NodeType.ROOT)

        self.logger.info(f"Scanning directory: {self.root_path}")

        # Only scan top-level directories
        for item in os.listdir(self.root_path):
            item_path = os.path.join(self.root_path, item)
            if os.path.isdir(item_path):
                if str(item).startswith("."):
                    self.logger.debug(f"Skipping hidden directory: {item}")
                    continue
                else:
                    self.logger.info(f"Scanning directory: {item_path}")
                    self._scan_helper(item_path, root_node, item)

        self.logger.info(
            f"Finished scanning directory: {self.root_path}, found {len(root_node.children)} microservices."
        )

        return root_node

    def _scan_helper(
        self,
        path: str,
        parent: Node,
        dir_name: str,
        preferred_name: Optional[str] = None,
    ) -> None:
        """Scan the directory for microservices and find Dockerfile."""

        # Only check files in the current directory, not recursively
        files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]

        # Check if there's a Dockerfile in this directory
        dockerfile_found = False
        microservice_node = None

        for file in files:
            if file.startswith('.'):
                    self.logger.warning(f"Skipping hidden file: {file}")
                    continue
            if file == "Dockerfile":
                dockerfile_found = True
                dockerfile_path = os.path.join(path, file)
                self.logger.info(f"Found Dockerfile in {dockerfile_path}")
                # Generate a new node parent
                if preferred_name is not None:
                    # Use the preferred name if provided
                    dir_name = preferred_name

                microservice_node = Node(
                    name=dir_name,
                    type=NodeType.MICROSERVICE,
                    parent=parent,
                    metadata={"dockerfile_path": path},
                )

                # Add the microservice node to the parent node
                parent.add_child(microservice_node)

                self.logger.debug(
                    f"Adding microservice node: {microservice_node.name} to parent: {parent.name}"
                )
                # Parse Dockerfile and add commands as children to the microservice node
                self._populate_microservice_node(
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

    def prepare_for_manifest(self, node: Node) -> None:
        """Generate manifests for the given node and its children."""
        if node.type == NodeType.MICROSERVICE:
            self.logger.info(
                f"Preparing microservice: {node.name} for manifest generation"
            )
            self.prepare_microservice(node)

    def prepare_microservice(self, node: Node) -> Dict[str, Any]:
        """Generate manifests for the given microservice node."""
        # Generate manifests for the microservice
        microservice: Dict[str, Any] = {"name": node.name}
        microservice.setdefault("labels", {"app.kubernetes.io/name": node.name})
        microservice.setdefault(
            "metadata", {"dockerfile": node.metadata.get("dockerfile_path", "")}
        )
        microservice.setdefault("image", node.name.lower())
        microservice.setdefault("env", []) 
        microservice.setdefault("volume_mounts", []) 
        microservice.setdefault("volumes", [])  
        
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
            len(ports := node.get_children_by_type(NodeType.PORT, must_be_active=True))
            > 0
        ):
            microservice["ports"] = [int(cast(str, port.value)) for port in ports]
            microservice["service-ports"] = [
                int(cast(str, port.value)) for port in ports
            ]
            microservice["type"] = "ClusterIP"
            microservice["protocol"] = "TCP"
            microservice["workload"] = "Deployment"

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
                volumes := node.get_children_by_type(
                    NodeType.VOLUME, must_be_active=True
                )
            )
            > 0
        ):
            for index, volume in enumerate(volumes):
                if volume.is_persistent:
                    # If the volume is persistent, add it to the persistent volumes list
                    if "persistent_volumes" not in microservice:
                        microservice["persistent_volumes"] = []

                    microservice["persistent_volumes"].append(
                        {
                            "name": f"volume-{index}",
                            "labels": {
                                "app": microservice["labels"]["app.kubernetes.io/name"],
                                "storage-type": "persistent",
                            },
                            "storage_class": "standard",
                            "access_modes": ["ReadWriteOnce"],
                            "resources": 1024,
                        }
                    )  # type: ignore
                microservice.setdefault("volume_mounts", [])
                microservice["volume_mounts"].append(
                    {"name": f"volume-{index}", "mountPath": volume.value}
                )

                microservice.setdefault("volumes", [])
                volume_to_add: Dict[str, Any] = {"name": f"volume-{index}"}
                if volume.is_persistent:
                    volume_to_add["persistentVolumeClaim"] = {
                        "claimName": f"volume-{index}"
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

        if service_extra_info is not None:
            microservice["workload"] = service_extra_info["workload"]
            microservice["protocol"] = service_extra_info["protocol"]
            microservice["type"] = service_extra_info.get("serviceType", "ClusterIP")

            # Set ports
            container_ports = [int(port) for port in service_extra_info["ports"]]

            # Set service ports fallback to the container ports
            microservice["service-ports"] = service_extra_info.get(
                "servicePorts", container_ports
            )

            # Only use ontology ports of not set in the container configuration
            if len(microservice["ports"]) == 0:
                microservice["ports"] = container_ports

            microservice["labels"].update(service_extra_info["labels"])

        self.logger.info(
            f"Microservice {microservice} prepared for manifest generation"
        )

        return microservice

    def print_tree(self, node: Node, level: int = 0) -> None:
        """Recursively print the tree structure."""
        if level == 0:
            indent = ""
            print(f"{indent}{node.name} ({node.type})")
        else:
            indent = ""
            for i in range(level - 1):
                indent = " " * ((i + 1) * 4) + "|"
            indent = indent + " " * (level * 4) + "|"
            print(
                f"{indent}-- {node.name} ({node.value})"
                if node.value is not None
                else f"{indent}-- {node.name}"
            )

        for child in node.children:
            self.print_tree(child, level + 1)

    def _populate_microservice_node(
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

                if node.metadata == {} or node.metadata["status"] == "active":
                    self.logger.debug(
                        f"Adding command node: {node.name} with metadata: {node.metadata}"
                    )
                    microservice_node.add_child(node)

    def _process_contextual_file(
        self, file_name: str, file_path: str, node: Node, max_file_size_kb: int = 500
    ) -> None:
        name, ext = os.path.splitext(file_name)
        for file_type, extensions in self.file_extensions.items():
            if ext in extensions:
                # Check if the file is a config file
                if file_type == ".env":
                    # Parse the config file and add it to the node
                    config_nodes = self.env_parser.parse(file_path)
                    node.add_children(config_nodes)