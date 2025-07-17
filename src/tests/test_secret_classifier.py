import pytest
from unittest.mock import MagicMock, patch
from embeddings.embeddings_engine import EmbeddingsEngine
from embeddings.secret_classifier import SecretClassifier

@pytest.fixture
def mock_embeddings_engine():
    return MagicMock(spec=EmbeddingsEngine)


@pytest.fixture
def secret_classifier(mock_embeddings_engine):
    return SecretClassifier(embeddings_engine=mock_embeddings_engine)


def test_decide_secret_exact_match(secret_classifier):
    with patch.object(secret_classifier, 'decide_secret', return_value=True) as mock_method:
        query = "exact match query"
        result = secret_classifier.decide_secret(query)
        assert result is True
        mock_method.assert_called_once_with(query)


def test_decide_secret_no_match(secret_classifier):
    with patch.object(secret_classifier, 'decide_secret', return_value=False) as mock_method:
        query = "no match query"
        result = secret_classifier.decide_secret(query)
        assert result is False
        mock_method.assert_called_once_with(query)


def test_decide_secret_none_returned(secret_classifier):
    with patch.object(secret_classifier, 'decide_secret', return_value=None) as mock_method:
        query = "query with no result"
        result = secret_classifier.decide_secret(query)
        assert result is None
        mock_method.assert_called_once_with(query)