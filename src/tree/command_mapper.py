import json
import os
from typing import  List
from dockerfile_parse import DockerfileParser
from embeddings.label_classifier import LabelClassifier
from tree.docker_instruction_node import DockerInstruction
from tree.node import Node
from tree.node_types import NodeType


class CommandMapper:
    """Class to classify Dockerfile commands."""

    def __init__(self, label_classifier: LabelClassifier):
        self._label_classifier = label_classifier

    DOCKER_COMMANDS: List[str] = [
        "CMD",
        "LABEL",
        "EXPOSE",
        "ENTRYPOINT",
        "VOLUME",
        "USER",
        "WORKDIR",
        "HEALTHCHECK",
        "STOPSIGNAL",
    ]

    def parse_dockerfile(self, file_name: str) -> List[dict]:
        """Read a Dockerfile and return the list of runtime commands present in the file.
        Args:
            file_name (str): Path to the Dockerfile.
        Returns:
            list[dict]: List of dict representing the filtered commands from the Dockerfile.
        """
        # Create a DockerfileParser object
        parser: DockerfileParser = DockerfileParser(path=file_name)
        dockerfile: List[dict] = [
            command
            for command in parser.structure
            if command["instruction"] in self.DOCKER_COMMANDS
        ]
        return dockerfile

    def get_commands(self, parsed_dockerfile: List[dict], parent: Node) -> List[DockerInstruction]:
        """Get the list of commands from a parsed Dockerfile.
        Args:
            parsed_dockerfile (list[dict]): Parsed Dockerfile.
        Returns:
            list[dict]: List of commands from the Dockerfile.
        """
         
        return [
            self.generate_node_from_command(command, parent)
            for command in parsed_dockerfile
        ]

    def generate_node_from_command(self, command: dict, parent: Node) -> DockerInstruction:
        """Generate a node from a Dockerfile command.
        Args:
            command (dict): Dockerfile command.
        Returns:
            dict: Node representing the command.
        """
        instruction = command["instruction"]

        switch = {
            "CMD": self._generate_cmd_node,
            "LABEL": self._generate_label_node,
            "EXPOSE": self._generate_expose_node,
            "ENTRYPOINT": self._generate_entrypoint_node,
            "VOLUME": self._generate_volume_node,
            "USER": self._generate_user_node,
            "WORKDIR": self._generate_workdir_node,
            "HEALTHCHECK": self._generate_healthcheck_node,
            "STOPSIGNAL": self._generate_stopsignal_node,
        }

        # Only filtered commands are passed as argument so the lambda is never executed
        return switch.get(instruction, lambda x: None)(command, parent)

    def _generate_cmd_node(self, command: dict, parent: Node) -> DockerInstruction:
        """Generate a node from a CMD command."""
        return self._create_docker_node(command, NodeType.CMD, parent)

    def _generate_label_node(self, command: dict, parent: Node) -> DockerInstruction:
        """Generate a node from a LABEL command."""
        is_label = self.decide_label(command["value"])

        return self._create_docker_node(command, NodeType.LABEL if is_label else NodeType.ANNOTATION, parent)
      

    def _generate_expose_node(self, command: dict, parent: Node) -> DockerInstruction:
        """Generate a node from an EXPOSE command."""
        return {"type": "PORTS", "command": command["value"]}
    
    def _generate_entrypoint_node(self, command: dict, parent: Node) -> DockerInstruction:
        """Generate a node from an ENTRYPOINT command."""
        return self._create_docker_node(command, NodeType.ENTRYPOINT, parent)
    
    def _generate_volume_node(self, command: dict, parent: Node) -> DockerInstruction:
        """Generate a node from a VOLUME command."""
        # Check if the volume is persistent
        volumes_path = os.path.join(os.path.dirname(__file__),"..", os.getenv("VOLUMES_PATH"))
        with open(volumes_path, "r") as f:
            volumes = json.load(f)

        is_persistent = command["value"] in volumes 
        return self._create_docker_node(command, NodeType.VOLUME, parent, is_persistent=is_persistent)
    
    def _generate_user_node(self, command: dict, parent: Node) -> DockerInstruction:
        """Generate a node from a USER command."""
        return self._create_docker_node(command, NodeType.USER, parent)
    
    def _generate_workdir_node(self, command: dict, parent: Node) -> DockerInstruction:
        """Generate a node from a WORKDIR command."""
        return self._create_docker_node(command, NodeType.WORKDIR, parent)
    
    def _generate_healthcheck_node(self, command: dict, parent: Node) -> DockerInstruction:
        """Generate a node from a HEALTHCHECK command."""
        return self._create_docker_node(command, NodeType.HEALTHCHECK, parent)
    
    def _generate_stopsignal_node(self, command: dict, parent: Node) -> DockerInstruction:
        """Generate a node from a STOPSIGNAL command."""
        return self._create_docker_node(command, NodeType.STOPSIGNAL, parent)
    
    
    def decide_label(self, label_key: str) -> bool:
        classified_label = self._label_classifier.classify_label(label_key)
        return classified_label == "label"
    

    def _create_docker_node(self, command: dict, type: NodeType, parent:  Node, is_persistent: bool = False) -> DockerInstruction:
        """Create a DockerInstruction from a command."""
        return DockerInstruction(
            name=command["instruction"],
            type=type,
            value=command["value"],
            parent=parent,
            is_persistent=is_persistent,
        )
