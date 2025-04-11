from enum import Enum
import json
import os
from typing import List, Optional
from tree.command_mapper import CommandMapper
from embeddings.embeddings_engine import EmbeddingsEngine

from embeddings.label_classifier import LabelClassifier
from embeddings.secret_classifier import SecretClassifier
from embeddings.service_classifier import ServiceClassifier
from tree.command_node import CommandNode
from tree.node_types import NodeType
from tree.node import Node
from tree.env_node import EnvNode
from tree.microservice_node import Microservice
from parsers.bash_parser import BashScriptParser


class MicroservicesTree:
    def __init__(
        self,
        root_path: str,
        emeddings_engine: EmbeddingsEngine,
        secret_classifier: SecretClassifier,
        service_classifier: ServiceClassifier,
        label_classifier: LabelClassifier,
    ):
        self.root_path = root_path
        self.root: Node = None
        self.embeddings_engine: EmbeddingsEngine = emeddings_engine
        self.secret_classifier = secret_classifier
        self.service_classifier = service_classifier
        self.command_parser: CommandMapper = CommandMapper(label_classifier)
        self.bash_parser: BashScriptParser = BashScriptParser(secret_classifier)

    def build(self) -> Node:
        # Placeholder for scanning logic
        print(f"Scanning repository at {self.root_path}...")

        for root, dirs, _ in os.walk(self.root_path, topdown=True):
            # Generate root node
            curr_dir = os.path.basename(root)
            self.root_node = Node(name=curr_dir, type=NodeType.ROOT)

            for dir in dirs:
                if str(dir).startswith("."):
                    continue
                else:
                    self._scan_helper(os.path.join(root, dir), self.root_node, dir)
        return self.root_node

    def _scan_helper(self, path: str, parent: Node, dir_name: str) -> None:
        """Recursively scan the directory for microservices and their dependencies."""

        for root, _, files in os.walk(path):

            # Scan the directory for dockerfiles, if present we assume a microservice
            is_microservice = False
            microservice_node: Optional[Node] = None

            for file in files:
                if file.endswith(".dockerfile") or file == "Dockerfile":

                    # Generate a new node parent
                    microservice_node = Microservice(
                        name=dir_name, type=NodeType.MICROSERVICE
                    )

                    # Add the microservice node to the parent node
                    parent.add_child(microservice_node)

                    # Parse Dockerfile and add commands as children to the microservice node
                    commands = self.command_parser.parse_dockerfile(
                        os.path.join(root, file)
                    )
                    command_nodes = [
                        self.command_parser.generate_node_from_command(command)
                        for command in commands
                    ]
                    microservice_node.add_children(command_nodes)
                    is_microservice = True
                    break

            # Only parse the directory if it is a microservice
            if is_microservice and microservice_node is not None:
                for file in files:
                    # Skip hidden files except .env
                    if str(file).startswith("."):
                        if file == ".env":
                            # Parse env file and add vars as children to root node
                            self._parse_env_file(
                                os.path.join(root, file), microservice_node
                            )
                            continue

            # Parse bash scripts if present in EntryPoint or CMD
            self._find_and_parse_startup_script(root, files, microservice_node)



    def _find_and_parse_startup_script(self, root: str, files: List[str], parent: Node) -> None:
        """Find and parse potential startup scripts."""
        script_path = self.bash_parser.find_startup_script(root, files)
        if script_path:
            nodes = self.bash_parser.parse_script(script_path)
            for node in nodes:
                parent.add_child(node)