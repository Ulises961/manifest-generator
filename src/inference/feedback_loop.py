import logging
import os
import sys
from typing import Any, Dict, List, Optional

from caseutil import to_snake
from inference.prompt_builder import PromptBuilder
from inference.llm_client import LLMClient
from manifests_generation.manifest_builder import ManifestBuilder
from overrides.overrider import Overrider
from validation.kubescape_validator import KubescapeValidator
import traceback

class ManifestFeedbackLoop:
    """
    Class to handle the feedback loop for manifest generation.
    It processes the output from the LLM and updates the microservice manifests accordingly.
    """

    V0 = "v0"

    def __init__(
        self,
        generator: LLMClient,
        evaluator: LLMClient,
        validator: KubescapeValidator,
        manifest_builder: ManifestBuilder,
        overrider: Overrider,
    ):
        self.logger = logging.getLogger(__name__)
        self.generator = generator
        self.evaluator = evaluator
        self.validator = validator
        self.prompt_builder = PromptBuilder()
        self.manifests_path = os.path.join(
            os.getenv("TARGET_DIR", "output"),
            os.getenv("MANIFESTS_PATH", "manifests"),
            os.getenv("LLM_MANIFESTS_PATH", "llm"),
        )
        self.manifest_builder = manifest_builder
        self.overrider = overrider
        os.makedirs(self.manifests_path, exist_ok=True)

    def generate_manifests(
        self, microservices: List[Dict[str, Any]], manifests_path: Optional[str] = None
    ):
        """
        Initialize the feedback loop with the microservices manifests.
        """
        self.logger.info("Initializing feedback loop with microservices manifests.")

        manifests_path = manifests_path or self.manifests_path

        for index, microservice in enumerate(microservices):
            self.logger.info(
                f"Generating manifests for child... {microservice['name']}"
            )

            prompt = f"""Now generate Kubernetes manifests in YAML format for the microservice '{microservice['name']}'.\n
                Details:\n"""

            for key, value in microservice.items():
                if key != "attached_files" and key != "manifests":
                    prompt += f"  {key}: {value}\n"

            user_prompt = self.prompt_builder.generate_user_prompt(prompt)

            if os.getenv("DRY_RUN", "false").lower() == "true":
                self.logger.info(f"Dry mode enabled, skipping LLM inference.\n\n----\n")
                continue

            system_prompt = (
                "You are a strict Kubernetes manifests generator.\n"
                "You only output valid raw Kubernetes YAML manifests starting off from a set of microservices described next.\n"
                "The set of microservices are interrelated and compose an application.\n"
                "Guidelines:\n"
                "- Use production-ready Kubernetes best practices.\n"
                "- If needed, add Service, ConfigMap, Secret, or PVC.\n"
                "- Use kubernetes compliant labels like `app.kubernetes.io/name`, `app.kubernetes.io/tier`, `app.kubernetes.io/role`, and `environment`.\n"
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
                messages=user_prompt,  # type: ignore
                system_prompt=self.prompt_builder._generate_system_prompt(system_prompt)
            )

            self.logger.info(f"Content from LLM: {response.content}")

            processed_response = self.generator.process_response(response.content)  # type: ignore

            self.logger.info(
                f"Received response for {microservice['name']}: {processed_response}"
            )

            for manifest in processed_response:
                self.logger.info(f"Generated manifest: {microservice['name']}")

                target_dir = os.path.join(
                    manifests_path,
                    self.V0,
                    os.getenv("K8S_MANIFESTS_PATH", "k8s"),
                    to_snake(manifest["name"]),
                )

                os.makedirs(target_dir, exist_ok=True)

                # Save the response to a file
                manifest_path = os.path.join(target_dir, f"{microservice['name']}.yaml")

                with open(manifest_path, "w") as f:
                    f.write(manifest["manifest"])

                self.logger.info(f"Saved manifest to {manifest_path}")

    def refine_manifests(
        self,
        enriched_services: List[Dict[str, Any]],
        manifests_path: Optional[str] = None,
    ):
        """
        Iterate through the feedback loop until no issues are found.
        """

        self.logger.info("Starting the refinement process for manifests.")

        manifests_path = manifests_path or self.manifests_path
        converged_manifests_path = os.path.join(
            manifests_path, os.getenv("REVIEWED_MANIFESTS", "final_manifests")
        )

        max_iterations = int(os.getenv("REFINEMENT_ITERATIONS", "3"))
        collected_metrics = []
        
        for iteration in range(max_iterations):
            self.logger.info(f"Starting iteration {iteration + 1}/{max_iterations}")
            
            previous_iteration_path = os.path.join(
                manifests_path, f"v{iteration}", os.getenv("K8S_MANIFESTS_PATH", "k8s")
            )
            
            # Check if the iteration directory exists
            if not os.path.exists(previous_iteration_path):
                self.logger.warning(f"Iteration path {previous_iteration_path} does not exist. Skipping iteration {iteration + 1}")
                continue
                
            iteration_has_issues = False
            
            for _, dirnames, _ in os.walk(previous_iteration_path):
                for dirname in dirnames:
                    self.logger.info(f"Processing directory: {dirname}")
                    dir_path = os.path.join(previous_iteration_path, dirname)
                    
                    if not os.path.exists(dir_path):
                        continue
                        
                    manifest_paths = [
                        os.path.join(dir_path, f)
                        for f in os.listdir(dir_path)
                        if f.endswith(".yaml")
                    ]

                    for manifest_path in manifest_paths:
                        self.logger.info(f"Validating manifest at {manifest_path}")

                        if (
                            not manifest_path.endswith(".yaml")
                            or os.path.basename(manifest_path).startswith("skaffold")
                            or os.path.basename(manifest_path).startswith("kustomization")
                        ):
                            continue

                        try:
                            # Validate the manifest
                            metrics = self.validator.validate_file(manifest_path)
                            collected_metrics.append(metrics)
                            issues = metrics.get("failed_controls", [])

                            if len(issues) > 0:
                                iteration_has_issues = True
                                review = self.review_manifest(
                                    manifest_path, issues
                                )
                            else:
                                review = ""
                        except Exception as e:
                            self.logger.error(f"Failed to validate manifest {manifest_path}: {traceback.format_exc()}")
                            # Copy manifest forward without changes if validation fails
                            review = ""

                        # If issues are found generate a new manifest
                        if review and review.strip():
                            self.logger.info(f"Review for {manifest_path}: {review}")

                            try:
                                patch = self.get_patch(review, manifest_path)[0] # type: ignore
                            except Exception as e:
                                self.logger.error(f"Failed to get patch for {manifest_path}: {traceback.format_exc()}")
                                patch = None

                            save_path = os.path.join(
                                manifests_path,
                                f"v{iteration + 1}",
                                os.getenv("K8S_MANIFESTS_PATH", "k8s"),
                                dirname,
                            )
                            os.makedirs(save_path, exist_ok=True)

                            if patch:
                                self.logger.info(f"Applying patch: {patch}\n to {manifest_path}")

                                with open(
                                    os.path.join(
                                        save_path, os.path.basename(manifest_path)
                                    ),
                                    "w",
                                ) as f:
                                    f.write(patch)

                                self.logger.info(
                                    f"Refined manifest saved to {save_path}"
                                )
                            else:
                                self.logger.warning(
                                    f"No patch generated for manifest at {manifest_path}. Copying original manifest."
                                )

                                # Copy the original manifest forward
                                with open(
                                    os.path.join(
                                        save_path, os.path.basename(manifest_path)
                                    ),
                                    "w",
                                ) as f:
                                    f.write(open(manifest_path).read())
                        else:
                            # Save to final directory if no issues or max iterations reached
                            output_dir = os.path.join(
                                converged_manifests_path,
                                os.getenv("K8S_MANIFESTS_PATH", "k8s"),
                                dirname,
                            )
                            os.makedirs(output_dir, exist_ok=True)
                            
                            output_path = os.path.join(output_dir, os.path.basename(manifest_path))

                            if not review or not review.strip():
                                self.logger.info(
                                    f"No issues found for manifest at {manifest_path}. Saving to final directory."
                                )

                            with open(output_path, "w") as f:
                                f.write(open(manifest_path).read())
                        
            # If no issues found in this iteration, we can break early
            if not iteration_has_issues:
                self.logger.info(f"No issues found in iteration {iteration + 1}. Refinement process converged.")
                break
                
        self.validator.save_metrics_to_csv(
            collected_metrics,
            output_file=os.path.join(manifests_path, "validation_results.csv"),
        )

        # Introduce extra manifests included in the overrides.yaml file
        if config := self.overrider.override_config:
            if config.get("customManifests", None):
                for manifest_name, manifest_content in config[
                    "customManifests"
                ].items():
                    # Log the manifest name and content
                    self.logger.debug(f"Processing custom manifest: {manifest_name}")

                    # Save the custom manifest
                    self.manifest_path = os.path.join(
                        converged_manifests_path,
                        os.getenv("K8S_MANIFESTS_PATH", "k8s"),
                        f"{manifest_name}.yaml",
                    )
                    
                    self.manifest_builder._save_yaml(
                        manifest_content, self.manifest_path
                    )
                    self.logger.info(f"Custom manifest saved: {self.manifest_path}")

        self.manifest_builder.generate_skaffold_config(
            enriched_services,  # For the Dockerfile paths of the repository scanned
            converged_manifests_path,
        )

    def review_manifest(
        self,
        manifest_path: str,
        issues: List[dict],
    ) -> str:
        with open(manifest_path, "r") as f:
            manifest_content = f.read()

        feedback = "\n".join(f"- {i['name']}: {i['suggested_remediation']}" for i in issues)
        self.logger.info(f"Refining manifest at {manifest_path} with issues: {issues}")

        system_prompt = self.prompt_builder._generate_system_prompt(
            """
            You are a Kubernetes security and best practices expert reviewing manifests for production deployment.
            
            Your task:
            1. Analyze the provided Kubernetes manifest against the security issues identified by Kubescape
            2. Generate specific, actionable improvement instructions that address each identified issue
            3. Focus on security, resource management, and Kubernetes best practices
            4. If no critical issues need addressing, return an empty string
            
            Output format:
            - Provide clear, specific instructions for fixing each issue
            - Use concrete values and configurations, not generic placeholders
            - Prioritize security and production-readiness
            - Be concise but comprehensive
            """
        )

        user_prompt = self.prompt_builder.generate_user_prompt(
            f"""
            Review this Kubernetes manifest and provide specific improvement instructions.
            
            SECURITY ISSUES IDENTIFIED BY KUBESCAPE:
            {feedback}
            
            MANIFEST TO REVIEW:
            --- Manifest Start ---
            {manifest_content}
            --- Manifest End ---
            
            Provide specific instructions to fix each identified security issue. Focus on:
            - Security contexts and privilege settings
            - Resource limits and requests
            - Network policies and service configurations
            - Label compliance and best practices
            """
        )

        messages = self.evaluator.chat(
            messages=user_prompt,
            system_prompt=system_prompt,
        )

        self.logger.info(f"Received review for {manifest_path}: {messages}")

        # Process the messages from the LLM
        messages = self.evaluator.pre_process_response(messages)  # type: ignore


        return " ".join(messages).strip()  # type: ignore

    def get_patch(
        self,
        review: str,
        manifest_path: str,
    ) -> Optional[str]:
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
            "**No other output is allowed. Do not explain, do not reas  on, do not output markdown or comments.**\n"
            "**Immediately output only valid Kubernetes YAML for the resource.**\n"
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
            system_prompt=system_prompt
        )
        
        self.logger.debug(f"Received patch for {manifest_path}: {response.content}")
        
        return self.generator.pre_process_response(response)  # type: ignore
