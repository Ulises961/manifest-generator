import pytest
from unittest.mock import Mock, patch
from embeddings.secret_classifier import SecretClassifier
import numpy as np

from utils.file_utils import load_environment

@pytest.fixture
def mock_embeddings_engine():
    engine = Mock()
    engine.encode.return_value = [np.array([0.1, 0.2, 0.3])]
    return engine

@pytest.fixture
def secret_classifier(mock_embeddings_engine):
    with patch('embeddings.secret_classifier.load_file') as mock_load:
        classifier = SecretClassifier(mock_embeddings_engine)
    return classifier

@pytest.fixture
def load_env_variables(monkeypatch):
    load_environment()

def test_load_secrets(secret_classifier, mock_embeddings_engine):
    with patch('embeddings.secret_classifier.load_file') as mock_load:
        # Mock the secrets file content
        mock_load.return_value = {
            "miscellaneous": ["test_secret1", "test_secret2"],
            "other_key": ["value1"]
        }
        
        result = secret_classifier._load_secrets("dummy/path")
        
        # Verify load_file was called
        mock_load.assert_called_once_with("dummy/path")
        
        # Verify encode was called for each miscellaneous value
        assert mock_embeddings_engine.encode.call_count == 2
        mock_embeddings_engine.encode.assert_any_call("test_secret1")
        mock_embeddings_engine.encode.assert_any_call("test_secret2")
        
        # Verify the structure of returned dict
        assert "embeddings" in result
        assert isinstance(result["embeddings"], list)
        assert len(result["embeddings"]) == 2  # One embedding per misc secret
        assert all(isinstance(emb, np.ndarray) for emb in result["embeddings"])

def test_load_secrets_preserves_original_keys(secret_classifier, mock_embeddings_engine):
    with patch('embeddings.secret_classifier.load_file') as mock_load:
        # Mock the secrets file with multiple keys
        mock_secrets = {
            "miscellaneous": ["secret1"],
            "api_keys": ["key1", "key2"],
            "passwords": ["pass1"]
        }
        mock_load.return_value = mock_secrets
        
        result = secret_classifier._load_secrets("dummy/path")
        
        # Verify original keys are preserved
        assert set(result.keys()) == set(mock_secrets.keys()) | {"embeddings"}
        assert len(mock_secrets["api_keys"]) == len(result["api_keys"])
        assert all(key in mock_secrets["api_keys"] for key in result["api_keys"])

        assert len(mock_secrets["passwords"]) == len(result["passwords"])
        assert all(pwd in mock_secrets["passwords"] for pwd in result["passwords"])
        
        assert len(mock_secrets["miscellaneous"]) == len(result["miscellaneous"])
        assert all(misc in mock_secrets["miscellaneous"] for misc in result["miscellaneous"])

def test_load_secrets_empty_file(secret_classifier):
    with patch('embeddings.secret_classifier.load_file') as mock_load:
        # Mock empty secrets file
        mock_load.return_value = {}
        
        result = secret_classifier._load_secrets("dummy/path")
        
        # Verify result structure
        assert "embeddings" in result
        assert len(result["embeddings"]) == 0

def test_load_secrets_no_miscellaneous(secret_classifier, mock_embeddings_engine):
    with patch('embeddings.secret_classifier.load_file') as mock_load:
        # Mock secrets without miscellaneous key
        mock_load.return_value = {
            "api_keys": ["key1", "key2"]
        }
        
        result = secret_classifier._load_secrets("dummy/path")
        
        # Verify no embeddings were computed
        mock_embeddings_engine.encode.assert_not_called()
        assert len(result["embeddings"]) == 0
        
def test_decide_secret_exact_match(secret_classifier):
    secret_classifier._secrets = {
        "api_keys": ["test_key"],
        "regex": [],
        "embeddings": []
    }
    assert secret_classifier.decide_secret("test_key") == True

def test_decide_secret_regex_match(secret_classifier):
    secret_classifier._secrets = {
        "api_keys": [],
        "regex": [r"^test\d+$"],
        "embeddings": []
    }
    assert secret_classifier.decide_secret("test123") == True
    assert secret_classifier.decide_secret("nottest") == False

def test_decide_secret_embedding_match(secret_classifier, mock_embeddings_engine):
    mock_embeddings_engine.encode.return_value = np.array([0.1, 0.2, 0.3])
    mock_embeddings_engine.compute_similarity.return_value = 0.95
    
    secret_classifier._secrets = {
        "api_keys": [],
        "regex": [],
        "embeddings": [np.array([0.2, 0.3, 0.4])]
    }
    
    assert secret_classifier.decide_secret("test_query") == True

def test_decide_secret_no_match(secret_classifier, mock_embeddings_engine):
    mock_embeddings_engine.encode.return_value = np.array([0.1, 0.2, 0.3])
    mock_embeddings_engine.compute_similarity.return_value = 0.5
    
    secret_classifier._secrets = {
        "api_keys": ["other_key"],
        "regex": [r"^test\d+$"],
        "embeddings": [np.array([0.2, 0.3, 0.4])]
    }
    
    assert secret_classifier.decide_secret("no_match") == False

