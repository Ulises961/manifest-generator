from typing import Any, Dict, List
import logging

class PromptBuilder:
    def __init__(
        self,
        microservices: List[Dict[str, Any]],
    ):
        self.prompt = self._generate_base_prompt(microservices)
        self.logger = logging.getLogger(__name__)

    def add_instruction(self, instruction: str):
        self.prompt += f"Instruction: {instruction}\n"

    def add_input(self, input_data: str):
        self.prompt += f"Input: {input_data}\n"

    def add_output(self, output_data: str):
        self.prompt += f"Output: {output_data}\n"

    def get_prompt(self) -> str:
        return self.prompt.strip()

    def attach_files(self, files: list):
        for file in files:
            self.prompt += f"File: {file}\n"
            with open(file, "r") as f:
                content = f.read()
                self.prompt += f"Content: {content}\n"

    def _generate_base_prompt(self, services: List[Dict[str, Any]]) -> str:
        generic_prompt = "Given the following microservices schema:\n"

        for service in services:
            #    Microservice {'name': 'recommendationservice', 'labels': {'app': 'recommendationservice'}, 'command': ['python', 'recommendation_server.py'], 'ports': [8080], 'service-ports': [8080], 'type': 'ClusterIP', 'protocol': 'TCP', 'workload': 'Deployment', 'env': [{'name': 'PYTHONUNBUFFERED', 'key': 'config', 'value': '1'}], 'workdir': '/recommendationservice'} prepared for manifest generation
            generic_prompt += f"{service['name']}: \n\t"
            for key, value in service.items():
                if key == "attached_files":
                    continue
                generic_prompt += f"{key}: {value}\n\t"

            generic_prompt += "\n"

        return generic_prompt

    def generate_prompt(self, microservice: Dict[str, Any]) -> str:
        """Generate a prompt for a specific microservice.

        Args:
            microservice: Dictionary containing microservice information

        Returns:
            str: Generated prompt
        """
        prompt = self.prompt
        prompt += "\n\n"
        prompt += f"The task is to generate a set Kubernetes manifests (YAML format) for the microservice '{microservice['name']}' using the schema presented above.\n"
        prompt += f"Please use it to infer any relations or iterdependencies and produce an appropriate output.\n\n"
        prompt += f"Here are its details:\n\n"
        prompt += f"{microservice['name']}:\n"

        for key, value in microservice.items():
            if key == "attached_files":
                continue
            prompt += f"{key}: {value}\n"

        prompt += "\nGuidelines:\n"
        prompt += "- Use best practices for production-ready workloads.\n"
        prompt += "- Infer appropriate labels (tier, role) based on service name.\n"
        prompt += (
            "- Add liveness/readiness probes if appropriate for a Python-based API.\n"
        )
        prompt += "- Create associated Kubernetes objects if needed (e.g., Service, ConfigMap):\n"
        prompt += "\t\tEach associated manifest must be headed with the object name in lowercase\n"
        prompt += (
            "- Do not guess values for unknowns — use TODO comments where applicable.\n"
        )
        prompt += "- Return only the final Kubernetes manifest in YAML.\n"

        self.logger.info(f"Prompt generated for the {microservice['name']} microservice: {prompt}")
        
        return prompt
