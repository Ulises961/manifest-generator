import pytest
from unittest.mock import MagicMock, patch

from embeddings.embeddings_client import EmbeddingsClient
from embeddings.secret_classifier import SecretClassifier
from parsers.env_parser import EnvParser
from tree.command_mapper import CommandMapper
from embeddings.label_classifier import LabelClassifier
from tree.node import Node
from tree.node_types import NodeType

import os

@pytest.fixture
def command_mapper():
    embeddings_client = MagicMock(spec=EmbeddingsClient)
    label_classifier = LabelClassifier(embeddings_client)
    secret_classifier = SecretClassifier(embeddings_client)
    env_parser = EnvParser(secret_classifier)
    return CommandMapper(label_classifier, env_parser, embeddings_client)

def test_parse_dockerfile(command_mapper):
    dockerfile_content = """
    CMD ["python", "app.py"]
    LABEL version="1.0"
    EXPOSE 80
    """
    with open("Dockerfile", "w") as f:
        f.write(dockerfile_content)

    try:
        result = command_mapper.parse_dockerfile("Dockerfile")
        assert len(result) == 3
        assert result[0]["instruction"] == "CMD"
        assert result[1]["instruction"] == "LABEL"
        assert result[2]["instruction"] == "EXPOSE"
    finally:
        os.remove("Dockerfile")

def test_generate_cmd_node(command_mapper):
    cmd = {"instruction": "CMD", "value": ["python", "app.py"]}
    nodes = command_mapper._generate_cmd_nodes(cmd, None)
    node = nodes[0]
    assert isinstance(node, Node)
    assert node.type == NodeType.CMD
    assert node.value == ["python", "app.py"]

@patch("tree.command_mapper.CommandMapper.decide_label")
def test_generate_label_node(mock_decide_label, command_mapper):
    mock_decide_label.return_value = True
    label = {"instruction": "LABEL", "value": "version=1.0"}
    nodes = command_mapper._generate_label_nodes(label, None)
    node = nodes[0]
    assert isinstance(node, Node)
    assert node.type == NodeType.LABEL
    assert node.name == "version"
    assert node.value == "1.0"

def test_generate_expose_node(command_mapper):
    expose = {"instruction": "EXPOSE", "value": "80"}
    nodes = command_mapper._generate_expose_nodes(expose, None)
    node = nodes[0]
    assert node.type == NodeType.PORT
    assert node.value == "80"

@patch("embeddings.label_classifier.LabelClassifier.classify_label")
def test_decide_label(mock_classify_label, command_mapper):
    mock_classify_label.return_value = "label"
    assert command_mapper.decide_label("test_label")

def test_get_commands(command_mapper):
    parsed_dockerfile = [
        {"instruction": "CMD", "value": ["python", "app.py"]},
        {"instruction": "EXPOSE", "value": "80"},
    ]
    commands = command_mapper.get_commands(parsed_dockerfile, None)
    assert len(commands) == 2
    assert isinstance(commands[0], Node)
    assert isinstance(commands[1], Node)

def test_generate_entrypoint_nodes(command_mapper):
    entrypoint = {"instruction": "ENTRYPOINT", "value": ["python", "app.py"]}
    nodes = command_mapper._generate_entrypoint_nodes(entrypoint, None)
    node = nodes[0]
    assert isinstance(node, Node)
    assert node.type == NodeType.ENTRYPOINT
    assert node.value == ["python", "app.py"]

def test_generate_entrypoint_w_script(command_mapper):
    entrypoint = {"instruction": "ENTRYPOINT", "value": ["./start.sh"]}
    nodes = command_mapper._generate_entrypoint_nodes(entrypoint, None)
    node = nodes[0]
    assert isinstance(node, Node)
    assert node.type == NodeType.ENTRYPOINT
    assert node.value == ["./start.sh"]

def test_generate_entrypoint_w_script_and_args(command_mapper):
    entrypoint = {
        "instruction": "ENTRYPOINT",
        "value": ["./start.sh", "--arg1", "--arg2"],
    }
    nodes = command_mapper._generate_entrypoint_nodes(entrypoint, None)
    node = nodes[0]
    assert isinstance(node, Node)
    assert node.type == NodeType.ENTRYPOINT
    assert node.value == ["./start.sh", "--arg1", "--arg2"]

def test_parse_healthcheck_none(command_mapper):
    command = "HEALTHCHECK NONE"
    result = command_mapper._parse_healthcheck(command)
    assert result == {"disabled": True}

def test_parse_healthcheck_invalid_format(command_mapper):
    command = "HEALTHCHECK INVALID"
    with pytest.raises(ValueError, match="Invalid HEALTHCHECK command format"):
        command_mapper._parse_healthcheck(command)

def test_parse_healthcheck_exec_form(command_mapper):
    command = 'HEALTHCHECK --interval=5s --timeout=3s CMD ["curl", "-f", "http://localhost/"]'
    result = command_mapper._parse_healthcheck(command)
    assert result["check"] == '/bin/sh -c "curl -f http://localhost/"'
    assert result["flags"]["periodSeconds"] == 5
    assert result["flags"]["timeoutSeconds"] == 3

def test_parse_healthcheck_shell_form(command_mapper):
    command = 'HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 CMD curl -f http://localhost/'
    result = command_mapper._parse_healthcheck(command)
    assert result["check"] == 'curl -f http://localhost/'
    assert result["flags"]["periodSeconds"] == 30
    assert result["flags"]["timeoutSeconds"] == 30 
    assert result["flags"]["initialDelaySeconds"] == 5
    assert result["flags"]["failureThreshold"] == 3

def test_parse_healthcheck_invalid_exec_form(command_mapper):
    command = 'HEALTHCHECK CMD [invalid json]'
    with pytest.raises(ValueError, match="Invalid exec form CMD array"):
        command_mapper._parse_healthcheck(command)
     
@patch("parsers.env_parser.EnvParser.parse_env_var")
def test_generate_env_nodes(mock_parse_env_var, command_mapper):
    # Create a mock node that would be returned by parse_env_var
    mock_node = Node(
        name='TEST_ENV',
        type=NodeType.ENV,
        value='test_value',
        metadata={'is_secret': False}
    )
    
    
    # Configure mock to return list with mock node
    mock_parse_env_var.return_value = [mock_node]
    
    # Test data
    command = {"instruction": "ENV", "value": "TEST_ENV=test_value"}
    
    # Call method 
    nodes = command_mapper.generate_env_nodes(command, None)
    
    # Assertions
    assert len(nodes) == 1
    node = nodes[0]
    assert isinstance(node, Node)
    assert node.name == 'TEST_ENV'
    assert node.type == NodeType.ENV
    assert node.value == 'test_value'
    assert node.parent is None
    assert not node.is_persistent
    assert node.metadata == {'is_secret': False}
    
    mock_parse_env_var.assert_called_once_with("TEST_ENV=test_value")

@patch("tree.command_mapper.EmbeddingsClient")
def test_generate_volume_node(mock_embeddings_client):
    # Mock the embeddings client to return a valid response
    mock_embeddings_client.return_value.decide_volume.return_value = {"decision": True}

    # Initialize CommandMapper with mocked dependencies
    label_classifier = MagicMock()
    env_parser = MagicMock()
    command_mapper = CommandMapper(label_classifier, env_parser, mock_embeddings_client.return_value)

    # Test data
    volume = {"instruction": "VOLUME", "value": "test_volume"}
    nodes = command_mapper._generate_volume_nodes(volume, None)

    # Assertions
    assert len(nodes) == 1
    node = nodes[0]
    assert node.name == "VOLUME"
    assert node.type == NodeType.VOLUME
    assert node.value == "test_volume"
    assert node.is_persistent is True