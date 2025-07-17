import os
import yaml
import pytest
from unittest.mock import patch, mock_open
from manifests_generation.secret_builder import SecretBuilder

@pytest.fixture
def secret_builder():
    return SecretBuilder(k8s_manifests_path="test_k8s")


@pytest.fixture
def mock_load_file():
    with patch("manifests_generation.secret_builder.load_file") as mock:
        mock.return_value = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "configmap", "labels": None},
            "data": None,
        }
        yield mock



def test_build_template_new_secret(mock_load_file, secret_builder):
    secret = {"name": "test-secret", "value": "test-value"}
    expected_output = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": "secrets", "labels": {"environment": "production"}},
        "type": "Opaque",
        "data": {"test-secret": "test-value"},
    }

    with patch("os.path.exists", return_value=False):
        result = secret_builder.build_template(secret)

    assert result == expected_output
    mock_load_file.assert_called_once()


def test_build_template_existing_secret(secret_builder):
    secret = {"name": "test-secret", "value": "test-value"}
    existing_data = {
        "kind": "Secret",
        "metadata": {"name": "secrets", "labels": {"environment": "production"}},
        "type": "Opaque",
        "data": {"existing-secret": "existing-value"},
    }
    expected_output = {
        "kind": "Secret",
        "metadata": {"name": "secrets", "labels": {"environment": "production"}},
        "type": "Opaque",
        "data": {
            "existing-secret": "existing-value",
            "test-secret": "test-value",
        },
    }

    with patch("os.path.exists", return_value=True), patch(
        "builtins.open", mock_open(read_data=yaml.dump(existing_data))
    ):
        result = secret_builder.build_template(secret)

    assert result == expected_output


def test_get_configmap_template(mock_load_file, secret_builder):
    result = secret_builder._get_configmap_template()

    expected_template = {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": "configmap", "labels": None},
        "data": None,
    }

    assert result == expected_template
    mock_load_file.assert_called_once()