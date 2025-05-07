import json
import os
import re
import shlex
from typing import Any, Dict, List, Optional
from dockerfile_parse import DockerfileParser
from embeddings.label_classifier import LabelClassifier
from parsers.env_parser import EnvParser

from tree.node import Node
from tree.node_types import NodeType
from utils.docker_utils import (
    normalize_multiline,
    normalize_spaced_values,
    parse_key_value_string,
)
from utils.file_utils import  normalize_command_field
import itertools


class CommandMapper:
    """Class to classify Dockerfile commands."""

    def __init__(self, label_classifier: LabelClassifier, env_parser: EnvParser):
        self._label_classifier = label_classifier
        self._env_parser = env_parser

    DOCKER_COMMANDS: List[str] = [
        "CMD",
        "LABEL",
        "EXPOSE",
        "ENTRYPOINT",
        "VOLUME",
        "ENV",
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
            dict(command)
            for command in parser.structure
            if command["instruction"] in self.DOCKER_COMMANDS
        ]

        return dockerfile

    def get_commands(
        self, parsed_dockerfile: List[dict], parent: Node
    ) -> List[Node]:
        """Get the list of commands from a parsed Dockerfile.
        Args:
            parsed_dockerfile (list[dict]): Parsed Dockerfile.
        Returns:
            list[dict]: List of commands from the Dockerfile.
        """

        commands = [
            self.generate_node_from_command(command, parent)
            for command in parsed_dockerfile
        ]
        return list(itertools.chain.from_iterable(commands))

    def generate_node_from_command(
        self, command: dict, parent: Node
    ) -> List[Node]:
        """Generate a node from a Dockerfile command.
        Args:
            command (dict): Dockerfile command.
        Returns:
            dict: Node representing the command.
        """
        instruction = command["instruction"]

        match instruction:
            case "CMD":
                return self._generate_cmd_nodes(command, parent)
            case "LABEL":
                return self._generate_label_nodes(command, parent)
            case "EXPOSE":
                return self._generate_expose_nodes(command, parent)
            case "ENTRYPOINT":
                return self._generate_entrypoint_nodes(command, parent)
            case "VOLUME":
                return self._generate_volume_nodes(command, parent)
            case "USER":
                return self._generate_user_nodes(command, parent)
            case "WORKDIR":
                return self._generate_workdir_nodes(command, parent)
            case "HEALTHCHECK":
                return self._generate_healthcheck_nodes(command, parent)
            case "ENV":
                return self.generate_env_nodes(command, parent)

        return []

    def _generate_entrypoint_nodes(
        self, command: dict, parent: Node
    ) -> List[Node]:
        """Generate a node from an ENTRYPOINT command."""
        return [self._generate_command_node(command, NodeType.ENTRYPOINT, parent)]

    def _generate_cmd_nodes(
        self, command: dict, parent: Node
    ) -> List[Node]:
        """Generate a node from a CMD command."""
        return [self._generate_command_node(command, NodeType.CMD, parent)]

    def _generate_command_node(
        self,
        command: dict,
        node_type: NodeType,
        parent: Node,
    ) -> Node:
        """Generalized generator for CMD or ENTRYPOINT."""
        value = normalize_command_field(command["value"])

        command["value"] = value

        return self._create_node(command, node_type, parent)

    def _generate_label_nodes(
        self, command: dict, parent: Node
    ) -> List[Node]:
        """Generate a node from a LABEL command."""
        nodes = []
        labels_dict = parse_key_value_string(command["value"])
        for key, value in labels_dict.items():
            is_label = self.decide_label(key)
            nodes.append(
                self._create_node(
                    {"instruction": key, "value": value},
                    NodeType.LABEL if is_label else NodeType.ANNOTATION,
                    parent,
                )
            )
        return nodes

    def _generate_expose_nodes(
        self, command: dict, parent: Node
    ) -> List[Node]:
        """Generate a node from an PORT command."""
        nodes = []
        ports = normalize_spaced_values(command["value"])
        for port in ports:
            nodes.append(
                self._create_node(
                    {"instruction": "PORT", "value": port}, NodeType.PORT, parent
                )
            )
        return nodes

    def _generate_volume_nodes(
        self, command: dict, parent: Node
    ) -> List[Node]:
        """Generate a node from a VOLUME command."""
        nodes = []
        # Normalize the command value
        normalized_volume_paths = normalize_spaced_values(command["value"])
        for volume_path in normalized_volume_paths:
            # Check if the volume is persistent
            volumes_path = os.path.join(
                os.path.dirname(__file__),
                "..",
                os.getenv("VOLUMES_PATH", "resources/knowledge_base/volumes.json"),
            )
            with open(volumes_path, "r") as f:
                volumes = json.load(f)

            is_persistent = volume_path in volumes

            nodes.append(
                self._create_node(
                    {"instruction": "VOLUME", "value": volume_path},
                    NodeType.VOLUME,
                    parent,
                    is_persistent=is_persistent,
                )
            )
        return nodes

    def _generate_user_nodes(
        self, command: dict, parent: Node
    ) -> List[Node]:
        """Generate a node from a USER command."""
        return [self._create_node(command, NodeType.USER, parent)]

    def _generate_workdir_nodes(
        self, command: dict, parent: Node
    ) -> List[Node]:
        """Generate a node from a WORKDIR command."""
        return [self._create_node(command, NodeType.WORKDIR, parent)]

    def _generate_healthcheck_nodes(
        self, command: dict, parent: Node
    ) -> List[Node]:
        """Generate a node from a HEALTHCHECK command."""
        healthcheck = normalize_multiline(command["value"])
        parsed_check = self._parse_healthcheck(healthcheck)
        command["value"] = parsed_check["check"]
        node = self._create_node(command, NodeType.HEALTHCHECK, parent)
        node.metadata = {"flags": parsed_check["flags"]}
        return [node]

    def decide_label(self, label_key: str) -> bool:
        classified_label = self._label_classifier.classify_label(label_key)
        return classified_label == "label"

    def generate_env_nodes(
        self, command: dict, parent: Node
    ) -> List[Node]:
        return self._env_parser.parse_env_var(command["value"])

    

    def _create_node(
        self, command: dict, type: NodeType, parent: Node, is_persistent: bool = False
    ) -> Node:
        """Create a Node from a command."""
        return Node(
            name=command["instruction"],
            type=type,
            value=command["value"],
            parent=parent,
            is_persistent=is_persistent,
        )

    def _parse_healthcheck(self, command: str) -> Dict[str, Any]:
        if "HEALTHCHECK NONE" in command:
            return {"disabled": True}

        healthcheck: Dict[str, Any] = {}

        # Extract flags and the actual CMD part
        cmd_match = re.search(r"(CMD|CMD-SHELL)\s+(.*)", command)
        if not cmd_match:
            raise ValueError(f"Invalid HEALTHCHECK command format: {command}")

        action = cmd_match.group(2).strip()

        if action.startswith("["):
            try:
                parsed_action = json.loads(action)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid exec form CMD array: {action}")
            # Join array to shell string for Kubernetes
            healthcheck["check"] = (
                '/bin/sh -c "' + " ".join(shlex.quote(a) for a in parsed_action) + '"'
            )
        else:
            # Treat as already a shell string
            healthcheck["check"] = action

        # Docker / Kubernetes flags mapping
        key_map = {
            "interval": "periodSeconds",
            "timeout": "timeoutSeconds",
            "start-period": "initialDelaySeconds",
            "retries": "failureThreshold",
        }

        # Extract all flags
        flags = re.findall(r"--(\w[\w-]*)=([\wsm]+)", command)

        for key, value in flags:
            if key in key_map:
                # Convert seconds like '10s' or '1m' to int seconds
                if value.endswith("s"):
                    val = int(value[:-1])
                elif value.endswith("m"):
                    val = int(value[:-1]) * 60
                else:
                    val = int(value)

                # Group flags under a unique key for later manipulation
                healthcheck.setdefault("flags", {})[key_map[key]] = val

        return healthcheck
