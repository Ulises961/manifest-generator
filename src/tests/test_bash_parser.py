import pytest
from unittest.mock import Mock, patch
from parsers.bash_parser import BashScriptParser
from tree.node import Node
from tree.node_types import NodeType



@pytest.fixture
def parser():
    secret_classifier = Mock()
    env_parser = Mock()
    embeddings_engine = Mock()
    return BashScriptParser(secret_classifier, env_parser, embeddings_engine)


def test_init(parser):
    assert parser.startup_script_names == [
        "start.sh",
        "entrypoint.sh",
        "run.sh",
        "serve.sh",
    ]
    assert isinstance(parser.patterns, dict)


def test_parse_env_var(parser):
    # Mock env parser
    env_node = Node("TEST_VAR", NodeType.ENV, "test_value")
    parser.env_parser.create_env_node.return_value = env_node

    # Test valid export
    result = parser._parse_env_var('export TEST_VAR="test_value"')
    assert result == env_node
    parser.env_parser.create_env_node.assert_called_with("TEST_VAR", "test_value")

    # Test invalid line
    assert parser._parse_env_var("not an export") is None


def test_parse_mount(parser):
    # Test valid mount
    result = parser._parse_mount("mount -t ext4 /dev/sda1 /mnt")
    assert result.type == NodeType.VOLUME
    assert result.value == "/dev/sda1 /mnt"

    # Test invalid mount
    assert parser._parse_mount("not a mount") is None


def test_is_orchestrator_line(parser):
    assert parser._is_orchestrator_line("kubectl get pods") is True
    assert parser._is_orchestrator_line("docker run container") is True
    assert parser._is_orchestrator_line("echo hello") is False


def test_find_startup_script(parser):
    with patch.object(parser._engine, "compute_similarity") as mock_similarity:
        # Mock the similarity function to return a high score for the first script
        mock_similarity.return_value = 0.9

        # Test with a list of files
        root = "/test/path"
        files = ["start.sh", "other.sh"]

        result = parser._find_startup_script(root, files)
        assert result == "/test/path/start.sh"
        # Test with no files
        mock_similarity.return_value = 0.0
        result = parser._find_startup_script(root, [])
        assert result is None
        # Test with a single file
        mock_similarity.return_value = 0.8
        result = parser._find_startup_script(root, ["start.sh"])
        assert result == "/test/path/start.sh"
        # Test with a different file
        mock_similarity.return_value = 0.0
        result = parser._find_startup_script(root, ["other.sh"])
        assert result is None


@patch("builtins.open")
def test_parse_script(mock_open, parser):
    mock_open.return_value.__enter__.return_value.read.return_value = """
    #!/bin/bash
    export TEST_VAR="test"
    mount /dev/sda1 /mnt
    exec python app.py
    """

    parent = Node("test", NodeType.MICROSERVICE, "test")
    nodes = parser.parse_script("/test/script.sh", None, None, parent)

    assert len(nodes) > 0
    assert any(isinstance(node, Node) for node in nodes)


@patch("builtins.open")
def test_determine_startup_command(mock_open, parser):
    # Setup mock file content
    mock_open.return_value.__enter__.return_value.read.return_value = """
    #!/bin/bash
    echo "Starting service"
    """

    # Mock the _find_startup_script method to return a specific path
    with patch.object(parser, "_find_startup_script", return_value="/test/start.sh"):
        root = "/test"
        files = ["start.sh"]
        service_node = Node("test-service", NodeType.MICROSERVICE, "test")

        # Test with no entrypoint/cmd
        parser.determine_startup_command(root, files, service_node)
        entrypoint = Node(
            "test-service",
            NodeType.ENTRYPOINT,
            ["echo", "Starting service"],
            metadata={
                "review": "Generated from bash script",
                "source": "script",
                "full_command": ["echo", "Starting service"],
                "status": "active",
            },
        )

        assert entrypoint in service_node.children

        # Verify the script was parsed and results added to service_node
        # You can add assertions here based on expected behavior

        # Test with entrypoint
        entrypoint = Node("test-service", NodeType.ENTRYPOINT, "start.sh")
        service_node.add_child(entrypoint)
        parser.determine_startup_command(root, files, service_node)
        assert entrypoint in service_node.children

        # Test with cmd
        cmd = Node("test-service", NodeType.CMD, "python app.py")
        service_node.add_child(cmd)
        parser.determine_startup_command(root, files, service_node)
        assert cmd in service_node.children
