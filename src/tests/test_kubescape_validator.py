import subprocess
import pytest
import json
from unittest.mock import patch, MagicMock
from validation.kubescape_validator import KubescapeValidator

@pytest.fixture
def validator():
    return KubescapeValidator(kubescape_path="kubescape")

def mock_subprocess_run_success(*args, **kwargs):
    mock = MagicMock()
    mock.returncode = 0
    mock.stdout = json.dumps({
        "summary": {"complianceScore": 85},
        "controls": [
            {
                "name": "Control1",
                "description": "desc1",
                "status": {"status": "failed"},
                "baseScore": "critical",
                "controlID": "id1"
            },
            {
                "name": "Control2",
                "description": "desc2",
                "status": {"status": "passed"},
                "baseScore": "high",
                "controlID": "id2"
            },
            {
                "name": "Control3",
                "description": "desc3",
                "status": {"status": "failed"},
                "baseScore": "medium",
                "controlID": "id3"
            }
        ]
    })
    mock.stderr = ""
    return mock

def test_kubescape_validator():
    """Test the KubescapeValidator class"""
    validator = KubescapeValidator(kubescape_path="kubescape")
    #test a real file
    assert validator.kubescape_path == "kubescape"
    output = validator.validate_file("/home/ulises/Documents/UniTn/2nd Year/2 semester/Tirocinio/Tool/output/manifests/llm/v0/k8s/deployment/adservice.yaml")
    print(output)
    assert False


def mock_subprocess_run_failure(*args, **kwargs):
    mock = MagicMock()
    mock.returncode = 1
    mock.stdout = ""
    mock.stderr = "error"
    return mock

def mock_subprocess_run_timeout(*args, **kwargs):
    raise subprocess.TimeoutExpired(cmd="kubescape", timeout=300)

def mock_subprocess_run_notfound(*args, **kwargs):
    raise FileNotFoundError()

def mock_subprocess_run_badjson(*args, **kwargs):
    mock = MagicMock()
    mock.returncode = 0
    mock.stdout = "not a json"
    mock.stderr = ""
    return mock

def test_validate_file_success(validator):
    with patch("subprocess.run", side_effect=mock_subprocess_run_success):
        metrics = validator.validate_file("manifest.yaml")
        assert metrics["file"] == "manifest.yaml"
        assert metrics["compliance_score"] == 85
        assert metrics["total_controls"] == 3
        assert metrics["severity_counts"]["critical"] == 1
        assert metrics["severity_counts"]["medium"] == 1
        assert metrics["severity_counts"]["high"] == 0
        assert metrics["severity_counts"]["low"] == 0
        assert metrics["severity_counts"]["info"] == 0
        assert len(metrics["failed_controls"]) == 2

def test_validate_file_failure(validator):
    with patch("subprocess.run", side_effect=mock_subprocess_run_failure):
        with pytest.raises(RuntimeError) as excinfo:
            validator.validate_file("manifest.yaml")
        assert "Kubescape scan failed" in str(excinfo.value)

def test_validate_file_timeout(validator):
    with patch("subprocess.run", side_effect=mock_subprocess_run_timeout):
        with pytest.raises(RuntimeError) as excinfo:
            validator.validate_file("manifest.yaml")
        assert "timed out" in str(excinfo.value)

def test_validate_file_notfound(validator):
    with patch("subprocess.run", side_effect=mock_subprocess_run_notfound):
        with pytest.raises(RuntimeError) as excinfo:
            validator.validate_file("manifest.yaml")
        assert "binary not found" in str(excinfo.value)

def test_validate_file_badjson(validator):
    with patch("subprocess.run", side_effect=mock_subprocess_run_badjson):
        with pytest.raises(RuntimeError) as excinfo:
            validator.validate_file("manifest.yaml")
        assert "Failed to parse Kubescape output as JSON" in str(excinfo.value)

def test_save_metrics_to_csv(tmp_path, validator):
    metrics_list = [
        {
            "file": "manifest.yaml",
            "compliance_score": 90,
            "severity_counts": {
                "critical": 1,
                "high": 2,
                "medium": 0,
                "low": 0,
                "info": 0,
            },
            "total_controls": 5,
            "failed_controls": [{"name": "c1"}, {"name": "c2"}, {"name": "c3"}],
        }
    ]
    output_file = tmp_path / "results.csv"
    validator.save_metrics_to_csv(metrics_list, str(output_file))
    content = output_file.read_text()
    assert "manifest.yaml" in content
    assert "critical" in content
    assert "failed_count" in content
    assert "3" in content