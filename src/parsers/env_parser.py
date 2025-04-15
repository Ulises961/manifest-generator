import base64
from typing_extensions import Buffer
from embeddings.secret_classifier import SecretClassifier
from tree.node import Node
from tree.node_types import NodeType


class EnvParser:
    def __init__(self, secret_classifier: SecretClassifier):
        self.secret_classifier = secret_classifier

    def get_env_vars(self):
        return self.env_vars
    
    def get_env_var(self, key):
        return self.env_vars.get(key)
    

    def parse(self, path: str, parent: Node) -> None:
        """Parse .env file and add variables as children to the parent node."""
        with open(path, "r") as f:
            for line in f:
                # Skip comments and empty lines
                if line.startswith("#") or not line.strip():
                    continue

                # Split the line into key-value pairs
                try:
                    key, value = line.strip().split("=", 1)
                    env_node = self.create_env_node(key, value)
                    parent.add_child(env_node)

                except ValueError:
                    continue
                
    def create_env_node(self, key: str, value: str) -> Node:
        """Create an Node from a key-value pair."""
        is_secret = self.secret_classifier.decide_secret(value)
        if is_secret:
            value = value.encode("utf-8")
            value = base64.b64encode(value)
        return Node(name=key, type=NodeType.SECRET if is_secret else NodeType.ENV, value=value)