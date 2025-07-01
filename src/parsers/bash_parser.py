from typing import List, Dict, Optional, Tuple, cast
import re
import os
from embeddings.embeddings_client import EmbeddingsClient
from parsers.env_parser import EnvParser
from tree.node import Node
from tree.node_types import NodeType

from embeddings.secret_classifier import SecretClassifier
from utils.file_utils import normalize_command_field


class BashScriptParser:
    """Parser for bash scripts that modify container runtime environment."""

    def __init__(
        self,
        secret_classifier: SecretClassifier,
        env_parser: EnvParser,
        embeddings_engine: EmbeddingsEngine,
    ):
        self._engine = embeddings_engine
        self.secret_classifier = secret_classifier
        self.startup_script_names = ["start.sh", "entrypoint.sh", "run.sh", "serve.sh"]
        self.env_parser = env_parser

        self.patterns = {
            "mount": r"mount\s+(-t\s+\w+\s+)?([^#\n]+)",
            "kubectl": r"kubectl\s+([^#\n]+)",
            "docker": r"docker\s+run\s+([^#\n]+)",
            "source": r"(source|\.)\s+([^\s#\n]+)",
            "exec": r"exec\s+([^#\n]+)",
        }

    def determine_startup_command(
        self, root: str, files: List[str], microservice_node: Node
    ) -> None:
        """Determine and parse the appropriate startup command."""
        entrypoint_nodes = {
            node.type: node
            for node in microservice_node.children
            if node.type in [NodeType.ENTRYPOINT, NodeType.CMD]
        }

        # Case 1: Both ENTRYPOINT and CMD
        if NodeType.ENTRYPOINT in entrypoint_nodes and NodeType.CMD in entrypoint_nodes:
            entrypoint = entrypoint_nodes[NodeType.ENTRYPOINT]
            cmd = entrypoint_nodes[NodeType.CMD]
            self._parse_command_pair(root, entrypoint, cmd, microservice_node)

        # Case 2: Only CMD
        elif NodeType.CMD in entrypoint_nodes:
            cmd = entrypoint_nodes[NodeType.CMD]
            self._parse_command_as_entrypoint(root, None, cmd, microservice_node)

        # Case 3: Only ENTRYPOINT
        elif NodeType.ENTRYPOINT in entrypoint_nodes:
            entrypoint = entrypoint_nodes[NodeType.ENTRYPOINT]
            self._parse_command_as_entrypoint(root, entrypoint, None, microservice_node)

        # Case 4: Neither - look for startup scripts
        else:
            self._find_and_parse_startup_script(root, files, microservice_node)

    def _find_and_parse_startup_script(
        self, root: str, files: List[str], parent: Node
    ) -> None:
        """Find and parse potential startup scripts."""
        # Determine the startup script based on the dockerfile instructions
        # (ENTRYPOINT, CMD) and parse it
        # Check for ENTRYPOINT or CMD in the dockerfile
        script_path = self._find_startup_script(root, files)
        if script_path:
            nodes = self.parse_script(script_path, None, None, parent)
            for node in nodes:
                parent.add_child(node)

    def _find_startup_script(self, root: str, files: List[str]) -> Optional[str]:
        """Find an appropriate startup script in the given files."""

        # First try exact matches
        for script in self.startup_script_names:
            if script in files:
                return os.path.join(root, script)

        # Then try semantic matching
        for file in files:
            if file.endswith(".sh"):
                file_name = self._engine.encode(file)
                for script in self.startup_script_names:
                    script_name = self._engine.encode(script)
                    similarity = self._engine.compute_similarity(file_name, script_name)
                    if similarity > 0.8:
                        # Assuming the script is a potential startup script
                        return os.path.join(root, file)
        return None

    def parse_script(
        self,
        path: str,
        original_entrypoint: Optional[Node],
        original_cmd: Optional[Node],
        parent: Node,
    ) -> List[Node]:
        """Parse a bash script and return its nodes."""
        with open(path, "r") as f:
            content = f.read()

        return self._parse_script_content(
            path, content, original_entrypoint, original_cmd, parent
        )

    def _parse_script_content(
        self,
        path: str,
        content: str,
        original_entrypoint: Optional[Node],
        original_cmd: Optional[Node],
        parent: Node,
    ) -> List[Node]:
        """Parse bash script content and return nodes."""
        nodes: List[Node] = []
        lines = content.split("\n")

        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Early exit if the script contains orchestration logic
            if self._is_orchestrator_line(line):
                parent.metadata["review"] = (
                    "Script contains orchestration logic (kubectl/docker). Manual inspection required."
                )
                parent.metadata["offending_line"] = line
                parent.metadata["parser_hint"] = (
                    "Skipped deeper parsing to avoid incorrect assumptions."
                )
                parent.metadata["status"] = "skipped"
                return nodes  # Return early without parsing the rest

            # Check for secret detection
            if env_node := self._parse_env_var(line):
                nodes.append(env_node)

            # Check for mount commands
            elif mount_node := self._parse_mount(line):
                nodes.append(mount_node)

            # Check for command or entrypoint
            elif cmd_nodes := self._parse_command(line, parent):
                entry, args = cmd_nodes
                # Check if $@ is *not* in args → means it's not forwarding the original CMD
                if args:
                    if original_cmd:
                        original_cmd.metadata["review"] = (
                            "Overridden by bash script. Manual inspection might be required."
                        )

                        original_cmd.metadata["parser_hint"] = (
                            "Script entrypoint detected. Original CMD marked for review."
                        )

                        original_cmd.metadata["status"] = "overridden"

                    nodes.extend([args])

                # Mark the original ENTRYPOINT for later inspection
                if entry:
                    if original_entrypoint:
                        original_entrypoint.metadata["review"] = (
                            "Overridden by bash script. Manual inspection might be required."
                        )
                        original_entrypoint.metadata["original_entrypoint"] = (
                            entry.value
                        )
                        original_entrypoint.metadata["parser_hint"] = (
                            "Script entrypoint detected. Original entrypoint marked for review."
                        )
                        original_entrypoint.metadata["status"] = "overridden"
                    nodes.append(entry)
            elif sourced_nodes := self._parse_source(path, line, parent):
                nodes.extend(sourced_nodes)

        return nodes

    def _parse_env_var(self, line: str) -> Optional[Node]:
        """Parse environment variable declarations."""
        if line.startswith("export"):
            parts = line.split("=", 1)
            if len(parts) == 2:
                name = parts[0].replace("export", "").strip()
                value = parts[1].strip().strip("\"'")
                return self.env_parser.create_env_node(name, value)
        return None

    def _parse_mount(self, line: str) -> Optional[Node]:
        """Parse mount commands and volume definitions."""
        match = re.match(self.patterns["mount"], line)
        if match:
            _, mount_path = match.groups()
            return Node(
                name=f"mount_{mount_path.split('/')[-1]}",
                type=NodeType.VOLUME,
                value=mount_path,
            )
        return None

    def _parse_command(
        self, line: str, parent: Node
    ) -> Tuple[Optional[Node], Optional[Node]]:
        """Parse command declarations."""
        normalized = normalize_command_field(line)
        if not normalized:
            return None, None

        command, args = self._split_command_and_args(normalized)

        forwards_args = any(token in ["$@", '"$@"', "'$@'", "${@}"] for token in args)

        entrypoint_node = Node(
            name=parent.name,
            type=NodeType.ENTRYPOINT,
            value=command,
            parent=parent,
            metadata={
                "review": "Generated from bash script",
                "source": "script",
                "full_command": normalized,
                "status": "active",
            },
        )

        cmd_node = None
        if not forwards_args and args:
            cmd_node = Node(
                name=parent.name,
                type=NodeType.CMD,
                value=args,
                parent=parent,
                metadata={
                    "review": "Generated from bash script",
                    "source": "script",
                    "full_command": normalized,
                    "status": "active",
                },
            )

        return entrypoint_node, cmd_node

    def _parse_source(
        self, dockerfile_path: str, line: str, parent: Node
    ) -> Optional[List[Node]]:
        match = re.match(self.patterns["source"], line)

        if not match:
            return None

        _, path = match.groups()
        full_path = os.path.join(os.path.basename(dockerfile_path), path)

        # The source command is a script and we have not found any entrypoint or cmd
        return self.parse_script(full_path,None, None, parent)

    def _parse_command_pair(
        self,
        root: str,
        entrypoint: Node,
        cmd: Node,
        parent: Node,
    ) -> None:
        """Parse ENTRYPOINT + CMD combination."""
        # Check if the entrypoint is a script
        for command in entrypoint.value:
            if command.endswith(".sh"):
                self.parse_script(
                    os.path.join(root, entrypoint.value), entrypoint, cmd, parent
                )
        # Other possible combination of commands are already handled by the mapper itself

    def _parse_command_as_entrypoint(
        self,
        root: str,
        original_entrypoint: Optional[Node],
        original_cmd: Optional[Node],
        parent: Node,
    ) -> None:
        """Parse single command as entrypoint."""
        if original_cmd:
            # The command needs to be run as an entrypoint
            original_cmd.type = NodeType.ENTRYPOINT
            original_cmd.metadata["status"] = "active"
            original_cmd.metadata["parser_hint"] = (
                "CMD detected. Converted to ENTRYPOINT."
            )

            # Reflect the upgrade in the references
            original_entrypoint = original_cmd
            original_cmd = None

        if original_entrypoint:
            for value in original_entrypoint.value:

                if value.endswith(".sh"):
                    original_entrypoint.metadata["parser_hint"] = (
                        "Generated from bash script"
                    )
                    self.parse_script(
                        os.path.join(root, value),
                        original_entrypoint,
                        original_cmd,
                        parent,
                    )

    def _split_command_and_args(
        self, normalized: List[str]
    ) -> tuple[List[str], List[str]]:
        """
        Splits a normalized command line into base command and its arguments.

        Example:
            ['gunicorn', 'app:main', '--bind', '0.0.0.0:8000']
            -> (['gunicorn', 'app:main'], ['--bind', '0.0.0.0:8000'])

        Heuristic: Base command ends where flags begin (starting with - or --),
        or at first "$@" which means pass-through.

        Returns:
            Tuple (command_base, arguments)
        """
        if not normalized:
            return [], []

        for i, token in enumerate(normalized):
            if token.startswith("-") or token in ["$@", '"$@"', "'$@'", "${@}"]:
                return normalized[:i], normalized[i:]

        return normalized, []

    def _is_orchestrator_line(self, line: str) -> bool:
        return any(
            re.match(self.patterns[pattern], line) for pattern in ["kubectl", "docker"]
        )

