import os
from typing import Optional, List, cast
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
        self.root: Optional[Node] = None
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
        self.root = Node(name=os.path.basename(self.root_path), type=NodeType.ROOT)

        for root, dirs, _ in os.walk(self.root_path, topdown=True):
            for dir in dirs:
                if str(dir).startswith("."):
                    continue
                else:
                    self._scan_helper(os.path.join(root, dir), self.root, dir)
        return self.root

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

                    # Parse Dockerfile and add commands as children to the microservice node
                    commands = self.command_parser.parse_dockerfile(
                        os.path.join(root, file)
                    )

                    for command in commands:
                        # Classify the command
                        node:DockerInstruction = self.command_parser.generate_node_from_command(command, microservice_node)
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

    def print_tree(self, node: Node, level: int = 0) -> None:
        """Recursively print the tree structure."""
        if level == 0:
            indent = ""
            print(f"{indent}{node.name} ({node.type})")
        else:
            indent = ""
            for i in range(level - 1):
                indent = " " * ((i+1) * 4) + "|"
            indent = indent + " " * (level * 4) + "|"
            print(f"{indent}-- {node.name} ({node.value})" if node.value is not None else f"{indent}-- {node.name}")

        for child in node.children:
            self.print_tree(child, level + 1)
