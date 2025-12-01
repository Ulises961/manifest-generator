import pytest
from unittest.mock import MagicMock, patch
from overrides.overrider import Overrider
from overrides.overrides_validator import OverridesValidator

@pytest.fixture
def overrider():
    """Fixture to create an Overrider instance."""
    instance = Overrider()
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
    instance._config_path = "test_config.yaml"
    instance.logger = MagicMock()
    return instance

def test_get_microservice_overrides(overrider):
    """Test get_microservice_overrides method."""
    # Mock get_config to return the override_config
    with patch.object(overrider, 'get_config', return_value=overrider.override_config):
        overrides = overrider.get_microservice_overrides("test_service")
        
        # The method returns only the service-specific overrides from the services dict
        expected = overrider.override_config["services"]["test_service"]
        assert "lifecycle" in overrides.get("services", {})
        
        overrides = overrider.get_microservice_overrides("nonexistent_service")
        assert overrides == {}

def test_get_config_file_not_found(overrider):
    """Test get_config method when the file is not found."""
    with patch("builtins.open", side_effect=FileNotFoundError):
        config = overrider.get_config("nonexistent_path")
        assert config is None
        overrider.logger.warning.assert_called_once_with(
            "Configuration file not found: nonexistent_path. Ignoring overrides.",
            exc_info=False,
            stack_info=False,
        )


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
    with patch("overrides.overrides_validator.OverridesValidator._get_schema") as mock_schema:
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
    with patch("overrides.overrides_validator.OverridesValidator._get_schema") as mock_schema:
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
    with patch("overrides.overrides_validator.OverridesValidator._get_schema") as mock_schema:
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
    with patch("overrides.overrides_validator.OverridesValidator._get_schema") as mock_schema:
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