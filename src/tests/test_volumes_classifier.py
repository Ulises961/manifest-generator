import pytest
import os
from unittest.mock import patch, mock_open
from embeddings.volumes_classifier import VolumesClassifier


class TestVolumesClassifier:
    """Test suite for VolumesClassifier"""

    @patch('builtins.open', mock_open(read_data="/data\n/var/log\n/tmp\n"))
    @patch('os.path.exists')
    def test_load_volumes_success(self, mock_exists):
        """Test loading volumes from file"""
        mock_exists.return_value = True
        
        classifier = VolumesClassifier()
        
        assert "/data" in classifier.volumes
        assert "/var/log" in classifier.volumes
        assert "/tmp" in classifier.volumes
        assert len(classifier.volumes) == 3

    @patch('os.path.exists')
    def test_load_volumes_file_not_found(self, mock_exists):
        """Test FileNotFoundError when volumes file doesn't exist"""
        mock_exists.return_value = False
        
        with pytest.raises(FileNotFoundError, match="Volumes file not found"):
            VolumesClassifier()

    @patch('builtins.open', mock_open(read_data="/data\n/var/log\n"))
    @patch('os.path.exists')
    def test_decide_volume_persistence_true(self, mock_exists):
        """Test volume persistence returns True for known volumes"""
        mock_exists.return_value = True
        classifier = VolumesClassifier()
        
        result = classifier.decide_volume_persistence("/data")
        
        assert result is True

    @patch('builtins.open', mock_open(read_data="/data\n/var/log\n"))
    @patch('os.path.exists')
    def test_decide_volume_persistence_false(self, mock_exists):
        """Test volume persistence returns False for unknown volumes"""
        mock_exists.return_value = True
        classifier = VolumesClassifier()
        
        result = classifier.decide_volume_persistence("/unknown")
        
        assert result is False

    @patch('builtins.open', mock_open(read_data="/data\n\n/var/log\n  \n/tmp\n"))
    @patch('os.path.exists')
    def test_load_volumes_with_empty_lines(self, mock_exists):
        """Test loading volumes with empty lines and whitespace"""
        mock_exists.return_value = True
        
        classifier = VolumesClassifier()
        
        # Should only have non-empty, stripped lines
        assert len(classifier.volumes) == 3
        assert "" not in classifier.volumes
        assert "  " not in classifier.volumes

    @patch('builtins.open', mock_open(read_data="  /data  \n  /var/log  \n"))
    @patch('os.path.exists')
    def test_load_volumes_strips_whitespace(self, mock_exists):
        """Test that loaded volumes are stripped of whitespace"""
        mock_exists.return_value = True
        
        classifier = VolumesClassifier()
        
        assert "/data" in classifier.volumes
        assert "/var/log" in classifier.volumes
        assert "  /data  " not in classifier.volumes

    @patch.dict(os.environ, {"LABELS_PATH": "custom/path/volumes.json"})
    @patch('builtins.open', mock_open(read_data="/custom\n"))
    @patch('os.path.exists')
    def test_load_volumes_custom_path(self, mock_exists):
        """Test loading volumes from custom path via environment variable"""
        mock_exists.return_value = True
        
        classifier = VolumesClassifier()
        
        assert "/custom" in classifier.volumes
