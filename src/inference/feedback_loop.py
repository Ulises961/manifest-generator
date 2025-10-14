import logging
import os
from re import I
import sys
from typing import Any, Dict, List, Optional

from caseutil import to_snake
from click import prompt
from inference.prompt_builder import PromptBuilder
from inference.llm_client import LLMClient
from manifests_generation.manifest_builder import ManifestBuilder
from overrides import overrider
from overrides.overrider import Overrider
from utils.file_utils import load_json_file, load_yaml_file
from validation.kubescape_validator import KubescapeValidator
import traceback


class ManifestFeedbackLoop:
    """
    Class to handle the feedback loop for manifest generation.
    It processes the output from the LLM and updates the microservice manifests accordingly.
    """

    def __init__(
        self,
        generator: LLMClient,
        validator: KubescapeValidator,
        manifest_builder: ManifestBuilder,
        overrider: Optional[Overrider] = None,
    ):
        self.logger = logging.getLogger(__name__)
        self.generator = generator
        self.validator = validator
        self.prompt_builder = PromptBuilder()

        self.manifest_builder = manifest_builder
        self.overrider = overrider

    def generate_manifests(
        self,
        microservices: List[Dict[str, Any]],
        manifests_path: str,
        alternative_path: Optional[str] = None,
    ):
        """
        Initialize the feedback loop with the microservices manifests.
        """
        self.logger.info("Initializing feedback loop with microservices manifests.")

        system_prompt = (
            "You are a strict Kubernetes manifests generator.\n"
            "You only output valid raw Kubernetes YAML manifests starting off from a set of microservices described next.\n"
        )
        for microservice in microservices:
            system_prompt += f"  - {microservice['name']}\n"

        system_prompt += (
            "The set of microservices are interrelated and compose an application.\n"
            "Guidelines:\n"
            "- Use production-ready Kubernetes best practices.\n"
            "- If needed, add Service, ServiceAccount, ConfigMap, Secret, or PVC.\n"
            "- Use resource requests and limits for CPU and memory.\n"
            "- Use TODO placeholders for values that cannot be confidently inferred.\n"
            "- If not specified, the image name must be the same as the microservice name.\n"
            "- Services with multiple ports require a name to differentiate them at deploy time, consider this a best practice.\n"
            "- Separate each manifest with '---' if multiple objects are required.\n"
            "- The result must be directly usable with `kubectl apply -f` or in CI/CD pipelines.\n"
            "- Maintain a uniform and syntactically cohesive style throughout manifests.\n"
            "**No other output is allowed. Do not explain, do not reason, do not output markdown or comments.**\n"
            "**Immediately output only valid Kubernetes YAML for the service.**\n"
        )

        for microservice in microservices:
            self.logger.info(
                f"Generating manifests for child... {microservice['name']}"
            )

            prompt = f"""Now generate Kubernetes manifests in YAML format for the microservice '{microservice['name']}'.\n
                Details:\n"""

            for key, value in microservice.items():
                if key != "manifests" and key != "metadata":
                    prompt += f"  {key}: {value}\n"

            user_prompt = self.prompt_builder.generate_user_prompt(prompt)
            self.logger.info(f"User prompt: {user_prompt}")

            if os.getenv("DRY_RUN", "false").lower() == "true":
                self.logger.info(f"Dry mode enabled, skipping LLM inference.\n\n----\n")
                continue

            self.query_llm(
                user_prompt,
                system_prompt,
                manifests_path,
                microservice["name"],
                alternative_path,
            )

    def review_with_llm(self, manifests_path: str) -> Dict[str, Any]:
        """
        Review the generated manifests with the LLM to ensure quality and compliance.
        """
        self.logger.info("Starting the review process with LLM.")

        system_prompt = (
            "You are a Kubernetes manifests reviewer.\n"
            "You will be provided with Kubernetes manifests.\n"
            "Your task is to review them for best practices, security, and correctness.\n"
            "Guidelines:\n"
            " - Output a two sections json: 'Valid Cluster: True/False' and 'Feedback'. \n"
            " - In 'Valid Cluster', state 'True' if the cluster is valid: in your opinion would correctly execute; 'False' otherwise.\n"
            " - In 'Feedback', provide specific suggestions for improvement or highlight any issues found.\n"
            " - If the manifests are valid and follow best practices, state 'No issues found'.\n"
            "**No other output is allowed. Do not explain, do not reason, do not output markdown or comments.**\n"
        )

        manifest_files = [
            load_yaml_file(os.path.join(dp, f))
            for dp, dn, filenames in os.walk(manifests_path)
            for f in filenames
            if f.endswith(".yaml")
        ]

        prompt = "Please review the following Kubernetes cluster:\n"
        for manifest in manifest_files:
            prompt += f"---\n{manifest}\n"
        user_prompt = self.prompt_builder.generate_user_prompt(prompt)

        self.logger.info(f"User prompt: {user_prompt}")

        if os.getenv("DRY_RUN", "false").lower() == "true":
            self.logger.info(f"Dry mode enabled, skipping LLM inference.\n\n----\n")
            return {
                "Valid Cluster": False,
                "Feedback": "Dry run enabled, skipping LLM inference.",
            }

        ## Generate the response
        response = self.generator.chat(
            messages=user_prompt,  # type: ignore
            system_prompt=self.prompt_builder._generate_system_prompt(system_prompt),
        )

        processed_response = self.generator.pre_process_response(response.content)  # type: ignore
        self.logger.info(f"Processed response: {processed_response}")
        result = load_json_file(processed_response[0])  # type: ignore
        self.logger.info(f"Review result: {result}")
        return result

    def review_manifests_hardening(
        self, manifests_path: str, output_dir: str = "output-after-ir"
    ):
        """
        Analyze the manifest for compliance using Kubescape
        """

        self.logger.info("Starting the refinement process for manifests.")

        manifests_path = os.path.join(
            manifests_path, os.getenv("K8S_MANIFESTS_PATH", "k8s")
        )

        collected_metrics = {}

        for _, dirnames, _ in os.walk(manifests_path):
            for dirname in dirnames:
                self.logger.info(f"Processing directory: {dirname}")
                dir_path = os.path.join(manifests_path, dirname)

                if not os.path.exists(dir_path):
                    continue

                manifest_paths = [
                    os.path.join(dir_path, f)
                    for f in os.listdir(dir_path)
                    if f.endswith(".yaml")
                ]

                for manifest_path in manifest_paths:
                    self.logger.info(f"Validating manifest at {manifest_path}")
                    manifest_file = os.path.basename(manifest_path)
                    if (
                        not manifest_path.endswith(".yaml")
                        or manifest_file.startswith("skaffold")
                        or manifest_file.startswith("kustomization")
                    ):
                        continue

                    manifest_file.removesuffix(".yaml")

                    try:
                        # Validate the manifest
                        metrics = self.validator.validate_file(manifest_path)
                        iteration_metrics = collected_metrics
                        iteration_metrics.setdefault(manifest_file, metrics)

                    except Exception as e:
                        self.logger.error(
                            f"Failed to validate manifest {manifest_path}: {e}"
                        )

        self.validator.save_metrics_to_csv(
            collected_metrics,
            output_file=os.path.join(output_dir, "validation_results.csv"),
        )

    def generate_manifests_blindly(
        self, collected_files: Dict[str, Any], manifests_path: str
    ):
        """
        Generate manifests without feedback loop, useful for testing or initial generation.
        """
        self.logger.info("Generating manifests without feedback loop.")
        system_prompt = "You are a strict Kubernetes manifests generator.\n"

        is_compose_present = (compose := collected_files.get("app", None)) is not None
        if is_compose_present:
            system_prompt += "You only output valid raw Kubernetes YAML manifests starting off from a set of microservices defined in a docker-compose file.\n"
            system_prompt += f"-Its content is as follows:\n{compose["content"]}\n"
        else:
            system_prompt += "You only output valid raw Kubernetes YAML manifests starting off from a set of microservices described by a set of docker files, the services are the described as follow.\n"
            for microservice in collected_files.values():
                system_prompt += f"- {microservice['name']}\n"

        system_prompt += (
            "The set of microservices are interrelated and compose an application.\n"
            "Guidelines:\n"
            "- Use production-ready Kubernetes best practices.\n"
            "- If needed, add Service, ServiceAccount, ConfigMap, Secret, or PVC.\n"
            "- Use resource requests and limits for CPU and memory.\n"
            "- Use TODO placeholders for values that cannot be confidently inferred.\n"
            "- Image name must be the same as the microservice name.\n"
            "- Separate each manifest with '---' if multiple objects are required.\n"
            "- The result must be directly usable with `kubectl apply -f` or in CI/CD pipelines.\n"
            "- Maintain a uniform and syntactically cohesive style throughout manifests.\n"
            "**No other output is allowed. Do not explain, do not reason, do not output markdown or comments.**\n"
            "**Immediately output only valid Kubernetes YAML for the service.**\n"
        )

        if is_compose_present:
            microservices: Dict[str, Any] = compose["content"].get("services", {})
            for name, microservice in microservices.items():
                prompt = f"""Now generate Kubernetes manifests in YAML format for the microservice '{name}'.\n
                Docker-Compose details:\n {microservice}\n"""
                if docker := collected_files.get(name, None):
                    prompt += f"Docker file content:\n {docker['content']}\n"

                user_prompt = self.prompt_builder.generate_user_prompt(prompt)

                self.logger.info(f"User prompt: {user_prompt}")

                if os.getenv("DRY_RUN", "false").lower() == "true":
                    self.logger.info(
                        f"Dry mode enabled, skipping LLM inference.\n\n----\n"
                    )
                    continue
                else:
                    self.query_llm(user_prompt, system_prompt, manifests_path, name)
        else:
            for microservice in collected_files.values():
                if microservice["name"] == "app":
                    continue

                prompt = f"""Now generate Kubernetes manifests in YAML format for the microservice '{microservice['name']}'.\n
                Dockerfile details:\n {microservice['content']}\n"""

                user_prompt = self.prompt_builder.generate_user_prompt(prompt)

                self.logger.info(f"User prompt: {user_prompt}")

                if os.getenv("DRY_RUN", "false").lower() == "true":
                    self.logger.info(
                        f"Dry mode enabled, skipping LLM inference.\n\n----\n"
                    )
                    continue
                else:
                    self.query_llm(
                        user_prompt, system_prompt, manifests_path, microservice["name"]
                    )

    def query_llm(
        self,
        user_prompt: List[Dict[str, Any]],
        system_prompt: str,
        manifests_path: str,
        microservice_name: str = "",
        alternative_path: Optional[str] = None,
    ):
        ## Generate the response
        response = self.generator.chat(
            messages=user_prompt,  # type: ignore
            system_prompt=self.prompt_builder._generate_system_prompt(system_prompt),
        )

        processed_response = self.generator.process_response(response.content)  # type: ignore

        self.logger.info(
            f"Received response for {microservice_name}: {processed_response}"
        )

        for manifest in processed_response:
            if microservice_name == "":
                microservice_name = (
                    manifest["manifest"].get("metadata", {}).get("name", "default")
                )
            self._save_manifest_to_file(manifest, microservice_name, manifests_path)

            if alternative_path and alternative_path != "":
                self._save_manifest_to_file(
                    manifest, microservice_name, alternative_path
                )

    def prepare_for_execution(
        self,
        enriched_services: List[Dict[str, Any]],
        manifests_path: str,
        include_overrides: bool = False,
    ):

        self.logger.info("Preparing for execution...")

        # Introduce extra manifests included in the overrides.yaml file
        if (
            include_overrides
            and self.overrider
            and (config := self.overrider.override_config)
        ):
            if config.get("customManifests", None):
                for manifest_name, manifest_content in config[
                    "customManifests"
                ].items():
                    # Log the manifest name and content
                    self.logger.debug(f"Processing custom manifest: {manifest_name}")

                    # Save the custom manifest
                    manifest_path = os.path.join(
                        manifests_path,
                        os.getenv("K8S_MANIFESTS_PATH", "k8s"),
                        f"{manifest_name}.yaml",
                    )

                    self.manifest_builder._save_yaml(manifest_content, manifest_path)
                    self.logger.info(f"Custom manifest saved: {manifest_path}")

        self.manifest_builder.generate_skaffold_config(
            enriched_services,  # For the Dockerfile paths of the repository scanned
            manifests_path,
        )

    def _save_manifest_to_file(
        self, manifest: Dict[str, str], microservice_name: str, path: str
    ):
        target_dir = os.path.join(
            path,
            os.getenv("K8S_MANIFESTS_PATH", "k8s"),
            to_snake(manifest["name"]),
        )

        os.makedirs(target_dir, exist_ok=True)

        # Save the response to a file
        manifest_path = os.path.join(target_dir, f"{microservice_name}.yaml")

        with open(manifest_path, "w") as f:
            f.write(manifest["manifest"])

        self.logger.info(f"Saved manifest to {manifest_path}")
