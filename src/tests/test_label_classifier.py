import pytest
from unittest.mock import MagicMock
from embeddings.embeddings_client import EmbeddingsClient
from embeddings.label_classifier import LabelClassifier

@pytest.fixture
def mock_embeddings_client():
    return MagicMock(spec=EmbeddingsClient)


@pytest.fixture
def label_classifier(mock_embeddings_client):
    return LabelClassifier(mock_embeddings_client)


def test_classify_label_returns_decision(label_classifier, mock_embeddings_client):
    mock_embeddings_client.classify_label.return_value = {"decision": "positive"}
    result = label_classifier.classify_label("test_label")
    assert result == "positive"
    mock_embeddings_client.classify_label.assert_called_once_with("test_label")


def test_classify_label_returns_unknown_when_no_decision(label_classifier, mock_embeddings_client):
    mock_embeddings_client.classify_label.return_value = {}
    result = label_classifier.classify_label("test_label")
    assert result == "unknown"
    mock_embeddings_client.classify_label.assert_called_once_with("test_label")


def test_classify_label_returns_none_when_no_result(label_classifier, mock_embeddings_client):
    mock_embeddings_client.classify_label.return_value = None
    result = label_classifier.classify_label("test_label")
    assert result is None
    mock_embeddings_client.classify_label.assert_called_once_with("test_label")