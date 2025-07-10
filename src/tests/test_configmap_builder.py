import os
import yaml
import pytest
from unittest.mock import patch, mock_open
from manifests_generation.configmap_builder import ConfigMapBuilder

@pytest.fixture
def config_map_builder():
    return ConfigMapBuilder(k8s_manifests_path="test_k8s")

@pytest.fixture
def mock_config_map():
    return {"name": "test_key", "value": "test_value"}

@pytest.fixture
def mock_template():
    return {
        "kind": "ConfigMap",
        "metadata": {
            "name": "config",
            "labels": {"environment": "production"}
        },
        "data": {}
    }

@patch("manifests_generation.configmap_builder.load_file")
def test_get_configmap_template(mock_load_file, config_map_builder, mock_template):
    mock_load_file.return_value = mock_template
    template = config_map_builder._get_configmap_template()
    assert template == mock_template
    mock_load_file.assert_called_once()

@patch("os.path.exists")
@patch("builtins.open", new_callable=mock_open, read_data="data: {}")
@patch("manifests_generation.configmap_builder.load_file")
def test_build_template_new_configmap(mock_load_file, mock_open_file, mock_path_exists, config_map_builder, mock_config_map, mock_template):
    mock_path_exists.return_value = False
    mock_load_file.return_value = mock_template

    result = config_map_builder.build_template(mock_config_map)

    assert result["kind"] == "ConfigMap"
    assert result["metadata"]["name"] == "config"
    assert result["metadata"]["labels"] == {"environment": "production"}
    assert result["data"] == {mock_config_map["name"]: mock_config_map["value"]}

@patch("os.path.exists")
@patch("builtins.open", new_callable=mock_open, read_data="data: {}")
def test_build_template_existing_configmap(mock_open_file, mock_path_exists, config_map_builder, mock_config_map):
    mock_path_exists.return_value = True

    result = config_map_builder.build_template(mock_config_map)

    mock_open_file.assert_called_once_with(os.path.join("test_k8s", "config_map.yaml"), "r")
    assert "data" in result
    assert result["data"][mock_config_map["name"]] == mock_config_map["value"]

@patch("os.path.exists")
@patch("builtins.open", new_callable=mock_open, read_data="data: {existing_key: existing_value}")
def test_build_template_update_existing_configmap(mock_open_file, mock_path_exists, config_map_builder, mock_config_map):
    mock_path_exists.return_value = True

    result = config_map_builder.build_template(mock_config_map)

    assert "data" in result
    assert result["data"]["existing_key"] == "existing_value"
    assert result["data"][mock_config_map["name"]] == mock_config_map["value"]