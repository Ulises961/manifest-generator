import os
from typing import Any, Dict, List
import logging

from tree.attached_file import AttachedFile


class PromptBuilder:
    def __init__(
        self,
        microservices: List[Dict[str, Any]],
    ):
        self.logger = logging.getLogger(__name__)
        self.prompt = self._generate_base_prompt(microservices)
        self.is_prod_mode = os.getenv("DEV_MODE", "false").lower() == "false"
        self.attached_files: List[AttachedFile] = []

    def add_instruction(self, instruction: str):
        self.prompt += f"Instruction: {instruction}\n"

    def add_output(self, output_data: str):
        self.prompt += f"Output: {output_data}\n"

    def get_prompt(self) -> str:
        return self.prompt.strip()

    def attach_files(self, files: list):
        """Attach files to the prompt for additional context."""
        self.attached_files.extend(files)

    def attach_file(self, file: AttachedFile):
        """Attach a file to the prompt for additional context."""
        self.attached_files.append(file)

    def include_attached_files(self):
        """Include attached files in the prompt for a specific microservice."""
        if self.is_prod_mode and len(self.attached_files) > 0:
            self.prompt += f"\nAttached files for additional context:\n"
            for file in self.attached_files:
                self.prompt += f" {file.name}: {file}"
            

    def _generate_base_prompt(self, services: List[Dict[str, Any]]) -> str:
        """Generate the base prompt for all microservices, providing context for interdependencies."""
        self.logger.info("Generating base prompt for microservices.")

        # Strong role assignment and formatting constraint for small models
        self.prompt = (
            "You are a strict Kubernetes YAML generator.\n"
            "You only output valid raw Kubernetes YAML manifests.\n"
            "Do not explain, do not reason, do not output markdown or comments.\n\n"
        )

        self.prompt += "Here is the schema for all microservices in this system:\n\n"
        for service in services:
            self.prompt += f"Microservice: {service['name']}\n"
            for key, value in service.items():
                if key != "attached_files":
                    self.prompt += f"  {key}: {value}\n"
            self.prompt += "\n"

        self.prompt += (
            "Use the above to understand context and infer common configurations "
            "or interdependencies between services, but do not explain them.\n"
        )

        return self.prompt

    def generate_prompt(self, microservice: Dict[str, Any]) -> str:
        """Generate a Kubernetes manifest generation prompt for a specific microservice."""
        prompt = self.prompt + "\n"

        prompt += f"Now generate Kubernetes manifests in YAML format for the microservice '{microservice['name']}'.\n\n"

        prompt += "Microservice details:\n"
        
        for key, value in microservice.items():
            if key != "attached_files":
                prompt += f"  {key}: {value}\n"

        if self.is_prod_mode and microservice.get("attached_files"):
            prompt += f"\nAttached files for additional context:\n  {microservice['attached_files']}\n"

        prompt += "\nGuidelines:\n"
        prompt += "- Use production-ready Kubernetes best practices.\n"
        prompt += "- Include at minimum a Deployment or StatefulSet and a Service.\n"
        prompt += "- If needed, add ConfigMap, Secret, or PVC.\n"
        prompt += "- Use labels like `app`, `tier`, `role`, and `environment`.\n"
        prompt += "- Use TODO placeholders for values that cannot be confidently inferred.\n"
        prompt += "- Output ONLY valid raw Kubernetes YAML — no explanations, no markdown, no comments.\n"
        prompt += "- Separate each manifest with '---' if multiple objects are required.\n"
        prompt += "- The result must be directly usable with `kubectl apply -f` or in CI/CD pipelines.\n"
        prompt += " **Immediately output only valid Kubernetes YAML for the service below.**\n"
        prompt += "**Begin directly with `apiVersion:`. No other output is allowed.**\n"


        self.logger.info(
            f"Prompt generated for the {microservice['name']} microservice:\n{prompt}"
        )
        return prompt

    def clear_prompt(self):
        """Clear the prompt."""
        self.prompt = ""

    def create_prompt(self, instruction: str, output_data: str):
        """Create a prompt with instruction and output data."""
        self.prompt = f"Instruction: {instruction}\nOutput: {output_data}\n"

    def generate_second_pass_prompt(self) -> None:
        """Generate a second pass prompt to optimize the already generated manifests."""

        self.clear_prompt()
        self.prompt = (
            "You are a senior DevOps engineer. Your task is to strictly review and improve Kubernetes manifests.\n\n"
            "Requirements:\n"
            "1. Enforce production best practices (security, scalability, observability, reliability).\n"
            "2. Ensure all required fields are present (resources, probes, labels, volumes, secrets).\n"
            "3. Ensure manifests coordinate across services (env vars, service names, config refs).\n"
            "4. Output must be valid and directly usable with `kubectl apply -f`.\n\n"
            "Guidelines:\n"
            "- DO NOT guess unknown values. Use '# TODO' where needed.\n"
            "- DO NOT explain anything or include markdown/comments.\n"
            "- DO NOT regenerate unchanged content unless improvement is necessary.\n"
            "- Output ONLY valid raw Kubernetes YAML.\n"
            "- If returning multiple manifests, separate with '---' and prefix with a YAML comment of the object type (e.g., '# Deployment').\n\n"
            "Begin improved YAML output now:\n"
        )