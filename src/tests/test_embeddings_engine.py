import pytest
from sentence_transformers import SentenceTransformer
from numpy import ndarray, array
from embeddings.embeddings_engine import EmbeddingsEngine
from utils.file_utils import setup_sentence_transformer

@pytest.fixture
def model():
    return setup_sentence_transformer(True)

@pytest.fixture
def engine(model):
    return EmbeddingsEngine(model)

def test_model_property(engine, model):
    assert engine.model == model


def test_encode(engine):
    text = "test"
    result = engine.encode(text) 
    assert isinstance(result, ndarray)
    assert result.ndim == 1  # [embedding_dim]

def test_compute_similarity(engine):
    # Test with 1D arrays
    emb1 = array([1.0, 0.0, 0.0])
    emb2 = array([1.0, 0.0, 0.0])
    similarity = engine.compute_similarity(emb1, emb2)
    assert isinstance(similarity, float)
    assert similarity == 1.0

    # Test with 2D arrays
    emb3 = array([[1.0, 0.0, 0.0]])
    emb4 = array([[0.0, 1.0, 0.0]])
    similarity = engine.compute_similarity(emb3, emb4)
    assert isinstance(similarity, float)
    assert similarity == 0.0

def test_compare_manifests(engine):
    text1 = "This is a test"
    text2 = "This is a test"
    similarity = engine.compare_manifests(text1, text2)
    assert isinstance(similarity, float)
    assert 0 <= similarity <= 1

def test_compare_words(engine):
    # Similar words
    assert engine.compare_words("test", "exam") > 0.5
    assert engine.compare_words("happy", "glad") > 0.5
    
    # Different words
    assert engine.compare_words("cat", "database") < 0.3
    
    # Same word
    assert engine.compare_words("test", "test") > 0.99

def test_negative_similarity(engine):
    # Test with opposite vectors to verify -1 similarity
    emb1 = array([1.0, 0.0, 0.0])
    emb2 = array([-1.0, 0.0, 0.0]) 
    similarity = engine.compute_similarity(emb1, emb2)
    assert similarity == -1.0

def test_different_dimension_inputs(engine):
    # Test that compute_similarity handles different input dimensions correctly
    emb1 = array([1.0, 0.0, 0.0])  # 1D
    emb2 = array([[1.0, 0.0, 0.0]])  # 2D
    similarity = engine.compute_similarity(emb1, emb2)
    assert isinstance(similarity, float)
    assert similarity == 1.0

def test_empty_string_encoding(engine):
    # Test encoding empty string
    result = engine.encode("")
    assert isinstance(result, ndarray)
    assert result.ndim == 1
    assert result.shape[0] == 384  # MiniLM dimension

def test_special_characters(engine):
    # Test encoding special characters
    special = "!@#$%^&*()"
    result = engine.encode(special)
    assert isinstance(result, ndarray)
    assert result.ndim == 1
