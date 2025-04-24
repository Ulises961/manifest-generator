import json
import os
from typing import Any, Dict, Optional, List, cast
from parsers.env_parser import EnvParser
from tree.command_mapper import CommandMapper
from embeddings.embeddings_engine import EmbeddingsEngine

from embeddings.label_classifier import LabelClassifier
from embeddings.secret_classifier import SecretClassifier
from embeddings.service_classifier import ServiceClassifier
from tree.docker_instruction_node import DockerInstruction
from tree.node_types import NodeType
from tree.node import Node
from parsers.bash_parser import BashScriptParser
import logging


class MicroservicesTree:
    def __init__(
        self,
        root_path: str,
        embeddings_engine: EmbeddingsEngine,
        secret_classifier: SecretClassifier,
        service_classifier: ServiceClassifier,
        label_classifier: LabelClassifier,
    ):
        self.root_path = root_path
        self.embeddings_engine: EmbeddingsEngine = embeddings_engine
        self.secret_classifier = secret_classifier
        self.service_classifier = service_classifier
        self.command_parser: CommandMapper = CommandMapper(label_classifier)
        self.env_parser: EnvParser = EnvParser(secret_classifier)
        self.bash_parser: BashScriptParser = BashScriptParser(
            secret_classifier, self.env_parser, embeddings_engine
        )

        self.logger = logging.getLogger(__name__)

    def build(self) -> Node:
        root_node = Node(name=os.path.basename(self.root_path), type=NodeType.ROOT)
        logging.info(f"Scanning directory: {self.root_path}")
        for root, dirs, _ in os.walk(self.root_path, topdown=True):
            for dir in dirs:
                if str(dir).startswith("."):
                    logging.info(f"Skipping hidden directory: {dir}")
                    continue
                else:
                    logging.info(f"Scanning directory: {os.path.join(root, dir)}")
                    self._scan_helper(os.path.join(root, dir), root_node, dir)
        logging.info(
            f"Finished scanning directory: {self.root_path}, found {len(root_node.children)} microservices."
        )
        return root_node

    def _scan_helper(self, path: str, parent: Node, dir_name: str) -> None:
        """Recursively scan the directory for microservices and their dependencies."""

        for root, _, files in os.walk(path):

            # Scan the directory for dockerfiles, if present we assume a microservice
            is_microservice = False
            microservice_node: Optional[Node] = None

            for file in files:
                if file.endswith(".dockerfile") or file == "Dockerfile":
                    logging.info(f"Found Dockerfile in {os.path.join(root, file)}")
                    # Generate a new node parent
                    microservice_node = Node(
                        name=dir_name, type=NodeType.MICROSERVICE, parent=parent
                    )

                    # Add the microservice node to the parent node
                    parent.add_child(microservice_node)
                    logging.info(
                        f"Adding microservice node: {microservice_node.name} to parent: {parent.name}"
                    )
                    # Parse Dockerfile and add commands as children to the microservice node
                    commands = self.command_parser.parse_dockerfile(
                        os.path.join(root, file)
                    )

                    for command in commands:
                        # Classify the command
                        node: DockerInstruction = (
                            self.command_parser.generate_node_from_command(
                                command, microservice_node
                            )
                        )
                        if node.type == NodeType.WORKDIR:
                            # Keep the latest one
                            for child in microservice_node.children:
                                if child.type == NodeType.WORKDIR:
                                    logging.info(
                                        f"Removing old WORKDIR node: {child.name}"
                                    )
                                    microservice_node.children.remove(child)

                        if node.metadata == {} or node.metadata["status"] == "active":
                            logging.info(
                                f"Adding command node: {node.name} with metadata: {node.metadata}"
                            )
                            microservice_node.add_child(node)

                    is_microservice = True
                    break

            # Only parse the directory if it is a microservice
            if is_microservice and microservice_node is not None:
                # Parse the directory for .env files
                for file in files:
                    # Skip hidden files except .env
                    if str(file).startswith("."):
                        if file == ".env":
                            # Parse env file and add vars as children to root node
                            self.env_parser.parse(
                                os.path.join(root, file), microservice_node
                            )
                            continue

                # Parse bash script if present in EntryPoint or CMD
                self.bash_parser.determine_startup_command(
                    root, files, microservice_node
                )

    def prepare_for_manifest(self, node: Node) -> None:
        """Generate manifests for the given node and its children."""
        if node.type == NodeType.MICROSERVICE:
            self.logger.info(
                f"Preparing microservice: {node.name} for manifest generation"
            )
            self.prepare_microservice(node)

    def prepare_microservice(self, node: Node) -> None:
        """Generate manifests for the given microservice node."""
        # Generate manifests for the microservice
        service_extra_info = self.service_classifier.decide_service(node.name)
        microservice: Dict[str, Any] = {"name": node.name}
        if len(labels := node.get_children_by_type(NodeType.LABEL)) > 0:
            if not "labels" in microservice:
                microservice["labels"] = []
            for label in labels:
                microservice["labels"].append(label.value)  # type: ignore
        if len(annotations := node.get_children_by_type(NodeType.ANNOTATION)) > 0:
            if not "annotations" in microservice:
                microservice["annotations"] = []
            for annotation in annotations:
                microservice["annotations"].append(annotation.value)  # type: ignore

        if (
            len(
                entrypoint := node.get_children_by_type(
                    NodeType.ENTRYPOINT, must_be_active=True
                )
            )
            > 0
        ):
            # There's a unique entrypoint
            microservice["entrypoint"] = entrypoint[0].value

        if len(cmd := node.get_children_by_type(NodeType.CMD, must_be_active=True)) > 0:
            # There's a unique command. Possibly none
            microservice["command"] = cmd[0].value

        if (
            len(ports := node.get_children_by_type(NodeType.PORT, must_be_active=True))
            > 0
        ):
            microservice["ports"] = [port.value for port in ports]

        if (
            len(
                healthcheck := node.get_children_by_type(
                    NodeType.HEALTHCHECK, must_be_active=True
                )
            )
            > 0
        ):
            # There's a unique healthcheck
            microservice["liveness_probe"] = healthcheck[0].value

        if (
            len(
                env_vars := node.get_children_by_type(NodeType.ENV, must_be_active=True)
            )
            > 0
        ):
            for env in env_vars:
                microservice.setdefault("env", [])
                microservice["env"].append(
                    {"key": env.name, "value": env.value}
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
                    {"name": secret.name, "key": secret.value}
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
                volume = cast(DockerInstruction, volume)
                if volume.is_persistent:
                    # If the volume is persistent, add it to the persistent volumes list
                    if "persistent_volumes" not in microservice:
                        microservice["persistent_volumes"] = []

                    # TODO: define custom based values for PVC
                    microservice["persistent_volumes"].append(
                        {
                            "name": f"volume-{index}",
                            "labels": [],
                            "storage_class": None,
                            "access_modes": None,
                            "resources": None,
                        }
                    )  # type: ignore
                if "volume_mounts" not in microservice:
                    microservice["volume_mounts"] = []
                microservice["volume_mounts"].append(
                    {"name": f"volume-{index}", "mountPath": volume.value}
                )
                if "volumes" not in microservice:
                    microservice["volumes"] = []

                    volume_to_add: Dict[str, Any] = {"name": f"volume-{index}"}
                    if volume.is_persistent:
                        volume_to_add["persistentVolumeClaim"] = {
                            "claimName": f"volume-{index}"
                        }
                    else:
                        volume_to_add["emptyDir"] = {}
                    microservice["volumes"].append(volume)

        if len(ports := node.get_children_by_type(NodeType.PORT)) > 0:
            if "ports" not in microservice:
                microservice["ports"] = []
            for port in ports:
                microservice["ports"].append(port)
        if len(wordirs := node.get_children_by_type(NodeType.WORKDIR)) > 0:
            # There's a unique child working dir
            microservice["workingDir"] = wordirs[0].value

        if service_extra_info is not None:
            microservice["workload"] = service_extra_info["workload"]
            microservice["service-ports"] = service_extra_info["ports"]
            microservice["protocol"] = service_extra_info["protocol"]
            microservice["type"] = service_extra_info["serviceType"]

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
