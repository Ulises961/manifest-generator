import pytest
from unittest.mock import Mock, mock_open, patch
from embeddings.secret_classifier import SecretClassifier
from tree.node import Node
from tree.node_types import NodeType
from parsers.env_parser import EnvParser
import base64

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
        nodes = env_parser.parse("dummy.env")
        assert len(nodes) == 0

def test_parse_comments_and_empty_lines(env_parser, parent_node):
    content = """
    # comment
    
    # another comment
    """
    with patch("builtins.open", mock_open(read_data=content)):
        nodes = env_parser.parse("dummy.env")
        assert len(nodes) == 0

def test_parse_valid_env_vars(env_parser, parent_node):
    content = """
    DB_HOST=localhost
    DB_PORT=5432
    """
    with patch("builtins.open", mock_open(read_data=content)):
        nodes = env_parser.parse("dummy.env")
        assert len(nodes) == 2
        # Check for SECRET type and base64-encoded value
        assert nodes[0].name == "DB_HOST"
        assert nodes[0].type == NodeType.SECRET
        assert base64.b64decode(nodes[0].value).decode() == "localhost"
        assert nodes[1].name == "DB_PORT"
        assert nodes[1].type == NodeType.SECRET
        assert base64.b64decode(nodes[1].value).decode() == "5432"

def test_parse_invalid_lines(env_parser, parent_node):
    content = """
    invalid_line
    DB_HOST=localhost
    another_invalid
    """
    with patch("builtins.open", mock_open(read_data=content)):
        nodes = env_parser.parse("dummy.env")
        assert len(nodes) == 1
        assert nodes[0].name == "DB_HOST"
        assert nodes[0].type == NodeType.SECRET
        assert base64.b64decode(nodes[0].value).decode() == "localhost"

def test_multiline_env_var(env_parser, parent_node):
    content = """
    ENV DOTNET_EnableDiagnostics=0 \
        ASPNETCORE_HTTP_PORTS=7070
    """
    with patch("builtins.open", mock_open(read_data=content)):
        nodes = env_parser.parse("dummy.env")
        assert len(nodes) == 2
        assert nodes[0].name == "DOTNET_EnableDiagnostics"
        assert base64.b64decode(nodes[0].value).decode() == "0"
        assert nodes[1].name == "ASPNETCORE_HTTP_PORTS"
        assert base64.b64decode(nodes[1].value).decode() == "7070"

def test_parse_env_var_with_spaces(env_parser, parent_node):
    content = """
    ENV DB_HOST=localhost     DB_PORT=5432
    """
    with patch("builtins.open", mock_open(read_data=content)):
        nodes = env_parser.parse("dummy.env")
        assert len(nodes) == 2
        # Check for SECRET type and base64-encoded value
        assert nodes[0].name == "DB_HOST"
        assert nodes[0].type == NodeType.SECRET
        assert base64.b64decode(nodes[0].value).decode() == "localhost"
        assert nodes[1].name == "DB_PORT"
        assert nodes[1].type == NodeType.SECRET
        assert base64.b64decode(nodes[1].value).decode() == "5432"