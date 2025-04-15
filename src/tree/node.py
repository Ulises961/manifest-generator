import json
from typing import List, Optional, Sequence

from tree.node_types import NodeType


class Node:
    def __init__(
        self,
        name: str,
        type: NodeType,
        value: Optional[str] | Optional[List[str]] = None,
        parent: Optional["Node"] = None,
        metadata: Optional[dict] = None,
    ):
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
        self.value: Optional[str] | Optional[List[str]] = value
        self.parent: Optional["Node"] = parent
        self.children: List[Node] = []
        self.metadata: Optional[dict] = metadata

    def add_child(self, child: "Node") -> None:
        self.children.append(child)
        child.parent = self

    def add_children(self, children: Sequence["Node"]) -> None:
        self.children.extend(children)
        for child in children:
            child.parent = self

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        if isinstance(value, str):
            self._value = value
        elif isinstance(value, list):
            self._value = value
        elif value is None:
            self._value = None
        else:
            raise ValueError("Value must be a string or a list of strings.")

    def __repr__(self):
        return f"Node(name={self.name}, type={self.type}, value={self._value}, parent={self.parent} ,children={self.children})"

    def __str__(self):
        return f"Node(name={self.name}, type={self.type}, value={self._value} parent={self.parent}, children={self.children})"

    def __eq__(self, other):
        if not isinstance(other, Node):
            return False
        return (
            self.name == other.name
            and self.type == other.type
            and self._value == other.value
            and self.parent == other.parent
        )

    def __hash__(self):
        return hash((self.name, self.type, self._value, self.parent))

    def to_dict(self):
        return {
            "name": self.name,
            "type": self.type,
            "parent": self.parent,
        }

    def from_dict(data):
        node = Node(data["name"], data["type"])
        return node
