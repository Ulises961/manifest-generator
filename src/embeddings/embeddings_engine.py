import re
from typing import Dict, List, Optional, Union, Any
import os
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from numpy import ndarray
from numpy import log
from utils import load_file


class EmbeddingsEngine:
    """Embeddings engine for microservices."""

    def __init__(self, model: SentenceTransformer) -> None:
        self._model: SentenceTransformer = model

    @property
    def model(self) -> SentenceTransformer:
        """Get the model."""
        return self._model

    def encode_word(self, text: str) -> ndarray:
        """Encode the text using the model."""
        return self.model.encode(text, output_value="token_embeddings")

    def encode(self, text: str) -> ndarray:
        """Encode the text using the model."""
        return self.model.encode(text, output_value="sentence_embeddings")

    def compute_similarity(self, embedding_1: ndarray, embedding_2: ndarray) -> float:
        """Compute cosine similarity between embeddings.

        Args:
            embedding_1: First embedding (1D or 2D array)
            embedding_2: Second embedding (1D or 2D array)

        Returns:
            float: Cosine similarity score
        """

        # Handle 1D arrays (sentence embeddings)
        if embedding_1.ndim == 1:
            embedding_1 = embedding_1.reshape(1, -1)
        if embedding_2.ndim == 1:
            embedding_2 = embedding_2.reshape(1, -1)

        return float(cosine_similarity(embedding_1, embedding_2)[0][0])

    def compare_manifests(self, query: str, base: str) -> float:
        """Compare two sentences using cosine similarity."""
        query_embedding: ndarray = self.model.encode(query)
        base_embedding: ndarray = self.model.encode(base)

        return self.compute_similarity(query_embedding, base_embedding)
