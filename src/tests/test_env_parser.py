import pytest
from unittest.mock import Mock, mock_open, patch
from embeddings.secret_classifier import SecretClassifier
from tree.node import Node
from tree.node_types import NodeType
from parsers.env_parser import EnvParser

@pytest.fixture
def embeddings_engine():
    engine = Mock()
    engine.encode.return_value = [0.5, 0.5] 
    return engine

@pytest.fixture
def env_parser(embeddings_engine):
    secret_classifier = SecretClassifier(embeddings_engine)
    return EnvParser(secret_classifier)

@pytest.fixture
def parent_node():
    return Node("root", NodeType.ROOT, value="")

def test_parse_empty_file(env_parser, parent_node):
    with patch("builtins.open", mock_open(read_data="")):
        env_parser.parse("dummy.env", parent_node)
        assert len(parent_node.children) == 0

def test_parse_comments_and_empty_lines(env_parser, parent_node):
    content = """
    # comment
    
    # another comment
    """
    with patch("builtins.open", mock_open(read_data=content)):
        env_parser.parse("dummy.env", parent_node)
        assert len(parent_node.children) == 0

def test_parse_valid_env_vars(env_parser, parent_node):
    content = """
    DB_HOST=localhost
    DB_PORT=5432
    """
    with patch("builtins.open", mock_open(read_data=content)):
        env_parser.parse("dummy.env", parent_node)
        assert len(parent_node.children) == 2
        assert parent_node.children[0].name == "DB_HOST"
        assert parent_node.children[0].value == "localhost"
        assert parent_node.children[1].name == "DB_PORT"
        assert parent_node.children[1].value == "5432"

def test_parse_invalid_lines(env_parser, parent_node):
    content = """
    invalid_line
    DB_HOST=localhost
    another_invalid
    """
    with patch("builtins.open", mock_open(read_data=content)):
        env_parser.parse("dummy.env", parent_node)
        assert len(parent_node.children) == 1
        assert parent_node.children[0].name == "DB_HOST"
        assert parent_node.children[0].value == "localhost"