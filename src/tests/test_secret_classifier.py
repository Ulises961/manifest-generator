import pytest
from unittest.mock import MagicMock
from embeddings.embeddings_client import EmbeddingsClient
from embeddings.secret_classifier import SecretClassifier

@pytest.fixture
def mock_embeddings_client():
    return MagicMock(spec=EmbeddingsClient)


@pytest.fixture
def secret_classifier(mock_embeddings_client):
    return SecretClassifier(embeddings_client=mock_embeddings_client)


def test_decide_secret_exact_match(secret_classifier, mock_embeddings_client):
    mock_embeddings_client.decide_secret.return_value = {"decision": True}
    query = "exact match query"
    result = secret_classifier.decide_secret(query)
    assert result is True
    mock_embeddings_client.decide_secret.assert_called_once_with(query)


def test_decide_secret_no_match(secret_classifier, mock_embeddings_client):
    mock_embeddings_client.decide_secret.return_value = {"decision": False}
    query = "no match query"
    result = secret_classifier.decide_secret(query)
    assert result is False
    mock_embeddings_client.decide_secret.assert_called_once_with(query)


def test_decide_secret_none_returned(secret_classifier, mock_embeddings_client):
    mock_embeddings_client.decide_secret.return_value = None
    query = "query with no result"
    result = secret_classifier.decide_secret(query)
    assert result is False
    mock_embeddings_client.decide_secret.assert_called_once_with(query)