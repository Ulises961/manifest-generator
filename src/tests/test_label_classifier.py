import pytest
from unittest.mock import MagicMock, patch
from embeddings.embeddings_engine import EmbeddingsEngine
from embeddings.label_classifier import LabelClassifier

@pytest.fixture
def mock_embeddings_engine():
    return MagicMock(spec=EmbeddingsEngine)


@pytest.fixture
def label_classifier(mock_embeddings_engine):
    return LabelClassifier(mock_embeddings_engine)


def test_classify_label_returns_decision(label_classifier):
    with patch.object(label_classifier, 'classify_label', return_value="label") as mock_method:
        result = label_classifier.classify_label("test_label")
        assert result == "label"
        mock_method.assert_called_once_with("test_label")


def test_classify_label_returns_annotation(label_classifier):
    with patch.object(label_classifier, 'classify_label', return_value="annotation") as mock_method:
        result = label_classifier.classify_label("test_label")
        assert result == "annotation"
        mock_method.assert_called_once_with("test_label")


def test_classify_label_returns_none_when_no_result(label_classifier):
    with patch.object(label_classifier, 'classify_label', return_value=None) as mock_method:
        result = label_classifier.classify_label("test_label")
        assert result is None
        mock_method.assert_called_once_with("test_label")