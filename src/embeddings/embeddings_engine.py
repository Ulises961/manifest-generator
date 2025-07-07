from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
from torch import Tensor



class EmbeddingsEngine:
    """Embeddings engine for microservices."""

    def __init__(self, model: SentenceTransformer) -> None:
        self._model: SentenceTransformer = model

    @property
    def model(self) -> SentenceTransformer:
        """Get the model."""
        return self._model


    def encode(self, text: str) -> Tensor:
        """Encode the text using the model."""
        tensor_output = self.model.encode(text)            
        return tensor_output

    def compute_similarity(self, embedding_1: Tensor, embedding_2: Tensor) -> float:
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
        query_embedding: Tensor = self.model.encode(query)
        base_embedding: Tensor = self.model.encode(base)

        return self.compute_similarity(query_embedding, base_embedding)

    def compare_words(self, word1: str, word2: str) -> float:
        """Compare two words using their embeddings.
        
        Args:
            word1: First word to compare
            word2: Second word to compare
            
        Returns:
            float: Similarity score between 0 and 1
        """
        # Use sentence embeddings for single words
        emb1 = self.model.encode(word1, convert_to_numpy=True)
        emb2 = self.model.encode(word2, convert_to_numpy=True)
        
        return float(cosine_similarity([emb1], [emb2])[0][0])
