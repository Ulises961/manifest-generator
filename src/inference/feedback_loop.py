import logging
import os
from typing import Any, Dict, List, Optional

from caseutil import to_snake
from llm_client import LLMClient
from inference.prompt_builder import PromptBuilder
from manifests_generation.manifest_builder import ManifestBuilder
from validation.kubescape_validator import KubescapeValidator


class ManifestFeedbackLoop:
    """
    Class to handle the feedback loop for manifest generation.
    It processes the output from the LLM and updates the microservice manifests accordingly.
    """

    def __init__(
        self,
        generator: LLMClient,
        evaluator: LLMClient,
        validator: KubescapeValidator,
        manifest_builder: ManifestBuilder
    ):
        self.logger = logging.getLogger(__name__)
        self.generator = generator
        self.evaluator = evaluator
        self.validator = validator
        self.prompt_builder = PromptBuilder()
        self.manifests_path = os.path.join(os.getenv("TARGET_DIR", "target"), os.getenv("MANIFESTS_PATH", "manifests"), "LLM_MANIFESTS_PATH", "llm")
        self.manifest_builder = manifest_builder
        
    def review_manifest(
        self,
        manifest_path: str,
        issues: List[dict],
        include_system_prompt: bool = False,
    ) -> str:
        with open(manifest_path, "r") as f:
            manifest_content = f.read()

        feedback = "\n".join(f"- {i['name']}: {i['description']}" for i in issues)
        self.logger.info(f"Refining manifest at {manifest_path} with issues: {issues}")

        system_prompt = self.prompt_builder._generate_system_prompt(
            """
            You are a Kubernetes expert tasked with reviewing manifests that describe a microservices cluster ready for deployment. 
            Your responsibilities are as follows:
            1. Analyze the provided Kubernetes manifest for issues related to security, performance, or best practices.
            2. If issues are found, suggest actionable and specific corrections in the form of a prompt for the LLM that generated the manifest, so it can refine the manifest.
            3. If no issues are found, return an empty string.

            Ensure your feedback is concise and directly addresses the identified issues.
            """
        )

        user_prompt = self.prompt_builder.generate_user_prompt(
            f"""
            Analyze the following Kubernetes manifest and provide feedback on how to improve it.
            To support your review, you have the following issues identified by Kubescape:
            {feedback}

            --- Manifest Start ---
            {manifest_content}
            --- Manifest End ---
            """
        )

        messages = self.evaluator.chat(
            messages=user_prompt,
            system_prompt=system_prompt,
        )

        reviews = []

        for block in messages:
            # Accept either a string or an object with .text
            if isinstance(block, str):
                content = block
            else:
                content = getattr(block, "text", "")

            if not content or not isinstance(content, str) or not content.strip():
                self.logger.warning(
                    "Received empty or invalid content block, skipping."
                )
                continue

            reviews.append(content.strip())

        return reviews.join("\n").strip()  # type: ignore

    def patch_manifest(
        self,
        review: str,
        manifest_path: str,
        iteration: int,
        first_prompt: bool = False,
    ):
        """
        Patch the manifest based on the review provided by the LLM.
        The review should contain actionable instructions for the LLM that generated the manifest.
        """

        self.logger.info(f"Patching manifest with review: {review}")
        system_prompt = self.prompt_builder._generate_system_prompt(
            """
            The manifests previously generated have been reviewed, and feedback has been provided. 
            Your task is to refine the manifest based on the feedback to address all identified issues. 
            The output should be a valid, production-ready Kubernetes manifest that adheres to best practices 
            and requires no further refinements.

            Ensure that:
            1. All feedback points are addressed explicitly.
            2. No unnecessary changes are introduced beyond the scope of the feedback.
            3. The refined manifest is syntactically and semantically valid for Kubernetes deployment.
            """
        )

        user_prompt = self.prompt_builder.generate_user_prompt(
            f"""
            Based on the following review, refine the Kubernetes manifest:
            {review}

            --- Manifest Start ---
            {open(manifest_path).read()}
            --- Manifest End ---
            """
        )

        response = self.generator.chat(
            messages=user_prompt,
            system_prompt=system_prompt if first_prompt else None,
        )

        if not response or not isinstance(response, list) or not response[0].strip():
            self.logger.warning(
                f"No valid response received for manifest at {manifest_path}. Skipping patching."
            )
            return

        # Save the refined manifest
        iteration_dir = os.path.join(os.getenv("ITERATION_DIR", "iterations"), f"v_{iteration}")
        os.makedirs(iteration_dir, exist_ok=True)
        
        with open(manifest_path, "w") as f:
            f.write(response[0].strip())

        self.logger.info(f"Manifest at {manifest_path} patched successfully.")

    def refine_manifests(self, previous_iteration_path: str):
        """
        Iterate through the feedback loop until no issues are found.
        """
        max_iterations = int(os.getenv("MAX_FEEDBACK_ITERATIONS", "3"))
        first_prompt = True

        for iteration in range(max_iterations):
            for _, _, manifest_paths in os.walk(previous_iteration_path):
                for manifest_path in manifest_paths:
                    self.logger.info(f"Validating manifest at {manifest_path}")
                    if (
                        not manifest_path.endswith(".yaml")
                        or manifest_path.startswith("skaffold")
                        or manifest_path.startswith("kustomization")
                    ):
                        continue

                    # Validate the manifest
                    metrics = self.validator.validate_file(manifest_path)
                    issues = metrics.get("failed_controls", [])
                    review = self.review_manifest(manifest_path, issues, first_prompt)

                    if review and review.strip():
                        self.logger.info(f"Review for {manifest_path}: {review}")

                        # If issues are found, generate a new manifest
                        self.patch_manifest(
                            review, manifest_path, iteration, first_prompt
                        )

                    else:
                        self.logger.info(
                            f"No issues found for manifest at {manifest_path}. Saving converged manifest."
                        )

                        # Save the converged manifest to an output directory
                        output_dir = os.getenv("REVIEWED_MANIFESTS", "final_manifests")
                        os.makedirs(output_dir, exist_ok=True)
                        output_path = os.path.join(
                            output_dir, os.path.basename(manifest_path)
                        )

                        with open(output_path, "w") as f:
                            f.write(open(manifest_path).read())
                        
                        self.logger.info(f"Converged manifest saved to {output_path}")

                    first_prompt = False

          # Introduce extra manifests included in the overrides.yaml file
        if config := overrider.override_config:
            if config.get("customManifests", None):
                for manifest_name, manifest_content in config["customManifests"].items():
                    # Log the manifest name and content
                    logger.debug(f"Processing custom manifest: {manifest_name}")

                    # Save the custom manifest
                    manifest_path = os.path.join(llm_manifests_path, os.getenv("K8S_MANIFESTS_PATH", "k8s"), f"{manifest_name}.yaml")
                    manifest_builder._save_yaml(manifest_content, manifest_path)
                    logger.info(f"Custom manifest saved: {manifest_path}")

        manifest_builder.generate_skaffold_config(
            enriched_services, # For the Dockerfile paths of the repository scanned
            llm_manifests_path
        )

    def generate_manifests(self, microservices: List[Dict[str, Any]], manifests_path: Optional[str] = None):
        """
        Initialize the feedback loop with the microservices manifests.
        """
        self.logger.info("Initializing feedback loop with microservices manifests.")
        
        for index, microservice in enumerate(microservices):
            logging.info(f"Generating manifests for child... {microservice['name']}")
        
            prompt = f"""Now generate Kubernetes manifests in YAML format for the microservice '{microservice['name']}'.\n
                Details:\n"""
            
            for key, value in microservice.items():
                if key != "attached_files" and key != "manifests":
                    prompt += f"  {key}: {value}\n"

            user_prompt = self.prompt_builder.generate_user_prompt(prompt)

            if os.getenv("DRY_RUN", "false").lower() == "true":
                logging.info(f"Dry mode enabled, skipping LLM inference.\n\n----\n")
                continue
            
            system_prompt = (
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
                "- Maintain a uniform and syntactically cohesive style throughout manifests.\n"
                "**No other output is allowed. Do not explain, do not reason, do not output markdown or comments.**\n"
                "**Immediately output only valid Kubernetes YAML for the service.**\n"
            )

            ## Generate the response
            response = self.generator.chat(
                system=prompt_builder._generate_system_prompt(system_prompt) if index == 0 else None,  # type: ignore
                messages=user_prompt # type: ignore
            )
    
            logging.info(f"Content from LLM: {response.content}")

            processed_response = inference_processor.process_response(response.content) # type: ignore
            
            self.logger.info(f"Received response for {microservice['name']}: {processed_response}")

            # Save the manifests to the target directory
            llm_manifests_path = os.path.join( os.getenv("TARGET_PATH", "target"),
                    os.getenv("MANIFESTS_PATH", "manifests"),
                    os.getenv("LLM_MANIFESTS_PATH", "llm"))

            os.makedirs(llm_manifests_path, exist_ok=True)


            for manifest in processed_response:
                logging.info(f"Generated manifest: {microservice['name']}")

                target_dir = os.path.join(
                    llm_manifests_path,
                    os.getenv("K8S_MANIFESTS_PATH", "k8s"),
                    to_snake(manifest['name'])
                )

                os.makedirs(target_dir, exist_ok=True)

                # Save the response to a file
                manifest_path = os.path.join(target_dir, f"{microservice['name']}.yaml")
                
                with open(manifest_path, "w") as f:
                    f.write(manifest["manifest"])

                logging.info(f"Saved manifest to {manifest_path}")


        