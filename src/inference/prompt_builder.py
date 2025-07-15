import os
from typing import Any, Dict, List
import logging
from tree.attached_file import AttachedFile
import yaml


class PromptBuilder:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def _generate_system_prompt(self, prompt: str) -> List[Dict[str, Any]]:
        """Generate the base prompt for all microservices, providing context for interdependencies."""
        self.logger.info("Generating common prompt for microservices.")

        # For Anthropic's caching, the system message should be structured correctly
        return [
            {
                "type": "text",
                "text": prompt,
                "cache_control": {"type": "ephemeral"} if self.is_caching_enabled else None
            }
        ]

    def generate_user_prompt(self, prompt: str) -> List[Dict[str, Any]]:
        """Generate a Kubernetes manifest generation prompt for a specific microservice."""
        return [{"role": "user", "content": prompt}]

    @property
    def is_caching_enabled(self) -> bool:
        """Check if caching should be enabled based on environment."""
        return os.getenv("ENABLE_CACHING", "true").lower() == "true"

    @property
    def is_prod_mode(self):
        return os.getenv("PROD_MODE", "").strip().lower() == "true"
