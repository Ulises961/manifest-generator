import json
from typing import List, Optional

from tree.node_types import NodeType


class Node:
    def __init__(self, name: str, type: NodeType, parent: Optional['Node']=None, metadata: Optional[dict]=None):
        """
        Initialize a Node instance.
        Args:
            name (str): The name of the node.
            type (NodeType): The type of the node.
            parent (Optional[Node]): The parent node. Default is None.
            metadata (Optional[dict]): Additional metadata. Default is None.
        """
        self.name: str = name
        self.type: NodeType = type
        self.parent: Optional['Node'] = parent
        self.children: List[Node] = []
        self.medatada: Optional[dict] = metadata
    
    def add_child(self, child: 'Node') -> None:  # Add this missing method
        self.children.append(child)
        child.parent = self

    def add_children(self, children: List['Node']) -> None:
        self.children.extend(children)
        for child in children:
            child.parent = self
    
    def __repr__(self):
        return f"Node(name={self.name}, type={self.type}, parent={self.parent})"

    def __str__(self):
        return f"Node(name={self.name}, type={self.type}, parent={self.parent})"

    def __eq__(self, other):
        if not isinstance(other, Node):
            return False
        return self.name == other.name and self.type == other.type and self.parent == other.parent

    def __hash__(self):
        return hash((self.name, self.type, self.parent))

    def to_dict(self):
        return {
            "name": self.name,
            "type": self.type,
            "parent": self.parent,
        }

    def from_dict(data):
        node = Node(data["name"], data["type"])
        return node

    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)

    def from_json(json_str):
        data = json.loads(json_str)
        return Node.from_dict(data)
