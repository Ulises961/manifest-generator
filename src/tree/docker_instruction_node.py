from typing import List, Optional
from tree.node import Node


class DockerInstruction(Node):
    def __init__(
        self,
        name: str,
        type: str,
        value: str| List[str],
        parent: Optional["Node"] = None,
        is_persistent: bool = False,
        metadata: Optional[dict] = None,
    ):

        super().__init__(name, type, value, parent, metadata)
        self.is_persistent = is_persistent

    def __repr__(self):
        return f"DockerInstruction(name={self.name}, type={self.type}, value={self.value} metadata={self.metadata})"

    def __str__(self):
        return f"DockerInstruction(name={self.name}, type={self.type}, value={self.value} metadata={self.metadata})"

    def __eq__(self, other):
        if not isinstance(other, DockerInstruction):
            return False
        return (
            self.name == other.name
            and self.type == other.type
            and self.value == other.value
            and self.metadata == other.metadata
        )

    def __hash__(self):
        return hash((self.name, self.type, self.value))

    def to_dict(self):
        return {
            "name": self.name,
            "type": self.type,
            "value": self.value,
            "metadata": self.metadata,
        }

    def from_dict(data):
        docker_command_node = DockerInstruction(
            data["name"], data["type"], data["value"]
        )
        return docker_command_node
