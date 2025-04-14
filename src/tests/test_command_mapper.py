import pytest
from unittest.mock import patch

from sentence_transformers import SentenceTransformer
from embeddings.embeddings_engine import EmbeddingsEngine
from tree.command_mapper import CommandMapper
from embeddings.label_classifier import LabelClassifier
from tree.node_types import NodeType
from tree.docker_instruction_node import DockerInstruction
import os
from utils.file_utils import load_environment, setup_sentence_transformer

@pytest.fixture
def command_mapper():
    model: SentenceTransformer = setup_sentence_transformer()
    embeddings_engine = EmbeddingsEngine(model)
    label_classifier = LabelClassifier(embeddings_engine)
    return CommandMapper(label_classifier)

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
    node = command_mapper._generate_cmd_node(cmd, None)
    assert isinstance(node, DockerInstruction)
    assert node.type == NodeType.CMD
    assert node.value == ["python", "app.py"]

@patch("tree.command_mapper.CommandMapper.decide_label")
def test_generate_label_node(mock_decide_label, command_mapper):
    mock_decide_label.return_value = True
    label = {"instruction": "LABEL", "value": "version=1.0"}
    node = command_mapper._generate_label_node(label, None)
    assert isinstance(node, DockerInstruction)
    assert node.type == NodeType.LABEL
    assert node.value == "version=1.0"

def test_generate_expose_node(command_mapper):
    expose = {"instruction": "EXPOSE", "value": "80"}
    node = command_mapper._generate_expose_node(expose, None)
    assert node["type"] == "PORTS"
    assert node["command"] == "80"

def test_generate_volume_node(command_mapper):
    load_environment()

    volumes_content = '["test_volume"]'
    with open("volumes.json", "w") as f:
        f.write(volumes_content)

    try:
        volume = {"instruction": "VOLUME", "value": "test_volume"}
        node = command_mapper._generate_volume_node(volume, None)
        assert isinstance(node, DockerInstruction)
        assert node.type == NodeType.VOLUME
        assert not node.is_persistent
    finally:
        os.remove("volumes.json")

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
    assert isinstance(commands[0], DockerInstruction)
    assert isinstance(commands[1], dict)

def test_generate_entrypoint_node(command_mapper):
    entrypoint = {"instruction": "ENTRYPOINT", "value": ["python", "app.py"]}
    node = command_mapper._generate_entrypoint_node(entrypoint, None)
    assert isinstance(node, DockerInstruction)
    assert node.type == NodeType.ENTRYPOINT
    assert node.value == ["python", "app.py"]

def test_generate_entrypoint_w_script(command_mapper):
    entrypoint = {"instruction": "ENTRYPOINT", "value": ["./start.sh"]}
    node = command_mapper._generate_entrypoint_node(entrypoint, None)
    assert isinstance(node, DockerInstruction)
    assert node.type == NodeType.ENTRYPOINT
    assert node.value == ["./start.sh"]

def test_generate_entrypoint_w_script_and_args(command_mapper):
    entrypoint = {
        "instruction": "ENTRYPOINT",
        "value": ["./start.sh", "--arg1", "--arg2"],
    }
    node = command_mapper._generate_entrypoint_node(entrypoint, None)
    assert isinstance(node, DockerInstruction)
    assert node.type == NodeType.ENTRYPOINT
    assert node.value == ["./start.sh", "--arg1", "--arg2"]
