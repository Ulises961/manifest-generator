import os
import pytest
from unittest.mock import patch, MagicMock
from manifests_generation.pvc_builder import PVCBuilder

@pytest.fixture
def pvc_builder():
    return PVCBuilder()


@pytest.fixture
def pvc_data():
    return {
        "name": "test-pvc",
        "labels": {"app": "test-app"},
        "storage_class": "standard",
        "access_modes": ["ReadWriteOnce"],
        "resources": "10Gi",
    }


@pytest.fixture
def pvc_template():
    return {
        "metadata": {
            "name": "",
            "labels": {}
        },
        "spec": {
            "storageClassName": "",
            "accessModes": [],
            "resources": {
                "requests": {
                    "storage": ""
                }
            }
        }
    }


@patch("manifests_generation.pvc_builder.load_file")
def test_build_template(mock_load_file, pvc_builder, pvc_data, pvc_template):
    mock_load_file.return_value = pvc_template

    result = pvc_builder.build_template(pvc_data)

    assert result["metadata"]["name"] == pvc_data["name"]
    assert result["metadata"]["labels"] == pvc_data["labels"]
    assert result["spec"]["storageClassName"] == pvc_data["storage_class"]
    assert result["spec"]["accessModes"] == pvc_data["access_modes"]
    assert result["spec"]["resources"]["requests"]["storage"] == pvc_data["resources"]

    mock_load_file.assert_called_once()


@patch("manifests_generation.pvc_builder.load_file")
def test_get_pvc_template(mock_load_file, pvc_builder, pvc_template):
    mock_load_file.return_value = pvc_template

    result = pvc_builder._get_pvc_template()

    assert result == pvc_template
    mock_load_file.assert_called_once_with(
        os.path.join(
            os.path.dirname(os.path.abspath("src/manifests_generation/pvc_builder.py")),
            "..",
            os.getenv("PVC_TEMPLATE_PATH", "resources/k8s_templates/pvc.json"),
        )
    )


@patch("manifests_generation.pvc_builder.load_file")
def test_build_template_with_missing_fields(mock_load_file, pvc_builder, pvc_template):
    mock_load_file.return_value = pvc_template

    pvc_data = {
        "name": "test-pvc",
        # Missing labels, storage_class, access_modes, and resources
    }

    result = pvc_builder.build_template(pvc_data)
    assert result["metadata"]["name"] == pvc_data["name"]
    assert "labels" not in result["metadata"]
    assert "spec" not in result

    mock_load_file.assert_called_once()
