from sentence_transformers import SentenceTransformer
from utils.file_utils import (
    check_shell_in_commands,
    needs_shell_parsing,
    normalize_command_field,
    remove_none_values,
    setup_sentence_transformer,
)
import pytest
from unittest.mock import patch, create_autospec


def test_not_dict():
    assert remove_none_values("test") == "test"
    assert remove_none_values(123) == 123
    assert remove_none_values(None) is None


def test_empty_dict():
    assert remove_none_values({}) is None


def test_dict_with_none():
    input_dict = {"a": 1, "b": None, "c": "test"}
    expected = {"a": 1, "c": "test"}
    assert remove_none_values(input_dict) == expected


def test_nested_dict_with_none():
    input_dict = {"a": {"x": None, "y": 2}, "b": None, "c": {"z": None}}
    expected = {
        "a": {"y": 2},
    }
    assert remove_none_values(input_dict) == expected


def test_deeply_nested_dict():
    input_dict = {
        "a": {"x": {"y": None, "z": 1}},
        "b": {"p": None, "q": {"r": None, "s": 2}},
    }
    expected = {"a": {"x": {"z": 1}}, "b": {"q": {"s": 2}}}
    assert remove_none_values(input_dict) == expected


def test_dict_with_empty_dict():
    input_dict = {"a": {}, "b": {"x": 1}, "c": None}
    expected = {"b": {"x": 1}}
    assert remove_none_values(input_dict) == expected


def test_normalize_command_field_empty():
    assert normalize_command_field(None) == []
    assert normalize_command_field("") == []
    assert normalize_command_field([]) == []


def test_normalize_command_field_list():
    assert normalize_command_field(["echo", "hello"]) == ["echo", "hello"]
    assert normalize_command_field(["ls", "-l"]) == ["ls", "-l"]
    assert normalize_command_field(["echo $HOME"]) == ["/bin/sh -c", "echo $HOME"]


def test_normalize_command_field_str():
    assert normalize_command_field("echo hello") == ["echo", "hello"]
    assert normalize_command_field("ls -l") == ["ls", "-l"]
    assert normalize_command_field('["echo", "hello"]') == ["echo", "hello"]
    assert normalize_command_field("echo $HOME") == ["/bin/sh -c", "echo $HOME"]


def test_normalize_command_field_invalid_json():
    assert normalize_command_field("[invalid json]") == []


def test_needs_shell_parsing():
    assert needs_shell_parsing("echo hello") == False
    assert needs_shell_parsing("echo $HOME") == True
    assert needs_shell_parsing("ls | grep test") == True
    assert needs_shell_parsing("$(pwd)") == True
    assert needs_shell_parsing("echo ${PATH}") == True
    assert needs_shell_parsing("bash -c 'echo hello'") == True


def test_check_shell_in_commands():
    assert check_shell_in_commands(["echo", "hello"]) == False
    assert check_shell_in_commands(["echo", "$HOME"]) == True
    assert check_shell_in_commands(["ls", "|", "grep"]) == True
    assert check_shell_in_commands(["bash", "-c", "echo"]) == True


@pytest.fixture
def mock_env_vars():
    """Fixture for environment variables."""
    return {"MODELS_PATH": "/fake/path/models", "EMBEDDINGS_MODEL": "test-model"}


@pytest.fixture
def mock_cuda_available():
    """Fixture for CUDA availability."""
    with patch("torch.cuda.is_available", return_value=True):
        yield


@pytest.fixture
def mock_cuda_unavailable():
    """Fixture for CUDA unavailability."""
    with patch("torch.cuda.is_available", return_value=False):
        yield


class TestSetupSentenceTransformer:

    @patch("utils.file_utils.SentenceTransformer")
    @patch("os.path.exists")
    def test_existing_model_cpu_forced(self, mock_exists, mock_transformer):
        """Test loading existing model with forced CPU usage."""
        # Setup
        mock_exists.return_value = True
        mock_model = create_autospec(SentenceTransformer)
        mock_transformer.return_value = mock_model

        # Execute
        result = setup_sentence_transformer(force_cpu=True)

        # Assert
        assert result is mock_model  # Use 'is' instead of '=='
        mock_transformer.assert_called_once()
        kwargs = mock_transformer.call_args.kwargs
        assert kwargs.get("device") == "cpu"

    @patch("utils.file_utils.SentenceTransformer")
    @patch("os.path.exists")
    def test_new_model_download(self, mock_exists, mock_transformer):
        """Test downloading and saving new model."""
        # Setup
        mock_exists.return_value = False
        mock_model = create_autospec(SentenceTransformer)
        mock_transformer.return_value = mock_model

        # Execute
        result = setup_sentence_transformer()

        # Assert
        assert result is mock_model
        mock_transformer.assert_called_once()
        mock_model.save.assert_called_once()
