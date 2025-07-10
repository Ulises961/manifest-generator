import os
import pytest
from manifests_generation.skaffold_config_builder import SkaffoldConfigBuilder

@pytest.fixture
def builder():
    return SkaffoldConfigBuilder()

def test_build_template(builder):
    microservices = [
        {"name": "service1", "metadata": {"dockerfile": "path/to/service1"}},
        {"name": "service2", "metadata": {"dockerfile": "path/to/service2"}}
    ]
    manifests_path = "path/to/manifests"
    result = builder.build_template(microservices, manifests_path)

    assert result["apiVersion"] == "skaffold/v3"
    assert result["kind"] == "Config"
    assert result["metadata"]["name"] == "app"
    assert len(result["build"]["artifacts"]) == 2
    assert result["build"]["artifacts"][0]["image"] == "service1"
    assert result["build"]["artifacts"][0]["context"] == "path/to/service1"
    assert result["manifests"]["kustomize"]["paths"] == [manifests_path]

def test_build_kustomization_template_with_empty_dirs(builder, tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    monkeypatch.setenv("K8S_MANIFESTS_PATH", "k8s")
    
    result = builder.build_kustomization_template(str(output_dir))
    assert result["apiVersion"] == "kustomize.config.k8s.io/v1beta1"
    assert result["kind"] == "Kustomization"
    assert result["metadata"]["name"] == "manifests"
    assert result["resources"] == []

def test_build_kustomization_template_with_files(builder, tmp_path, monkeypatch):
    output_dir = tmp_path / "output"
    k8s_dir = output_dir / "k8s"
    deployment_dir = k8s_dir / "deployment"
    service_dir = k8s_dir / "service"
    deployment_dir.mkdir(parents=True)
    service_dir.mkdir(parents=True)

    # Create mock files
    (deployment_dir / "deployment1.yaml").write_text("mock content")
    (service_dir / "service1.yaml").write_text("mock content")
    monkeypatch.setenv("K8S_MANIFESTS_PATH", "k8s")

    result = builder.build_kustomization_template(str(output_dir))
    assert "k8s/deployment/deployment1.yaml" in result["resources"]
    assert "k8s/service/service1.yaml" in result["resources"]
    assert len(result["resources"]) == 2