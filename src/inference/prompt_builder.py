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
        self.is_prod_mode = os.getenv("DEV_MODE", "false").lower() == "false"
        self.attached_files: List[AttachedFile] = []

    def attach_files(self, files: list):
        """Attach files to the prompt for additional context."""
        self.attached_files.extend(files)

    def attach_file(self, file: AttachedFile):
        """Attach a file to the prompt for additional context."""
        self.attached_files.append(file)

    def include_attached_files(self, prompt: str) -> str:
        """Include attached files in the prompt for a specific microservice."""
        if self.is_prod_mode and len(self.attached_files) > 0:
            prompt += f"\nAttached files for additional context:\n"
            for file in self.attached_files:
                prompt += f" {file.name}: {file}"
        return prompt

    def _generate_system_prompt(self) -> List[Dict[str, Any]]:
        """Generate the base prompt for all microservices, providing context for interdependencies."""
        self.logger.info("Generating base prompt for microservices.")

        # Strong role assignment and formatting constraint for small models
        prompt = (
            "You are a strict Kubernetes manifests generator.\n"
            "You only output valid raw Kubernetes YAML manifests starting off from a set of microservices described next.\n"
            "The set of microservices are interrelated and compose an application.\n"
            "Guidelines:\n"
            "- Use production-ready Kubernetes best practices.\n"
            "- If needed, add Service, ConfigMap, Secret, or PVC.\n"
            "- Use labels like `app`, `tier`, `role`, and `environment`.\n"
            "- Use TODO placeholders for values that cannot be confidently inferred.\n"
            "- Image name must be the same as the microservice name.\n"
            "- Separate each manifest with '---' if multiple objects are required.\n"
            "- The result must be directly usable with `kubectl apply -f` or in CI/CD pipelines.\n"
            "**No other output is allowed. Do not explain, do not reason, do not output markdown or comments.**\n"
            "**Immediately output only valid Kubernetes YAML for the service.**\n"
        )

        # prompt += "Here is the schema for all microservices in this system:\n\n"
        # for index, service in enumerate(services):
        #     if index > 0:
        #         prompt += ", "
        #     prompt += f"{service['name']}"
        #     # for key, value in service.items():
        #     #     if key != "attached_files" and key != "manifests":
        #     #         prompt += f"  {key}: {value}\n"
        #     # prompt += "\n"
        # prompt += ".\n"
        # prompt += (
        #     "Use the above to understand context and infer common configurations "
        #     "or interdependencies between services, but do not explain them.\n"
        # )

        return [{"type": "text", "text": prompt, "cache_control": {"type": "ephemeral"}}]

    def generate_prompt(self, microservice: Dict[str, Any], microservices: List[Dict[str,Any]]) -> List[Dict[str, str]]:
        """Generate a Kubernetes manifest generation prompt for a specific microservice."""
        
        prompt = f"Now generate Kubernetes manifests in YAML format for the microservice '{microservice['name']}'.\n\n"

        prompt += "Microservice details:\n"
        
        for key, value in microservice.items():
            if key != "attached_files" and key != "manifests":
                prompt += f"  {key}: {value}\n"

        prompt += "Output:\n"

        self.logger.info(
            f"Prompt generated for the {microservice['name']} microservice:\n{prompt}"
        )
        return [{"role": "user", "content": prompt}]
