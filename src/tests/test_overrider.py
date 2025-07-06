import pytest
from unittest.mock import MagicMock, patch
from manifests_generation.overrider import Overrider
from validation.overrides_validator import OverridesValidator

@pytest.fixture
def overrider():
    """Fixture to create an Overrider instance."""
    with patch("manifests_generation.overrider.Overrider.__init__", lambda x, y: None):
        instance = Overrider("dummy_path")
        instance.override_config = {
            "services": {
                "test_service": {
                    "lifecycle": {"postStart": {"exec": {"command": ["echo", "Hello"]}}},
                    "affinity": {"nodeAffinity": {"requiredDuringSchedulingIgnoredDuringExecution": {}}},
                    "volumeClaims": {"test_volume": {"name": "test_volume"}},
                    "secrets": [{"name": "test_secret"}],
                }
            },
            "volumeClaims": {"test_volume": {"name": "test_volume"}},
        }
        instance.logger = MagicMock()
        return instance

def test_get_microservice_overrides(overrider):
    """Test get_microservice_overrides method."""
    overrides = overrider.get_microservice_overrides("test_service")
    assert overrides == overrider.override_config["services"]["test_service"]

    overrides = overrider.get_microservice_overrides("nonexistent_service")
    assert overrides == {}

def test_apply_overrides(overrider):
    """Test apply_overrides method."""
    microservice = {"name": "test_service"}
    updated_microservice = overrider.apply_overrides(microservice, "test_service")
    assert updated_microservice == microservice

def test_apply_lifecycle(overrider):
    """Test _apply_lifecycle method."""
    service = {}
    lifecycle_config = {"postStart": {"exec": {"command": ["echo", "Hello"]}}}
    overrider._apply_lifecycle(service, lifecycle_config)
    assert service["spec"]["template"]["spec"]["containers"][0]["lifecycle"]["postStart"] == lifecycle_config["postStart"]

def test_apply_affinity(overrider):
    """Test _apply_affinity method."""
    service = {}
    affinity_config = {"nodeAffinity": {"requiredDuringSchedulingIgnoredDuringExecution": {}}}
    overrider._apply_affinity(service, affinity_config)
    assert service["spec"]["template"]["spec"]["affinity"] == affinity_config

def test_apply_volume_claims(overrider):
    """Test _apply_volume_claims method."""
    service = {"name": "test_service"}
    volume_claims = [{"name": "test_volume"}]
    overrider._apply_volume_claims(service, volume_claims)
    assert service["persistent_volumes"] == volume_claims

def test_apply_secrets(overrider):
    """Test _apply_secrets method."""
    service = {}
    secrets = [{"name": "test_secret"}]
    overrider._apply_secrets(service, secrets)
    # Add assertions based on the expected behavior of _apply_secrets

def test_get_config_file_not_found(overrider):
    """Test get_config method when the file is not found."""
    with patch("builtins.open", side_effect=FileNotFoundError):
        config = overrider.get_config("nonexistent_path")
        assert config is None
        overrider.logger.exception.assert_called_once_with(
            "Configuration file not found: nonexistent_path. Ignoring overrides.",
            exc_info=True,
            stack_info=True,
        )

def test_apply_environment_variables(overrider):
    """Test _apply_environment_variables method."""
    service = {}
    service_env = [{"name": "TEST_ENV", "value": "test_value"}]
    global_env = [{"name": "GLOBAL_ENV", "value": "global_value"}]
    overrider._apply_environment_variables(service, service_env, global_env)
    container = service["spec"]["template"]["spec"]["containers"][0]
    assert {"name": "TEST_ENV", "value": "test_value"} in container["env"]
    assert {"name": "GLOBAL_ENV", "value": "global_value"} in container["env"]

def test_apply_port_config(overrider):
    """Test _apply_port_config method."""
    service = {}
    port_configs = [{"containerPort": 8080}]
    overrider._apply_port_config(service, port_configs)
    container = service["spec"]["template"]["spec"]["containers"][0]
    assert {"containerPort": 8080} in container["ports"]

def test_apply_resource_constraints(overrider):
    """Test _apply_resource_constraints method."""
    service = {}
    resources = {
        "limits": {"cpu": "500m", "memory": "256Mi"},
        "requests": {"cpu": "250m", "memory": "128Mi"},
    }
    overrider._apply_resource_constraints(service, resources)
    container = service["spec"]["template"]["spec"]["containers"][0]
    assert container["resources"]["limits"] == {"cpu": "500m", "memory": "256Mi"}
    assert container["resources"]["requests"] == {"cpu": "250m", "memory": "128Mi"}

def test_apply_probe(overrider):
    """Test _apply_probe method."""
    service = {}
    probe_config = {
        "httpGet": {"path": "/health", "port": 8080},
        "initialDelaySeconds": 5,
        "timeoutSeconds": 2,
    }
    overrider._apply_probe(service, probe_config, "livenessProbe")
    container = service["spec"]["template"]["spec"]["containers"][0]
    assert container["livenessProbe"]["httpGet"] == {"path": "/health", "port": 8080}
    assert container["livenessProbe"]["initialDelaySeconds"] == 5
    assert container["livenessProbe"]["timeoutSeconds"] == 2

def test_apply_metadata(overrider):
    """Test _apply_metadata method."""
    service = {}
    metadata = {
        "annotations": {"key1": "value1"},
        "labels": {"key2": "value2"},
    }
    overrider._apply_metadata(service, metadata)
    assert service["metadata"]["annotations"] == {"key1": "value1"}
    assert service["metadata"]["labels"] == {"key2": "value2"}

def test_process_dependencies(overrider):
    """Test _process_dependencies method."""
    service = {"name": "test_service"}
    service_configs = {
        "test_service": {
            "dependencies": [
                {"service": "dependency1", "required": True, "port": 8080},
                {"service": "dependency2", "required": False, "port": 9090},
            ]
        },
        "dependency1": {},
        "dependency2": {},
    }
    with patch("manifests_generation.overrider.Overrider._ensure_container_spec"):
        overrider._process_dependencies(service, service_configs)
        # Add assertions based on the expected behavior of _process_dependencies


def test_validate_valid_config():
    """Test validate method with a valid configuration."""
    validator = OverridesValidator()
    valid_config = {
        "version": "1.0",
        "project": {"name": "test_project"},
        "services": {
            "test_service": {
                "replicas": 2,
                "image": "test_image",
                "environment": [{"name": "TEST_ENV", "value": "test_value"}],
            }
        }
    }
    with patch("validation.overrides_validator.OverridesValidator._get_schema") as mock_schema:
        mock_schema.return_value = {
            "type": "object",
            "properties": {
                "services": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "replicas": {"type": "integer"},
                            "image": {"type": "string"},
                            "environment": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "value": {"type": "string"},
                                    },
                                    "required": ["name", "value"],
                                },
                            },
                        },
                        "required": ["replicas", "image", "environment"],
                    },
                }
            },
            "required": ["services"],
        }
        assert validator.validate(valid_config) is True


def test_validate_invalid_config():
    """Test validate method with an invalid configuration."""
    validator = OverridesValidator()
    invalid_config = {
        "services": {
            "test_service": {
                "replicas": "two",  # Invalid type
                "image": "test_image",
            }
        }
    }
    with patch("validation.overrides_validator.OverridesValidator._get_schema") as mock_schema:
        mock_schema.return_value = {
            "type": "object",
            "properties": {
                "services": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "replicas": {"type": "integer"},
                            "image": {"type": "string"},
                        },
                        "required": ["replicas", "image"],
                    },
                }
            },
            "required": ["services"],
        }
        assert validator.validate(invalid_config) is False


def test_validate_missing_required_field():
    """Test validate method with a configuration missing a required field."""
    validator = OverridesValidator()
    invalid_config = {
        "services": {
            "test_service": {
                "image": "test_image",  # Missing "replicas"
            }
        }
    }
    with patch("validation.overrides_validator.OverridesValidator._get_schema") as mock_schema:
        mock_schema.return_value = {
            "type": "object",
            "properties": {
                "services": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "replicas": {"type": "integer"},
                            "image": {"type": "string"},
                        },
                        "required": ["replicas", "image"],
                    },
                }
            },
            "required": ["services"],
        }
        assert validator.validate(invalid_config) is False


def test_validate_logs_error_on_invalid_config(caplog):
    """Test that validate method logs an error for an invalid configuration."""
    validator = OverridesValidator()
    invalid_config = {
        "services": {
            "test_service": {
                "replicas": "two",  # Invalid type
                "image": "test_image",
            }
        }
    }
    with patch("validation.overrides_validator.OverridesValidator._get_schema") as mock_schema:
        mock_schema.return_value = {
            "type": "object",
            "properties": {
                "services": {
                    "type": "object",
                    "additionalProperties": {
                        "type": "object",
                        "properties": {
                            "replicas": {"type": "integer"},
                            "image": {"type": "string"},
                        },
                        "required": ["replicas", "image"],
                    },
                }
            },
            "required": ["services"],
        }
        validator.validate(invalid_config)
        assert "Validation error" in caplog.text