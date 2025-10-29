import logging
import os
import json
from typing import Any, Dict, List, Optional

from caseutil import to_snake
from inference.prompt_builder import PromptBuilder
from inference.llm_client import LLMClient
from manifests_generation.manifest_builder import ManifestBuilder
from overrides import overrider
from overrides.overrider import Overrider
from utils.file_utils import load_yaml_file
from validation.kubescape_validator import KubescapeValidator


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
                if key != "manifests" and key != "metadata" and key != "overrides":
                    prompt += f"  {key}: {value}\n"

            if microservice.get("overrides", None):
                prompt += f"Consider the following overrides:\n{microservice['overrides']}\n and use them in the generation.\n"

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

    def review_with_llm(self, manifests_path: str, collected_files: Dict[str, Any]) -> Dict[str, Any]:
        """
        Review the generated manifests to determine if they can be deployed.
        Focuses on deployment viability, not security/optimization.
        """
        self.logger.info("Checking cluster deployment viability with LLM.")

        system_prompt = (
            "You are a semantic validator.\n"
            "Your ONLY task is to determine if the set of manifests reproduces the desired application behavior. The application has been tested to deploy successfully, your task is to determine to the best of your capability whether the application aligns with the original intent of interactions inferrable from the gathered application metadata.\n\n"
            
            "Output Format (ONLY valid JSON):\n"
            "{\n"
            '  "aligned_to_intent": boolean,\n'
            '  "confidence": "high" | "medium" | "low",\n'
            '  "reasoning": string,  # Brief explanation of your assessment\n'
            "}\n\n"
            
            "Rules:\n"
            "- aligned_to_intent=false ONLY if the application behavior does not match the original intent\n"
            "**Output ONLY the JSON object. No markdown, no explanations.**\n"
        )

        # Load all manifests
        manifest_files = []
        for dp, dn, filenames in os.walk(manifests_path):
            for f in filenames:
                if f.endswith(".yaml") and not f.startswith(("skaffold", "kustomization")):
                    manifest_content = load_yaml_file(os.path.join(dp, f))
                    manifest_files.append(manifest_content)

        if not manifest_files:
            self.logger.warning("No manifest files found to review")
            return {
                "aligned_to_intent": False,
                "confidence": "high",
                "reasoning": "No manifest files found to review"
            }

        # Build prompt with all manifests
        prompt = "Evaluate deployment viability for this Kubernetes cluster:\n\n"
        for idx, manifest in enumerate(manifest_files, 1):
            prompt += f"--- Manifest {idx} ---\n{manifest}\n\n"
        
        prompt += ("Consider the following contextual information about the application:\n")
        is_compose_present = (compose := collected_files.get("app", None)) is not None
        if is_compose_present:
            prompt += f"- The application is defined by a docker-compose file with the following content:\n{compose['content']}\n"
        else:
            prompt += "- The application is defined by a set of Dockerfiles for its microservices.\n"
            prompt += "The microservices are:\n"
            for microservice in collected_files.values():
                if microservice["type"] == "contextual" or microservice["name"] == "app":
                    continue
                prompt += f"  - {microservice['name']}\n"
                if docker := collected_files.get(microservice["name"], None):
                    prompt += f"    - Dockerfile content:\n{docker['content']}\n"
        prompt += "\n You can consider also the following contextual files:\n"

        for file in collected_files.values():
            if file["type"] == "contextual":
                prompt += f"- {file['name']}:\n{file['content']}\n"

        user_prompt = self.prompt_builder.generate_user_prompt(prompt)

        if os.getenv("DRY_RUN", "false").lower() == "true":
            self.logger.info("Dry mode enabled, skipping LLM inference.")
            return {
                "aligned_to_intent": True,
                "confidence": "low",
                "reasoning": "Dry run mode, no actual review performed."
            }

        # Query LLM
        try:
            response = self.generator.chat(
                messages=user_prompt,
                system_prompt=self.prompt_builder._generate_system_prompt(system_prompt),
            )

            processed_response = self.generator.pre_process_response(response.content)
            self.logger.debug(f"Raw LLM response: {processed_response}")
            
            result = json.loads(processed_response[0])
            
            # Validate response structure
            self._validate_viability_response(result)
            
            # Log summary
            aligned_to_intent = result.get("aligned_to_intent", False)
            resoning = result.get("reasoning", "")
            self.logger.info(
                f"Deployment viability check complete: "
                f"aligned_to_intent={aligned_to_intent}, "
                f"confidence={result.get('confidence', 'unknown')}, "
                f" reasoning={resoning[:100]}..."  # Log first 100 chars of reasoning
                
            )
                        
            return result
            
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse LLM response as JSON: {e}")
            self.logger.error(f"Raw response: {processed_response if 'processed_response' in locals() else 'N/A'}") # type: ignore
            raise ValueError(f"LLM did not return valid JSON: {e}")
        except Exception as e:
            self.logger.error(f"Error during viability check: {e}")
            raise

    def _validate_viability_response(self, result: Dict[str, Any]):
        """Validate that the LLM response matches expected schema."""
        required_keys = ["aligned_to_intent", "confidence", "reasoning"]
        missing = [k for k in required_keys if k not in result]
        
        if missing:
            raise ValueError(f"LLM response missing required keys: {missing}")
        
        if not isinstance(result["aligned_to_intent"], bool):
            raise ValueError("'aligned_to_intent' must be a boolean")
        
        if result["confidence"] not in ["high", "medium", "low"]:
            raise ValueError("'confidence' must be 'high', 'medium', or 'low'")

        if not isinstance(result["reasoning"], str):
            raise ValueError("'reasoning' must be a string")


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
                if microservice["type"] == "contextual" or microservice["name"] == "app":
                    continue
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
                if microservice.get("type", "") == "contextual":
                    continue

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
                if microservice["name"] == "app" or microservice["type"] == "contextual":
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
        manifests_path: str):

        self.logger.info("Preparing for execution...")      
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
