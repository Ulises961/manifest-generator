import os
from typing import cast
from sentence_transformers import SentenceTransformer

from embeddings.embeddings_client import EmbeddingsClient


class EmbeddingsComparator:
    """Embeddings engine for microservices."""

    def __init__(self, model: SentenceTransformer) -> None:
        self._model: SentenceTransformer = model
        self.embedding_client = EmbeddingsClient(
            os.getenv("EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        )

    @property
    def model(self) -> SentenceTransformer:
        """Get the model."""
        return self._model

    def compute_similarity(self, embedding_1: str, embedding_2: str) -> float:
        if (
            response := self.embedding_client.get_similarity(embedding_1, embedding_2)
        ) is not None:
            return cast(float,response.get("similarity", 0.0))
        else:
            raise ValueError("Failed to compute similarity between embeddings.")

    def compare_manifests(self, query: str, base: str) -> float:
        """Compare two sentences using cosine similarity."""
        return self.compute_similarity(query, base)
