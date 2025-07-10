import os
import pytest
from unittest.mock import patch, MagicMock
from manifests_generation.deployment_builder import DeploymentBuilder

@pytest.fixture
def mock_load_file():
    with patch("manifests_generation.deployment_builder.load_file") as mock:
        yield mock

@pytest.fixture
def mock_remove_none_values():
    with patch("utils.file_utils.remove_none_values") as mock:
        mock.side_effect = lambda x: x  # Return the input as-is for simplicity
        yield mock


@pytest.fixture
def deployment_builder():
    return DeploymentBuilder()

def test_get_deployment_template(mock_load_file, deployment_builder):
    mock_template = {"metadata": {}, "spec": {}}
    mock_load_file.return_value = mock_template

    # Mock the environment variable
    with patch.dict(os.environ, {"DEPLOYMENT_TEMPLATE_PATH": "test_path/deployment.json"}):
        template = deployment_builder._get_deployment_template()

    assert template == mock_template
    
    # The path is calculated relative to the deployment_builder.py file, not the test file
    expected_path = os.path.join(
        os.path.dirname(os.path.abspath("src/manifests_generation/deployment_builder.py")),
        "..",
        "test_path/deployment.json",
    )
    mock_load_file.assert_called_once_with(expected_path)

def test_build_template_basic(mock_remove_none_values, deployment_builder):
    deployment = {
        "name": "test-deployment",
        "labels": {"app": "test"},
        "command": ["/bin/bash"],
        "image": "test-image",
    }

    mock_template = {
        "metadata": {"name": "", "labels": {}},
        "spec": {
            "selector": {"matchLabels": {}},
            "template": {
                "metadata": {"labels": {}},
                "spec": {"containers": [{"name": "", "image": "", "command": []}]},
            },
        },
    }

    with patch.object(deployment_builder, "_get_deployment_template", return_value=mock_template):
        result = deployment_builder.build_template(deployment)

    assert result["metadata"]["name"] == "test-deployment"
    assert result["metadata"]["labels"] == {"app": "test"}
    assert result["spec"]["template"]["spec"]["containers"][0]["image"] == "test-image"
    assert result["spec"]["template"]["spec"]["containers"][0]["command"] == ["/bin/bash"]


def test_build_template_with_env(mock_remove_none_values, deployment_builder):
    deployment = {
        "name": "test-deployment",
        "labels": {"app": "test"},
        "command": ["/bin/bash"],
        "image": "test-image",
        "env": [
            {"name": "ENV_VAR_1", "key": "value1"},
            {"name": "PASSWORD", "key": "password"},
        ],
    }

    mock_template = {
        "metadata": {"name": "", "labels": {}},
        "spec": {
            "selector": {"matchLabels": {}},
            "template": {
                "metadata": {"labels": {}},
                "spec": {"containers": [{"name": "", "image": "", "command": [], "env": []}]},
            },
        },
    }

    with patch.object(deployment_builder, "_get_deployment_template", return_value=mock_template):
        result = deployment_builder.build_template(deployment)

    env_vars = result["spec"]["template"]["spec"]["containers"][0]["env"]
    assert len(env_vars) == 2
    assert env_vars[0]["name"] == "ENV_VAR_1"
    assert env_vars[0]["valueFrom"]["configMapKeyRef"]["key"] == "ENV_VAR_1"
    assert env_vars[1]["name"] == "PASSWORD"
    assert env_vars[1]["valueFrom"]["secretKeyRef"]["key"] == "PASSWORD"


def test_build_template_with_volumes(mock_remove_none_values, deployment_builder):
    deployment = {
        "name": "test-deployment",
        "labels": {"app": "test"},
        "command": ["/bin/bash"],
        "image": "test-image",
        "volumes": [{"name": "volume1", "emptyDir": {}}],
        "volume_mounts": [{"name": "volume1", "mountPath": "/data"}],
    }

    mock_template = {
        "metadata": {"name": "", "labels": {}},
        "spec": {
            "selector": {"matchLabels": {}},
            "template": {
                "metadata": {"labels": {}},
                "spec": {"containers": [{"name": "", "image": "", "command": [], "volumeMounts": []}], "volumes": []},
            },
        },
    }

    with patch.object(deployment_builder, "_get_deployment_template", return_value=mock_template):
        result = deployment_builder.build_template(deployment)

    assert result["spec"]["template"]["spec"]["volumes"] == [{"name": "volume1", "emptyDir": {}}]
    assert result["spec"]["template"]["spec"]["containers"][0]["volumeMounts"] == [
        {"name": "volume1", "mountPath": "/data"}
    ]