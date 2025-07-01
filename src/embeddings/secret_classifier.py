from typing import cast

from embeddings.embeddings_client import EmbeddingsClient


class SecretClassifier:
    def __init__(self, embeddings_client: EmbeddingsClient) -> None:
        self.embeddings_client: EmbeddingsClient = embeddings_client

    def decide_secret(self, query: str) -> bool:
        """Decide the secret based on the query and a given threshold. The decision is made on a three tier filter:
        * Exact match
        * Regex match
        * Embeddings simmilarity: The decision threshold is calculated in relation to the size of the knowledge base dynamically learnt during the usage of the tool
        """
        if (result := self.embeddings_client.decide_secret(query)) is not None:
            return cast(bool, result.get("decision", False))
        return False
