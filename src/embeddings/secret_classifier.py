import os
import re
from typing import Any, Dict, List

from numpy import log
from torch import Tensor
from embeddings.embeddings_engine import EmbeddingsEngine
from utils.file_utils import load_file


class SecretClassifier:
    def __init__(self, embeddings_engine: EmbeddingsEngine) -> None:
        self._engine: EmbeddingsEngine = embeddings_engine
        
        secrets_path: str = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), os.getenv("SECRETS_PATH", "resources/knowledge_base/secrets.json")
        )
        # Load secret embeddingss
        self._secrets: Dict[str, List[Any]] = self._load_secrets(
          secrets_path
        )

        # Calculate the threshold for the secrets embeddings
        """Adjusted Threshold=Base Threshold-(log(KB Size)/Max KB Size) x Adjustment Factor"""
        self._secrets_threshold: float = 0.8 - (
            (log(len(self.secrets["embeddings"]) + 1 )  / (len(self.secrets["embeddings"]) + 1))
            * 0.01
        )
        
        self._secrets_threshold = max(
            0.1, min(self._secrets_threshold, 0.9)
        )  # Ensure threshold is between 0.1 and 0.9
        
    @property
    def secrets(self) -> Dict[str, List[Tensor]]:
        """Get the secrets embeddings."""
        return self._secrets

    def _load_secrets(self, path: str) -> Dict[str, List[Tensor]]:
        """Load secrets from a file."""
        secrets: Dict[str, List[Any]] = load_file(path)

        embeddings_list: List[Tensor] = []

        # Compute embeddings for known secrets
        for key, values in secrets.items():
            if key == "miscellaneous":
                # Compute embedding for each individual value in the array
                for value in values:
                    embedding = self._engine.encode(value)
                    embeddings_list.append(embedding)

        secrets["embeddings"] = embeddings_list

        return secrets
    
    def decide_secret(self, query: str) -> bool:
        """Decide the secret based on the query and a given threshold. The decision is made on a three tier filter:
        * Exact match
        * Regex match
        * Embeddings simmilarity: The decision threshold is calculated in relation to the size of the knowledge base dynamically learnt during the usage of the tool
        """
        # Find an exact match among the possible values
        for key, values in self._secrets.items():
            if key == "regex" or key == "embeddings":
                continue
            for value in values:
                if query == value:
                    return True

        # Check if the query matches any regex
        for regex in self._secrets["regex"]:
            # Compile regex pattern
            regex = re.compile(regex)

            # Check if the regex matches the query
            result = re.match(regex, query)

            if result:
                return True

        # Compute the embedding for the query
        query_embedding: Tensor = self._engine.encode(query)

        for token in self._secrets["embeddings"]:
            # Compute the cosine similarity
            similarity: float = self._engine.compute_similarity(
                query_embedding, token
            )

            # Check if the similarity is greater than the threshold
            if similarity > self._secrets_threshold:
                return True
        return False