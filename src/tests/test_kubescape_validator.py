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
        "summaryDetails": {
            "complianceScore": 85,
            "controls": {
                "id1": {
                    "name": "Control1",
                    "statusInfo": {"status": "failed"}
                },
                "id2": {
                    "name": "Control2",
                    "statusInfo": {"status": "passed"}
                },
                "id3": {
                    "name": "Control3",
                    "statusInfo": {"status": "failed"}
                }
            },
            "controlsSeverityCounters": {
                "criticalSeverity": 1,
                "highSeverity": 0,
                "mediumSeverity": 1,
                "lowSeverity": 0
            }
        },
        "results": [
            {
                "controls": [
                    {
                        "name": "Control1",
                        "controlID": "id1",
                        "status": {"status": "failed"},
                        "rules": []
                    },
                    {
                        "name": "Control3",
                        "controlID": "id3",
                        "status": {"status": "failed"},
                        "rules": []
                    }
                ]
            }
        ]
    })
    mock.stderr = ""
    return mock

def test_kubescape_validator():
    """Test the KubescapeValidator class initialization"""
    validator = KubescapeValidator(kubescape_path="kubescape")
    assert validator.kubescape_path == "kubescape"
    
    # Test with custom path
    custom_validator = KubescapeValidator(kubescape_path="/usr/local/bin/kubescape")
    assert custom_validator.kubescape_path == "/usr/local/bin/kubescape"


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
        assert metrics["passed_controls"] == 1
        assert metrics["failed_controls"] == 2
        assert len(metrics["failed_controls_details"]) == 2

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
    metrics_dict = {
        "service1": {
            "file": "manifest.yaml",
            "resource_type": "deployment",
            "compliance_score": 90,
            "calculated_compliance_score": 90,
            "relevant_controls": 5,
            "irrelevant_controls": 0,
            "passed_controls": 2,
            "failed_controls": 3,
            "total_controls": 5,
            "severity_counts": {
                "critical": 1,
                "high": 2,
                "medium": 0,
                "low": 0,
            },
            "failed_controls_details": [{"name": "c1"}, {"name": "c2"}, {"name": "c3"}],
        }
    }
    output_file = tmp_path / "results.csv"
    validator.save_metrics_to_csv(metrics_dict, str(output_file))
    content = output_file.read_text()
    assert "manifest.yaml" in content
    assert "deployment" in content
    assert "3" in content  # failed_controls count