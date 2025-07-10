import os
from typing import Any, Dict, List
import logging
from tree.attached_file import AttachedFile
import yaml

class PromptBuilder:
    def __init__(
        self
    ):
        self.logger = logging.getLogger(__name__)
        self.attached_files: List[AttachedFile] = []

    def _generate_system_prompt(self, prompt: str) -> List[Dict[str, Any]]:
        """Generate the base prompt for all microservices, providing context for interdependencies."""
        self.logger.info("Generating common prompt for microservices.")
        return [{"type": "text", "text": prompt, "cache_control": {"type": "ephemeral"}}]

    def generate_user_prompt(self, prompt: str) -> List[Dict[str, str]]:
        """Generate a Kubernetes manifest generation prompt for a specific microservice."""
        self.logger.info(
            f"Prompt generated:\n{prompt}"
        )
        return [{"role": "user", "content": prompt}]

    @property
    def is_prod_mode(self):
        return os.getenv("PROD_MODE", "").strip().lower() == "true"
