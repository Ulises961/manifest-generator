import pytest
import numpy as np
from unittest.mock import Mock, patch
from embeddings.service_classifier import ServiceClassifier


@pytest.fixture
def mock_embeddings_engine():
    """Create a mock embeddings engine for testing."""
    engine = Mock()
    engine.encode = Mock(return_value=np.array([0.1, 0.2, 0.3]))
    engine.encode = Mock(return_value=np.array([0.1, 0.2, 0.3]))
    engine.compute_similarity = Mock(return_value=0.85)
    return engine


@pytest.fixture
def sample_services():
    return {
        "services": [
            {
                "name": "test_service",
                "keywords": ["test", "service"],
                "description": "Test service",
            }
        ]
    }


def test_init(mock_embeddings_engine, sample_services):
    """Test ServiceClassifier initialization."""
    with patch("embeddings.service_classifier.load_file") as mock_load:
        mock_load.return_value = sample_services
        classifier = ServiceClassifier(mock_embeddings_engine)
        assert classifier._engine == mock_embeddings_engine
        # Check threshold is within reasonable bounds
        embedding_length = len(classifier._services[0]["embeddings"])
        assert 0.1 <= classifier.calculate_threshold(embedding_length) <= 0.9


def test_load_services(mock_embeddings_engine, sample_services):
    with patch("embeddings.service_classifier.load_file") as mock_load:
        mock_load.return_value = sample_services
        classifier = ServiceClassifier(mock_embeddings_engine)
        # Access the services attribute or property correctly
        services = classifier.services  # Try property first
        assert len(services) == 1
        assert "test_service" in services[0]["name"]
        mock_embeddings_engine.encode.assert_called()


def test_decide_service_above_threshold(mock_embeddings_engine,sample_services):
    with patch("embeddings.service_classifier.load_file") as mock_load:
        mock_load.return_value = sample_services
        classifier = ServiceClassifier(mock_embeddings_engine)
        result = classifier.decide_service("test query")
        assert result is not None
        assert result["name"] == "test_service"


def test_decide_service_below_threshold(mock_embeddings_engine, sample_services):
    mock_embeddings_engine.compute_similarity.return_value = 0.1
    with patch("embeddings.service_classifier.load_file") as mock_load:
        mock_load.return_value = sample_services
        classifier = ServiceClassifier(mock_embeddings_engine)
        result = classifier.decide_service("unrelated query")
        assert result is None

def test_decide_service_with_ports(mock_embeddings_engine, sample_services):
    with patch("embeddings.service_classifier.load_file") as mock_load:
        # Modify sample services to include ports
        sample_services["services"][0]["ports"] = [8080, 8081]
        mock_load.return_value = sample_services
        classifier = ServiceClassifier(mock_embeddings_engine)
        
        # Test with matching port
        result = classifier.decide_service("test query", ports=[8080])
        assert result is not None
        assert result["name"] == "test_service"
        
        # Test with non-matching port
        result = classifier.decide_service("test query", ports=[9090])
        assert result is not None  # Should still match due to high similarity

def test_decide_service_no_ports(mock_embeddings_engine, sample_services):
    with patch("embeddings.service_classifier.load_file") as mock_load:
        # Service with no ports defined
        sample_services["services"][0]["ports"] = []
        mock_load.return_value = sample_services
        classifier = ServiceClassifier(mock_embeddings_engine)
        
        result = classifier.decide_service("test query", ports=[8080])
        assert result is not None
        assert result["name"] == "test_service"

