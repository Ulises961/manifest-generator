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
        self.prompt = "You are a DevOps assistant tasked with generating Kubernetes manifests.\n\n"
        self.prompt += "Here is the schema for all microservices in this system:\n\n"

        for service in services:
            self.prompt += f"Microservice: {service['name']}\n"
            for key, value in service.items():
                if key != "attached_files":
                    self.prompt += f"  {key}: {value}\n"
            self.prompt += "\n"

        self.prompt += (
            "Use the above context to infer relationships, shared configurations, "
            "and any relevant interdependencies between services.\n"
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
        prompt += "- Use production-ready best practices.\n"
        prompt += "- Include Deployment and Service at minimum. Add ConfigMap, Secret, PVC, Ingress, etc., if required.\n"
        prompt += "- Infer appropriate metadata like labels (tier, role, environment) from the service name.\n"
        prompt += "- Use TODO placeholders for values you cannot confidently infer.\n"
        prompt += (
            "- Do NOT include explanations, comments, markdown or any other extra text in the output.\n"
        )
        prompt += "- Return only the final Kubernetes YAML manifest.\n"
        prompt += "- If multiple Kubernetes objects are needed, separate them with '---' and include the object type as a comment above each.\n"
        prompt += "- The result must be directly usable in a CI/CD or `kubectl apply -f` pipeline.\n"

        prompt += "\nOutput:\n"

        self.logger.info(
            f"Prompt generated for the {microservice['name']} microservice:\n {prompt}"
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
        self.prompt = """
        You are a senior DevOps engineer reviewing Kubernetes manifests for a microservice-based system.

        Your task is to review and improve these YAML manifests to ensure:
        1. They follow production best practices (security, scalability, observability, reliability).
        2. They include all required fields (resource limits, probes, labels, volumes, secrets).
        3. They coordinate properly across services (e.g., environment variables, service names, configs).
        4. They are ready to be deployed in a real-world CI/CD pipeline using `kubectl apply -f`.

        Guidelines:
        - Maintain the structure and intention of the original manifests.
        - Improve where needed — do not guess unknowns, insert '# TODO' where applicable.
        - Include all changes as valid Kubernetes YAML.
        - Do not include any comments, explanations, or markdown.
        - Do not regenerate unchanged parts unnecessarily.

        If multiple manifests are returned, separate them using '---' and place a YAML comment with the object type above each manifest (e.g., `# Deployment`, `# Service`).
        """
