from tree.node import Node


class Microservice(Node):
    def __init__(self, name, type):
        super().__init__(name, type)
        self.children: list[Node] = []

    def add_child(self, child: Node) -> None:
        """Add a child node to the microservice."""
        self.children.append(child)
        child.parent = self
        # Add the child node to the microservice's children list
        # and set its parent to the microservice

    def add_children(self, children: list[Node]) -> None:
        """Add multiple child nodes to the microservice."""
        self.children.extend(children)
        for child in children:
            child.parent = self
        # Add the child nodes to the microservice's children list
        # and set their parent to the microservice

    def __repr__(self):
        return f"Microservice(name={self.name}, type={self.type}, parent={self.parent})"

    def __str__(self):
        return f"Microservice(name={self.name}, type={self.type}, parent={self.parent})"

    def __eq__(self, other):
        if not isinstance(other, Microservice):
            return False
        return (
            self.name == other.name
            and self.type == other.type
            and self.parent == other.parent
        )

    def __hash__(self):
        return hash((self.name, self.type, self.parent))

    def to_dict(self):
        return {
            "name": self.name,
            "type": self.type,
            "parent": self.parent,
        }

    def from_dict(data):
        microservice = Microservice(data["name"], data["type"])
        return microservice
