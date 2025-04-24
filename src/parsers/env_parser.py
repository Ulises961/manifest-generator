import base64
from typing import List, Optional
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
    

    def parse(self, path: str) -> List[Node]:
        """Parse .env file and add variables as children to the parent node."""
        env_nodes = []
        with open(path, "r") as f:
            for line in f:
                # Skip comments and empty lines
                if line.startswith("#") or not line.strip():
                    continue

                # Split the line into key-value pairs
                try:
                    env_node = self.parse_env_var(line)
                    if env_node:
                        env_nodes.append(env_node)

                except ValueError:
                    continue
        return env_nodes
    
    def parse_env_var(self, line: str) -> Optional[Node]:
        # Docker variable declaration
        if line.strip().startswith("ENV "):

            line = line.removeprefix("ENV ") 
            return self.parse_env_var(line)
        # Bash variable export 
        if "=" in line:
            key, value = line.strip().split("=", 1)
            if key and value:  # Only create node if both key and value exist
                return self.create_env_node(key, value)

        # PORT "8080"
        parts = line.strip().split(" ", 1)
        if len(parts) == 2:  # Only process if we have all three parts
            [key, value] = parts
            if key and value:  # Only create node if both key and value exist
                return self.create_env_node(key, value)
                
        return None

    def create_env_node(self, key: str, value: str) -> Node:
        """Create an Node from a key-value pair."""
        is_secret = self.secret_classifier.decide_secret(key)
        if is_secret:
            encoded = value.encode("utf-8")
            encoded = base64.b64encode(encoded)
        return Node(name=key, type=NodeType.SECRET if is_secret else NodeType.ENV, value=encoded if is_secret else value)