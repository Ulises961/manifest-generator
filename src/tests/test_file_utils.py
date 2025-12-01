import json
import yaml
import csv
import os
from unittest.mock import patch
from utils.file_utils import (
    load_json_file,
    save_json,
    load_yaml_file,
    save_csv,
    load_csv_file,
    remove_none_values,
    load_environment,
    setup_cuda,
    _get_model_paths
)


class TestFileUtils:
    """Test suite for file_utils.py"""

    def test_load_json_file(self, tmp_path):
        """Test loading a JSON file"""
        test_file = tmp_path / "test.json"
        test_data = {"key": "value", "number": 42}
        test_file.write_text(json.dumps(test_data))
        
        result = load_json_file(str(test_file))
        assert result == test_data

    def test_save_json(self, tmp_path):
        """Test saving a JSON file"""
        test_file = tmp_path / "output.json"
        test_data = {"name": "test", "items": [1, 2, 3]}
        
        save_json(test_data, str(test_file))
        
        with open(test_file, 'r') as f:
            saved_data = json.load(f)
        assert saved_data == test_data

    def test_load_yaml_file(self, tmp_path):
        """Test loading a YAML file"""
        test_file = tmp_path / "test.yaml"
        test_data = {"key": "value", "list": [1, 2, 3]}
        test_file.write_text(yaml.dump(test_data))
        
        result = load_yaml_file(str(test_file))
        assert result == test_data

    def test_save_csv(self, tmp_path):
        """Test saving a CSV file"""
        test_file = tmp_path / "test.csv"
        csv_data = [
            ["Name", "Age", "City"],
            ["Alice", "30", "NYC"],
            ["Bob", "25", "LA"]
        ]
        
        save_csv(csv_data, str(test_file))
        
        with open(test_file, 'r') as f:
            reader = csv.reader(f)
            result = list(reader)
        assert result == csv_data

    def test_load_csv_file(self, tmp_path):
        """Test loading a CSV file"""
        test_file = tmp_path / "test.csv"
        csv_data = [["A", "B"], ["1", "2"], ["3", "4"]]
        
        with open(test_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerows(csv_data)
        
        result = load_csv_file(str(test_file))
        assert result == csv_data

    def test_remove_none_values_simple(self):
        """Test removing None values from a simple dictionary"""
        input_dict = {"a": 1, "b": None, "c": "test"}
        result = remove_none_values(input_dict)
        assert result == {"a": 1, "c": "test"}

    def test_remove_none_values_nested(self):
        """Test removing None values from a nested dictionary"""
        input_dict = {
            "outer": {
                "inner": None,
                "valid": "value"
            },
            "keep": "this"
        }
        result = remove_none_values(input_dict)
        assert result == {"outer": {"valid": "value"}, "keep": "this"}

    def test_remove_none_values_with_empty_dict(self):
        """Test removing empty dictionaries"""
        input_dict = {"a": {}, "b": "value"}
        result = remove_none_values(input_dict)
        assert result == {"b": "value"}

    def test_remove_none_values_with_empty_list(self):
        """Test removing empty lists"""
        input_dict = {"a": [], "b": "value"}
        result = remove_none_values(input_dict)
        assert result == {"b": "value"}

    def test_remove_none_values_with_list(self):
        """Test removing None from lists"""
        input_dict = {"items": [1, None, 2, None, 3]}
        result = remove_none_values(input_dict)
        assert result == {"items": [1, 2, 3]}

    def test_remove_none_values_with_empty_strings(self):
        """Test handling empty strings - they are set to None but then stripped becomes empty string"""
        input_dict = {"a": "", "b": " ", "c": "valid"}
        result = remove_none_values(input_dict)
        # Empty strings after strip become "" which is kept in the dict
        assert result == {"a": "", "b": "", "c": "valid"}

    def test_remove_none_values_strips_strings(self):
        """Test string stripping"""
        input_dict = {"a": "  test  ", "b": "value"}
        result = remove_none_values(input_dict)
        assert result == {"a": "test", "b": "value"}

    def test_remove_none_values_non_dict(self):
        """Test with non-dictionary input"""
        assert remove_none_values("string") == "string"
        assert remove_none_values(42) == 42
        assert remove_none_values(None) is None

    @patch('utils.file_utils.load_dotenv')
    @patch('os.path.join')
    @patch('os.path.dirname')
    def test_load_environment(self, mock_dirname, mock_join, mock_load_dotenv):
        """Test loading environment variables"""
        mock_dirname.return_value = "/fake/path"
        mock_join.return_value = "/fake/path/.env"
        
        load_environment()
        
        mock_load_dotenv.assert_called_once_with("/fake/path/.env")

    @patch('torch.cuda.is_available')
    def test_setup_cuda_with_cuda_available(self, mock_cuda_available):
        """Test CUDA setup when GPU is available"""
        mock_cuda_available.return_value = True
        
        result = setup_cuda(force_cpu=False)
        
        assert result == "cuda"

    @patch('torch.cuda.is_available')
    def test_setup_cuda_force_cpu(self, mock_cuda_available):
        """Test CUDA setup with force_cpu flag"""
        mock_cuda_available.return_value = True
        
        result = setup_cuda(force_cpu=True)
        
        assert result == "cpu"

    @patch('torch.cuda.is_available')
    def test_setup_cuda_no_cuda_available(self, mock_cuda_available):
        """Test CUDA setup when GPU is not available"""
        mock_cuda_available.return_value = False
        
        result = setup_cuda(force_cpu=False)
        
        assert result == "cpu"

    @patch.dict(os.environ, {"TEST_MODEL": "custom-model"})
    @patch('os.path.abspath')
    @patch('os.path.dirname')
    def test_get_model_paths_with_env_var(self, mock_dirname, mock_abspath):
        """Test getting model paths with environment variable"""
        mock_abspath.return_value = "/fake/path"
        mock_dirname.return_value = "/fake"
        
        model_name, model_path = _get_model_paths("TEST_MODEL", "default-model")
        
        assert model_name == "custom-model"
        assert "custom-model" in model_path

    @patch.dict(os.environ, {}, clear=True)
    @patch('os.path.abspath')
    @patch('os.path.dirname')
    def test_get_model_paths_with_default(self, mock_dirname, mock_abspath):
        """Test getting model paths with default value"""
        mock_abspath.return_value = "/fake/path"
        mock_dirname.return_value = "/fake"
        
        model_name, model_path = _get_model_paths("NONEXISTENT_VAR", "default-model")
        
        assert model_name == "default-model"
        assert "default-model" in model_path
