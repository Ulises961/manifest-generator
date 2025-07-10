import os
import shutil
import pytest
import yaml
from unittest.mock import MagicMock, patch
from manifests_generation.manifest_builder import ManifestBuilder

@pytest.fixture
def mock_overrider():
    with patch("manifests_generation.manifest_builder.Overrider") as MockOverrider:
        yield MockOverrider

@pytest.fixture
def mock_configmap_builder():
    with patch("manifests_generation.manifest_builder.ConfigMapBuilder") as MockConfigMapBuilder:
        yield MockConfigMapBuilder

@pytest.fixture
def mock_service_builder():
    with patch("manifests_generation.manifest_builder.ServiceBuilder") as MockServiceBuilder:
        yield MockServiceBuilder

@pytest.fixture
def mock_deployment_builder():
    with patch("manifests_generation.manifest_builder.DeploymentBuilder") as MockDeploymentBuilder:
        yield MockDeploymentBuilder

@pytest.fixture
def mock_statefulset_builder():
    with patch("manifests_generation.manifest_builder.StatefulSetBuilder") as MockStatefulSetBuilder:
        yield MockStatefulSetBuilder

@pytest.fixture
def mock_pvc_builder():
    with patch("manifests_generation.manifest_builder.PVCBuilder") as MockPVCBuilder:
        yield MockPVCBuilder

@pytest.fixture
def mock_secret_builder():
    with patch("manifests_generation.manifest_builder.SecretBuilder") as MockSecretBuilder:
        yield MockSecretBuilder

@pytest.fixture
def mock_skaffold_builder():
    with patch("manifests_generation.manifest_builder.SkaffoldConfigBuilder") as MockSkaffoldBuilder:
        yield MockSkaffoldBuilder

@pytest.fixture
def manifest_builder(mock_overrider, mock_configmap_builder, mock_service_builder, mock_deployment_builder,
                     mock_statefulset_builder, mock_pvc_builder, mock_secret_builder, mock_skaffold_builder):
    # Configure mocks to return real dictionaries
    mock_deployment_builder.return_value.build_template.return_value = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {"name": "test-service"}
    }
    
    mock_service_builder.return_value.build_template.return_value = {
        "apiVersion": "v1",
        "kind": "Service", 
        "metadata": {"name": "test-service"}
    }
    
    mock_pvc_builder.return_value.build_template.return_value = {
        "apiVersion": "v1",
        "kind": "PersistentVolumeClaim",
        "metadata": {"name": "test-pvc"}
    }
    
    mock_secret_builder.return_value.build_template.return_value = {
        "apiVersion": "v1",
        "kind": "Secret",
        "metadata": {"name": "test-secret"}
    }
    
    mock_configmap_builder.return_value.build_template.return_value = {
        "apiVersion": "v1", 
        "kind": "ConfigMap",
        "metadata": {"name": "test-config"}
    }
    
    mock_statefulset_builder.return_value.build_template.return_value = {
        "apiVersion": "apps/v1",
        "kind": "StatefulSet",
        "metadata": {"name": "test-statefulset"}
    }
    
    # Configure Skaffold builder mocks
    mock_skaffold_builder.return_value.build_template.return_value = {
        "apiVersion": "skaffold/v4beta3",
        "kind": "Config",
        "metadata": {"name": "skaffold-config"}
    }
    
    mock_skaffold_builder.return_value.build_kustomization_template.return_value = {
        "apiVersion": "kustomize.config.k8s.io/v1beta1",
        "kind": "Kustomization",
        "resources": []
    }
    
    return ManifestBuilder(config_path="mock_config_path")

def test_generate_manifests_deployment(manifest_builder, mock_deployment_builder):
    microservice = {
        "name": "test-service",
        "workload": "Deployment",
        "ports": [{"port": 80}],
        "persistent_volumes": [{"name": "test-pvc"}],
        "secrets": [{"name": "test-secret"}],
        "env": [{"name": "test-config"}]
    }

    manifest_builder.generate_manifests(microservice)

    assert "deployment" in microservice["manifests"]
    assert "service" in microservice["manifests"]
    assert "pvc" in microservice["manifests"]
    assert "secret" in microservice["manifests"]
    assert "config_map" in microservice["manifests"]

def test_generate_manifests_statefulset(manifest_builder, mock_statefulset_builder):
    microservice = {
        "name": "test-statefulset",
        "workload": "StatefulSet",
    }

    manifest_builder.generate_manifests(microservice)

    assert "stateful_set" in microservice["manifests"]

def test_generate_skaffold_config(manifest_builder, mock_skaffold_builder):
    microservices = [{"name": "test-service"}]
    output_dir = "mock_output_dir"

    skaffold_path = manifest_builder.generate_skaffold_config(microservices, output_dir)

    assert skaffold_path == os.path.join(output_dir, "skaffold.yaml")
    shutil.rmtree(output_dir, ignore_errors=True)  # Clean up the mock output directory

def test_generate_kustomization_file(manifest_builder, mock_skaffold_builder):
    output_dir = "mock_output_dir"

    kustomization_path = manifest_builder.generate_kustomization_file(output_dir)

    assert kustomization_path == os.path.join(output_dir, "kustomization.yaml")
    shutil.rmtree(output_dir, ignore_errors=True)  # Clean up the mock output directory

def test_save_yaml(manifest_builder):
    template = {"key": "value"}
    path = "mock_path.yaml"

    with patch("builtins.open", create=True) as mock_open, patch("os.makedirs") as mock_makedirs:
        mock_file = mock_open.return_value.__enter__.return_value
        manifest_builder._save_yaml(template, path)

        mock_makedirs.assert_called_once_with(os.path.dirname(path), exist_ok=True)
        mock_open.assert_called_once_with(path, "w")
        mock_file.write.assert_called()