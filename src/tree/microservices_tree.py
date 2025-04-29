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
        self.env_parser: EnvParser = EnvParser(secret_classifier)
        self.command_parser: CommandMapper = CommandMapper(
            label_classifier, self.env_parser
        )
        self.bash_parser: BashScriptParser = BashScriptParser(
            secret_classifier, self.env_parser, embeddings_engine
        )

        self.logger = logging.getLogger(__name__)

    def build(self) -> Node:
        root_node = Node(name=os.path.basename(self.root_path), type=NodeType.ROOT)
        self.logger.info(f"Scanning directory: {self.root_path}")
        # Only scan top-level directories
        for item in os.listdir(self.root_path):
            item_path = os.path.join(self.root_path, item)
            if os.path.isdir(item_path):
                if str(item).startswith("."):
                    self.logger.info(f"Skipping hidden directory: {item}")
                    continue
                else:
                    self.logger.info(f"Scanning directory: {item_path}")
                    self._scan_helper(item_path, root_node, item)
        self.logger.info(
            f"Finished scanning directory: {self.root_path}, found {len(root_node.children)} microservices."
        )
        return root_node

    def _scan_helper(self, path: str, parent: Node, dir_name: str) -> None:
        """Scan the directory for microservices and find Dockerfile."""
        # Only check files in the current directory, not recursively
        files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f))]

        # Check if there's a Dockerfile in this directory
        dockerfile_found = False
        microservice_node = None

        for file in files:
            if file.endswith(".dockerfile") or file == "Dockerfile":
                dockerfile_found = True
                self.logger.info(f"Found Dockerfile in {os.path.join(path, file)}")
                # Generate a new node parent
                microservice_node = Node(
                    name=dir_name, type=NodeType.MICROSERVICE, parent=parent
                )

                # Add the microservice node to the parent node
                parent.add_child(microservice_node)
                self.logger.debug(
                    f"Adding microservice node: {microservice_node.name} to parent: {parent.name}"
                )
                # Parse Dockerfile and add commands as children to the microservice node
                commands = self.command_parser.parse_dockerfile(
                    os.path.join(path, file)
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
                                self.logger.debug(
                                    f"Removing old WORKDIR node: {child.name}"
                                )
                                microservice_node.children.remove(child)

                    if node.metadata == {} or node.metadata["status"] == "active":
                        self.logger.debug(
                            f"Adding command node: {node.name} with metadata: {node.metadata}"
                        )
                        microservice_node.add_child(node)

                break  # Stop looking for more Dockerfiles in this directory

        # Only process environment files and scripts if a Dockerfile was found
        if dockerfile_found and microservice_node is not None:
            # Parse the directory for .env files (only in this directory)
            for file in files:
                # Skip hidden files except .env
                if str(file).startswith("."):
                    if file == ".env":
                        # Parse env file and add vars as children to root node
                        env_nodes = self.env_parser.parse(os.path.join(path, file))
                        # Add env node to microservice node
                        microservice_node.add_children(env_nodes)

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
                self.logger.info(f"Scanning directory: {subdir_path}")
                # Use a subdirectory name that combines parent and child for clarity
                self._scan_helper(subdir_path, parent, subdir)

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
        microservice.setdefault("labels", ["app: " + node.name])

        if len(labels := node.get_children_by_type(NodeType.LABEL)) > 0:

            for label in labels:
                microservice["labels"].append(label.value)  # type: ignore
        if len(annotations := node.get_children_by_type(NodeType.ANNOTATION)) > 0:
            microservice.setdefault("annotations", [])
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
            microservice["command"] = entrypoint[0].value

        if len(cmd := node.get_children_by_type(NodeType.CMD, must_be_active=True)) > 0:
            # There's a unique command. Possibly none
            microservice["args"] = cmd[0].value

        microservice.setdefault("ports", set())

        if (
            len(ports := node.get_children_by_type(NodeType.PORT, must_be_active=True))
            > 0
        ):
            microservice["ports"] = [int(port.value) for port in ports]
            microservice["service-ports"] = [int(port.value) for port in ports]
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

        if len(wordirs := node.get_children_by_type(NodeType.WORKDIR)) > 0:
            # There's a unique child working dir
            microservice["workingDir"] = wordirs[0].value

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
            microservice["service-ports"] = service_extra_info.get("servicePorts", container_ports)           

            # Only use ontology ports of not set in the container configuration
            if len(microservice["ports"]) == 0:
                microservice["ports"] = container_ports

            for label in service_extra_info["labels"]:
                microservice["labels"].append(label)

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
