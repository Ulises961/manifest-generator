import pytest
import numpy as np
import torch
from unittest.mock import Mock
from embeddings.embeddings_engine import EmbeddingsEngine


class TestEmbeddingsEngine:
    """Test suite for EmbeddingsEngine"""

    @pytest.fixture
    def mock_model(self):
        """Create a mock SentenceTransformer model"""
        model = Mock()
        model.encode = Mock()
        return model

    @pytest.fixture
    def engine(self, mock_model):
        """Create an EmbeddingsEngine instance with mock model"""
        return EmbeddingsEngine(mock_model)

    def test_init(self, mock_model):
        """Test EmbeddingsEngine initialization"""
        engine = EmbeddingsEngine(mock_model)
        assert engine.model == mock_model

    def test_model_property(self, engine, mock_model):
        """Test model property getter"""
        assert engine.model == mock_model

    def test_encode(self, engine, mock_model):
        """Test encoding text"""
        test_text = "test microservice"
        expected_tensor = torch.tensor([0.1, 0.2, 0.3])
        mock_model.encode.return_value = expected_tensor
        
        result = engine.encode(test_text)
        
        mock_model.encode.assert_called_once_with(test_text)
        assert torch.equal(result, expected_tensor)

    def test_compute_similarity_1d_arrays(self, engine):
        """Test computing similarity between 1D embeddings"""
        embedding_1 = torch.tensor([1.0, 0.0, 0.0])
        embedding_2 = torch.tensor([1.0, 0.0, 0.0])
        
        similarity = engine.compute_similarity(embedding_1, embedding_2)
        
        # Identical vectors should have similarity of 1.0
        assert isinstance(similarity, float)
        assert similarity == pytest.approx(1.0, abs=0.01)

    def test_compute_similarity_2d_arrays(self, engine):
        """Test computing similarity between 2D embeddings"""
        embedding_1 = torch.tensor([[1.0, 0.0, 0.0]])
        embedding_2 = torch.tensor([[1.0, 0.0, 0.0]])
        
        similarity = engine.compute_similarity(embedding_1, embedding_2)
        
        assert isinstance(similarity, float)
        assert similarity == pytest.approx(1.0, abs=0.01)

    def test_compute_similarity_orthogonal_vectors(self, engine):
        """Test computing similarity between orthogonal vectors"""
        embedding_1 = torch.tensor([1.0, 0.0, 0.0])
        embedding_2 = torch.tensor([0.0, 1.0, 0.0])
        
        similarity = engine.compute_similarity(embedding_1, embedding_2)
        
        # Orthogonal vectors should have similarity of 0.0
        assert similarity == pytest.approx(0.0, abs=0.01)

    def test_compute_similarity_opposite_vectors(self, engine):
        """Test computing similarity between opposite vectors"""
        embedding_1 = torch.tensor([1.0, 0.0, 0.0])
        embedding_2 = torch.tensor([-1.0, 0.0, 0.0])
        
        similarity = engine.compute_similarity(embedding_1, embedding_2)
        
        # Opposite vectors should have negative similarity
        assert similarity < 0

    def test_compare_words(self, engine, mock_model):
        """Test comparing two words"""
        word1 = "database"
        word2 = "storage"
        
        # Mock encode to return numpy arrays
        mock_model.encode.side_effect = [
            np.array([0.8, 0.2, 0.1]),
            np.array([0.7, 0.3, 0.1])
        ]
        
        similarity = engine.compare_words(word1, word2)
        
        assert isinstance(similarity, float)
        assert 0.0 <= similarity <= 1.0
        assert mock_model.encode.call_count == 2
        mock_model.encode.assert_any_call(word1, convert_to_numpy=True)
        mock_model.encode.assert_any_call(word2, convert_to_numpy=True)

    def test_compare_words_identical(self, engine, mock_model):
        """Test comparing identical words"""
        word = "service"
        mock_embedding = np.array([0.5, 0.5, 0.5])
        mock_model.encode.return_value = mock_embedding
        
        similarity = engine.compare_words(word, word)
        
        # Identical words should have high similarity
        assert similarity == pytest.approx(1.0, abs=0.01)

    def test_compare_words_different(self, engine, mock_model):
        """Test comparing completely different words"""
        word1 = "hello"
        word2 = "goodbye"
        
        mock_model.encode.side_effect = [
            np.array([1.0, 0.0, 0.0]),
            np.array([0.0, 1.0, 0.0])
        ]
        
        similarity = engine.compare_words(word1, word2)
        
        # Different words should have lower similarity
        assert 0.0 <= similarity < 1.0
