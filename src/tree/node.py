import json
from typing import Any, Dict, List, Optional, Sequence

from tree.attached_file import AttachedFile
from tree.node_types import NodeType

class Node:
    def __init__(
        self,
        name: str,
        type: NodeType,
        value: Optional[str] | Optional[List[str]] | Optional[bytes] = None,
        parent: Optional["Node"] = None,
        metadata: Dict[str, Any] = {},
        is_persistent: bool = False,

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
        self._value: Optional[str] | Optional[List[str]] | Optional[bytes]  = value
        self.parent: Optional["Node"] = parent
        self.children: List[Node] = []
        self.is_persistent: bool = is_persistent
        self._metadata: Dict[str, Any] = metadata

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

    @property
    def metadata(self):
        return self._metadata

    @metadata.setter
    def metadata(self, metadata):
        if isinstance(metadata, dict):
            self._metadata = metadata
        elif metadata is None:
            self._metadata = {}
        else:
            raise ValueError("Metadata must be a dictionary or None.")

   
    def __repr__(self):
        return f"Node(name={self.name}, type={self.type}, value={self._value}, parent={self.parent.name if self.parent else None} ,children={self.children})"

    def __str__(self):
        return f"Node(name={self.name}, type={self.type}, value={self._value} parent={self.parent.name if self.parent else None}, children={self.children})"

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
            "parent": self.parent.name if self.parent else None,
            "value": self._value,
            "metadata": self.metadata,
            "children": [child.to_dict() for child in self.children],
        }

    def from_dict(self, data):
        node = Node(data["name"], data["type"])
        return node

    def to_json(self):
        return json.dumps(self.to_dict(), indent=4)

    def get_children_by_type(
        self, type: NodeType, must_be_active: Optional[bool] = False
    ) -> List["Node"]:
        """Get a child node by name."""
        return [
            child
            for child in self.children
            if child.type == type
            and (
                not must_be_active
                or (
                    child.metadata is not {}
                    and child.metadata.setdefault("status", "active") == "active"
                )
            )
        ]
