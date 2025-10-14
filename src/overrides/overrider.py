from calendar import c
from enum import Enum
import logging
import traceback
from typing import Any, Dict, List, Optional, Tuple, cast, override
import yaml

from overrides.overrides_validator import OverridesValidator


class Overrider:
    """
    A class to override the default behavior of a class.
    """

    def __init__(self, config_path: str):
        """
        Initialize the Overrider with a validator for configuration overrides.

        :param overrides_validator: An instance of a validator to validate configuration overrides.
        """
        self.overrides_validator = OverridesValidator()
        self.logger = logging.getLogger(__name__)
        self.override_config = self.get_config(config_path)

    def get_config(self, config_path: str) -> Optional[Dict[str, Any]]:
        """Load and validate the configuration overrides from a YAML file."""
        if config_path == "":
            self.logger.info("No overrides file provided. Skipping overrides.")
            return None
        try:
            with open(config_path, "r") as file:
                # Load the configuration file
                self.logger.info(f"Loading configuration overrides from {config_path}")
                config = yaml.safe_load(file)

                # Validate the configuration file
                if self.overrides_validator.validate(config):
                    return cast(Dict[str, Any], config)
                else:
                    self.logger.error(
                        f"Configuration overrides validation failed for {config_path}. Please check the file format and content. Ignoring overrides."
                    )
                    return None
        except FileNotFoundError:
            self.logger.exception(
                f"Configuration file not found: {config_path}. Ignoring overrides.",
                exc_info=True,
                stack_info=True,
            )
            return None


    def get_microservice_overrides(self, microservice_name: str) -> Dict[str,Any]:
        """Get the overrides applied to a specific template."""
        overrides = {}
        if not self.override_config:
            self.logger.warning(
                "No override configuration loaded. Returning empty overrides."
            )
            return overrides
        
        for key, value in self.override_config.items():
            if key not in ["version","project","extraManifests"]:
                for microservice, config in value.items():
                    if microservice == microservice_name:
                        overrides[key] = config
        
        self.logger.info(
                f"Returning overrides for service {microservice_name}: {overrides}"
            )

        return cast(Dict[str, Any], overrides)


 