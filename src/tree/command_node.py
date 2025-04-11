from typing import List
from .node import Node
from .node_types import NodeType

class CommandNode(Node):
    def __init__(self, name: str, type: NodeType, command: List[str], args: List[str] = None):
        super().__init__(name, type)
        self.command = command
        self.args = args or []