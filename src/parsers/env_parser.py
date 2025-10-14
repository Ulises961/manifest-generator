import base64
from typing import List
from embeddings.secret_classifier import SecretClassifier
from tree.node import Node
from tree.node_types import NodeType
from utils.docker_utils import parse_key_value_string


class EnvParser:
    def __init__(self, secret_classifier: SecretClassifier):
        self.secret_classifier = secret_classifier


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
                    parsed_nodes = self.parse_env_var(line)
                    if isinstance(parsed_nodes, list):
                        env_nodes.extend(parsed_nodes)
                    elif isinstance(parsed_nodes, Node):
                        env_nodes.append(parsed_nodes)
                except ValueError:
                    continue
        return env_nodes
    
    def parse_env_var(self, line: str) -> List[Node]:
       
        # Docker variable declaration
        if line.strip().startswith("ENV "):
            new_line = line.strip()[4:] 
            return self.parse_env_var(new_line)
        
        # A single ENV declaration might export many variables in seceral lines
        # ENV DB_HOST=localhost \
        #     DB_PORT=5432 \
        #     DB_USER=postgres ...
        vars_dict = parse_key_value_string(line)

        return [self.create_env_node(key, value) for key, value in vars_dict.items()]
    

    def create_env_node(self, key: str, value: str) -> Node:
        """Create an Node from a key-value pair."""
        is_secret = self.secret_classifier.decide_secret(key)
        encoded = value
        if is_secret and type(value) is str:
            encoded = value.encode("utf-8")
            encoded = base64.b64encode(encoded)
        return Node(name=key, type=NodeType.SECRET if is_secret else NodeType.ENV, value=encoded)
    
