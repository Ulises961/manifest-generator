import pytest
from unittest.mock import MagicMock, patch
from embeddings.service_classifier import ServiceClassifier
from embeddings.embeddings_engine import EmbeddingsEngine

@pytest.fixture
def mock_embeddings_engine():
    """Fixture to create a mock EmbeddingsEngine."""
    return MagicMock(spec=EmbeddingsEngine)


@pytest.fixture
def service_classifier(mock_embeddings_engine):
    """Fixture to create a ServiceClassifier instance."""
    return ServiceClassifier(embeddings_engine=mock_embeddings_engine)


def test_decide_service_with_valid_result(service_classifier):
    """Test decide_service when the embeddings client returns a valid result."""
    query = "test query"
    ports = [80, 443]
    mock_result = {"service": "example_service"}
    
    with patch.object(service_classifier, 'decide_service', return_value=mock_result) as mock_method:
        result = service_classifier.decide_service(query, ports)
        assert result == mock_result
        mock_method.assert_called_once_with(query, ports)


def test_decide_service_with_no_result(service_classifier):
    """Test decide_service when the embeddings client returns None."""
    query = "test query"
    ports = [80, 443]
    
    with patch.object(service_classifier, 'decide_service', return_value=None) as mock_method:
        result = service_classifier.decide_service(query, ports)
        assert result is None
        mock_method.assert_called_once_with(query, ports)


def test_decide_service_with_no_ports(service_classifier):
    """Test decide_service when no ports are provided."""
    query = "test query"
    mock_result = {"service": "example_service"}
    
    with patch.object(service_classifier, 'decide_service', return_value=mock_result) as mock_method:
        result = service_classifier.decide_service(query)
        assert result == mock_result
        mock_method.assert_called_once_with(query)


def test_decide_service_with_empty_ports(service_classifier):
    """Test decide_service when an empty list of ports is provided."""
    query = "test query"
    ports = []
    mock_result = {"service": "example_service"}
    
    with patch.object(service_classifier, 'decide_service', return_value=mock_result) as mock_method:
        result = service_classifier.decide_service(query, ports)
        assert result == mock_result
        mock_method.assert_called_once_with(query, ports)