from typing import List, Dict, Optional
import re
import os
import shlex
from tree.node import Node
from tree.node_types import NodeType
from tree.env_node import EnvNode
from tree.command_node import CommandNode
from tree.docker_instruction_node import DockerInstruction
from embeddings.secret_classifier import SecretClassifier

class BashScriptParser:
    """Parser for bash scripts that modify container runtime environment."""
    
    def __init__(self, secret_classifier: SecretClassifier):
        self.secret_classifier = secret_classifier
        self.startup_script_names = ["start.sh", "entrypoint.sh", "run.sh", "serve.sh"]
        self.startup_keywords = ["start", "run", "serve", "launch", "init"]

    def find_startup_script(self, root: str, files: List[str]) -> Optional[str]:
        """Find an appropriate startup script in the given files."""
        # First try exact matches
        for script in self.startup_script_names:
            if script in files:
                return os.path.join(root, script)

        # Then try semantic matching
        for file in files:
            if file.endswith(".sh"):
                if self.service_classifier.is_startup_script(file, self.startup_keywords):
                    return os.path.join(root, file)
        
        return None

    def parse_script(self, path: str) -> List[Node]:
        """Parse a bash script and return its nodes."""
        with open(path, "r") as f:
            content = f.read()
            
        return self._parse_script_content(content)

    def _parse_script_content(self, content: str) -> List[Node]:
        """Parse bash script content and return nodes."""
        nodes: List[Node] = []
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            if env_node := self._parse_env_var(line):
                nodes.append(env_node)
                
            # Check for volume mounts
            elif mount_node := self._parse_mount(line):
                nodes.append(mount_node)
                
            # Check for command overrides
            elif cmd_node := self._parse_command(line):
                nodes.append(cmd_node)
                
        return nodes

    def _parse_env_var(self, line: str) -> Optional[EnvNode]:
        """Parse environment variable declarations."""
        if line.startswith('export'):
            parts = line.split('=', 1)
            if len(parts) == 2:
                name = parts[0].replace('export', '').strip()
                value = parts[1].strip().strip('"\'')
                
                is_secret = self.secret_classifier.decide_secret(f"{name}={value}")
                node_type = NodeType.SECRET if is_secret else NodeType.ENV
                
                if is_secret:
                    value = str.encode(value, encoding="base64")
                    
                return EnvNode(name=name, type=node_type, value=value)
        return None

    def _parse_command(self, line: str) -> Optional[CommandNode]:
        """Parse command declarations."""
        normalized = self._normalize_command(line)
        if normalized:
            return CommandNode(
                name="script_command",
                type=NodeType.COMMAND,
                command=normalized,
                args=[]
            )
        return None
    
    def _parse_mount(self, line: str) -> Optional[Node]:
        """Parse mount commands and volume definitions."""
        match = re.match(self.patterns['mount'], line)
        if match:
            _, mount_path = match.groups()
            return Node(
                name=f"mount_{mount_path.split('/')[-1]}",
                type=NodeType.VOLUME,
                value=mount_path
            )
        return None

    def _normalize_command(self, cmd: str) -> List[str]:
        """Convert shell form command to exec form."""
        try:
            return shlex.split(cmd)
        except ValueError:
            return []
        
    def _determine_startup_command(
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
            self._parse_command_as_entrypoint(root, cmd, microservice_node)

        # Case 3: Only ENTRYPOINT
        elif NodeType.ENTRYPOINT in entrypoint_nodes:
            entrypoint = entrypoint_nodes[NodeType.ENTRYPOINT]
            self._parse_command_as_entrypoint(root, entrypoint, microservice_node)

        # Case 4: Neither - look for startup scripts
        else:
            self._find_and_parse_startup_script(root, files, microservice_node)

    def _parse_command_pair(
        self, root: str, entrypoint: Node, cmd: Node, parent: Node
    ) -> None:
        """Parse ENTRYPOINT + CMD combination."""
        if entrypoint.value.endswith(".sh"):
            self._parse_bash_script(os.path.join(root, entrypoint.value), parent)
        else:
            # Create command node with entrypoint as command and cmd as args
            command_node = CommandNode(
                name="startup",
                type=NodeType.COMMAND,
                command=self._normalize_command(entrypoint.value),
                args=self._normalize_command(cmd.value),
            )
            parent.add_child(command_node)

    def _parse_command_as_entrypoint(self, root: str, cmd: Node, parent: Node) -> None:
        """Parse single command as entrypoint."""
        if cmd.value.endswith(".sh"):
            self._parse_bash_script(os.path.join(root, cmd.value), parent)
        else:
            command_node = CommandNode(
                name="startup",
                type=NodeType.COMMAND,
                command=self._normalize_command(cmd.value),
                args=[],
            )
            parent.add_child(command_node)