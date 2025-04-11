from typing import Optional
from tree.node import Node


class DockerInstruction(Node):
    def __init__(self, name: str, type: str, command: str, parent: Optional['Node'], is_persistent: bool = False):
        
        super().__init__(name, type, parent)
        self.command = command
        self.is_persistent = is_persistent

    def __repr__(self):
        return f"DockerInstruction(name={self.name}, type={self.type}, command={self.command})"

    def __str__(self):
        return f"DockerInstruction(name={self.name}, type={self.type}, command={self.command})"
    def __eq__(self, other):
        if not isinstance(other, DockerInstruction):
            return False
        return self.name == other.name and self.type == other.type and self.command == other.command
    def __hash__(self):
        return hash((self.name, self.type, self.command))
    def to_dict(self):
        return {
            "name": self.name,
            "type": self.type,
            "command": self.command,
        }
    def from_dict(data):
        docker_command_node = DockerInstruction(data["name"], data["type"], data["command"])
        return docker_command_node