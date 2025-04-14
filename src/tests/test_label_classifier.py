import pytest
from unittest.mock import Mock
from embeddings.label_classifier import LabelClassifier
from utils.file_utils import load_environment

@pytest.fixture
def mock_embeddings_engine():
    engine = Mock()
    engine.encode.return_value = [0.5, 0.5] 
    return engine

@pytest.fixture
def label_classifier(mock_embeddings_engine):
    classifier = LabelClassifier(mock_embeddings_engine)
    classifier._label_embeddings = {
        'labels': {'test_label': [0.5, 0.5]},
        'annotations': {'test_annotation': [0.5, 0.5]}
    }
    return classifier
@pytest.fixture
def load_env_variables(monkeypatch):
   load_environment()
   
def test_classify_label_returns_label(mock_embeddings_engine, label_classifier):
    mock_embeddings_engine.compute_similarity.side_effect = [0.9, 0.7]
    result = label_classifier.classify_label("test")
    assert result == "label"

def test_classify_label_returns_annotation(mock_embeddings_engine, label_classifier):
    mock_embeddings_engine.compute_similarity.side_effect = [0.7, 0.9]
    result = label_classifier.classify_label("test")
    assert result == "annotation"

def test_classify_label_with_only_label_match(mock_embeddings_engine, label_classifier):
    mock_embeddings_engine.compute_similarity.side_effect = [0.9, 0.5]
    result = label_classifier.classify_label("test")
    assert result == "label"

def test_classify_label_with_only_annotation_match(mock_embeddings_engine, label_classifier):
    mock_embeddings_engine.compute_similarity.side_effect = [0.5, 0.9]
    result = label_classifier.classify_label("test")
    assert result == "annotation"

def test_classify_label_with_custom_threshold(mock_embeddings_engine, label_classifier):
    mock_embeddings_engine.compute_similarity.side_effect = [0.7, 0.6]
    result = label_classifier.classify_label("test", threshold=0.5)
    assert result == "label"

def test_classify_label_with_no_matches(mock_embeddings_engine, label_classifier):
    mock_embeddings_engine.compute_similarity.side_effect = [0.1, 0.2]
    result = label_classifier.classify_label("test")
    assert result is None

