import pytest
from unittest.mock import MagicMock
from embeddings.service_classifier import ServiceClassifier
from embeddings.embeddings_client import EmbeddingsClient

@pytest.fixture
def mock_embeddings_client():
    """Fixture to create a mock EmbeddingsClient."""
    return MagicMock(spec=EmbeddingsClient)


@pytest.fixture
def service_classifier(mock_embeddings_client):
    """Fixture to create a ServiceClassifier instance."""
    return ServiceClassifier(embeddings_client=mock_embeddings_client)


def test_decide_service_with_valid_result(service_classifier, mock_embeddings_client):
    """Test decide_service when the embeddings client returns a valid result."""
    query = "test query"
    ports = [80, 443]
    mock_result = {"classification": {"service": "example_service"}}
    mock_embeddings_client.classify_service.return_value = mock_result

    result = service_classifier.decide_service(query, ports)

    assert result == mock_result["classification"]
    mock_embeddings_client.classify_service.assert_called_once_with(query, ports)


def test_decide_service_with_no_result(service_classifier, mock_embeddings_client):
    """Test decide_service when the embeddings client returns None."""
    query = "test query"
    ports = [80, 443]
    mock_embeddings_client.classify_service.return_value = None

    result = service_classifier.decide_service(query, ports)

    assert result is None
    mock_embeddings_client.classify_service.assert_called_once_with(query, ports)


def test_decide_service_with_no_ports(service_classifier, mock_embeddings_client):
    """Test decide_service when no ports are provided."""
    query = "test query"
    mock_result = {"classification": {"service": "example_service"}}
    mock_embeddings_client.classify_service.return_value = mock_result

    result = service_classifier.decide_service(query)

    assert result == mock_result["classification"]
    mock_embeddings_client.classify_service.assert_called_once_with(query, None)


def test_decide_service_with_empty_ports(service_classifier, mock_embeddings_client):
    """Test decide_service when an empty list of ports is provided."""
    query = "test query"
    ports = []
    mock_result = {"classification": {"service": "example_service"}}
    mock_embeddings_client.classify_service.return_value = mock_result

    result = service_classifier.decide_service(query, ports)

    assert result == mock_result["classification"]
    mock_embeddings_client.classify_service.assert_called_once_with(query, ports)