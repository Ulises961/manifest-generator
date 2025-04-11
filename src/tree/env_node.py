from tree.node import Node


class EnvNode(Node):
    def __init__(self, name, type, value):
        super().__init__(name, type)
        self.value = value

    def __repr__(self):
        return f"EnvNode(name={self.name}, type={self.type}, value={self.value})"

    def __str__(self):
        return f"EnvNode(name={self.name}, type={self.type}, value={self.value})"

    def __eq__(self, other):
        if not isinstance(other, EnvNode):
            return False
        return (
            self.name == other.name
            and self.type == other.type
            and self.value == other.value
        )

    def __hash__(self):
        return hash((self.name, self.type, self.value))

    def to_dict(self):
        return {
            "name": self.name,
            "type": self.type,
            "value": self.value,
        }

    def from_dict(data):
        node = EnvNode(data["name"], data["type"], data["value"])
        return node
