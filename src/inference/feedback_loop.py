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
                if key != "manifests":
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
                system_prompt=self.prompt_builder._generate_system_prompt(
                    system_prompt
                ),
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
        collected_metrics = {}

        for iteration in range(max_iterations):
            self.logger.info(f"Starting iteration {iteration + 1}/{max_iterations}")

            collected_metrics.setdefault(iteration, {})

            previous_iteration_path = os.path.join(
                manifests_path, f"v{iteration}", os.getenv("K8S_MANIFESTS_PATH", "k8s")
            )

            # Check if the iteration directory exists
            if not os.path.exists(previous_iteration_path):
                self.logger.warning(
                    f"Iteration path {previous_iteration_path} does not exist. Skipping iteration {iteration + 1}"
                )
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
                        manifest_file = os.path.basename(manifest_path)
                        if (
                            not manifest_path.endswith(".yaml")
                            or manifest_file.startswith("skaffold")
                            or manifest_file.startswith(
                                "kustomization"
                            )
                        ):
                            continue

                        manifest_file.removesuffix(".yaml")
                        issues = []
                        try:
                            # Validate the manifest
                            metrics = self.validator.validate_file(manifest_path)
                            iteration_metrics = collected_metrics.get(iteration, {})
                            iteration_metrics.setdefault(manifest_file, metrics)
                            collected_metrics.update({iteration: iteration_metrics})
                            issues_found = metrics.get("failed_controls_details", [])
                            iteration_has_issues = True
                        
                        except Exception as e:
                            self.logger.error(
                                f"Failed to validate manifest {manifest_path}: {traceback.format_exc()}"
                            )
                        
                            issues_found = []
                        
                        # Compare the issues with the previous iteration
                        previous_issues = collected_metrics[iteration-1][manifest_file]["failed_controls_details"] if iteration > 0 else []

                        for prev_issue in previous_issues:
                            # Only check for issues that have not yet been reported
                            if prev_issue not in issues_found:
                                issues.append(prev_issue)

                            self.logger.info(
                                f"New issues found in manifest {manifest_path}: {issues}"
                            )
                        
                        patch = self.patch_manifest(manifest_path, issues)


                        if patch and patch.strip():
                            self.logger.info(f"Patched maifest {manifest_path}: {patch}")

                               
                            save_path = os.path.join(
                                manifests_path,
                                f"v{iteration + 1}" if iteration < max_iterations - 1 else os.getenv("REVIEWED_MANIFESTS", "final_manifests"),
                                os.getenv("K8S_MANIFESTS_PATH", "k8s"),
                                dirname,
                            )
                            os.makedirs(save_path, exist_ok=True)

                            if patch:
                                self.logger.info(
                                    f"Applying patch: {patch}\n to {manifest_path}"
                                )

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

                            output_path = os.path.join(
                                output_dir, os.path.basename(manifest_path)
                            )

                            
                            self.logger.info(
                                f"No issues found for manifest at {manifest_path}. Saving to final directory."
                            )

                            with open(output_path, "w") as f:
                                f.write(open(manifest_path).read())
            
            self.validator.save_metrics_to_csv(
                collected_metrics[iteration],
                iteration,
                output_file=os.path.join(manifests_path, "validation_results.csv"),
            )

            # If no issues found in this iteration, we can break early
            if not iteration_has_issues:
                self.logger.info(
                    f"No issues found in iteration {iteration + 1}. Refinement process converged."
                )
                break

        # Introduce extra manifests included in the overrides.yaml file
        if config := self.overrider.override_config:
            if config.get("customManifests", None):
                for manifest_name, manifest_content in config[
                    "customManifests"
                ].items():
                    # Log the manifest name and content
                    self.logger.debug(f"Processing custom manifest: {manifest_name}")

                    # Save the custom manifest
                    manifest_path = os.path.join(
                        converged_manifests_path,
                        os.getenv("K8S_MANIFESTS_PATH", "k8s"),
                        f"{manifest_name}.yaml",
                    )

                    self.manifest_builder._save_yaml(
                        manifest_content, manifest_path
                    )
                    self.logger.info(f"Custom manifest saved: {manifest_path}")

        self.manifest_builder.generate_skaffold_config(
            enriched_services,  # For the Dockerfile paths of the repository scanned
            converged_manifests_path,
        )

    def patch_manifest(
        self,
        manifest_path: str,
        issues: List[dict],
    ) -> str:
        with open(manifest_path, "r") as f:
            manifest_content = f.read()

        # Better issue formatting
        if issues:
            formatted_issues = []
            for issue in issues:
                issue_text = f"- Control: {issue.get('name', 'Unknown')}"

                # Better remediation formatting
                remediation = issue.get('suggested_remediation', [])
                for solution in remediation:
                    issue_text += f"\n- Fix: {solution.get('path', solution)} - Apply: {solution.get('value', 'Unknown')}"
                formatted_issues.append(issue_text)
            
            issues_context = "\n".join(formatted_issues)
        else:
            issues_context = "No specific issues identified."

        system_prompt = self.prompt_builder._generate_system_prompt(
        f"""
        You are a senior Kubernetes security engineer reviewing manifests for production deployment.
        
        Your expertise should guide the decision-making process. Use the security analysis as input, but apply your professional judgment.
 
        
        Your task:
        1. Review the Kubernetes manifest for security and best practices
        2. Apply fixes that genuinely improve manifest quality without breaking functionality
        3. Feel free to SKIP fixes that are:
           - Would break legitimate functionality
           - Are overly restrictive for the use case
           - Create operational complexity without significant security benefit
        4. Output the improved manifest in valid YAML format
        5. If no meaningful improvements are needed, return an empty string
        
        Decision Guidelines:
        - Some security controls may not apply to certain resource types (e.g., Service resources)
        - Network policies, resource limits, and security contexts are often valuable
        - Overly restrictive permissions can hinder legitimate operations
        - Production workloads need reasonable security without operational burden
        
        Output Rules:
        - Only output valid Kubernetes YAML or empty string
        - Do not add explanations or comments
        - Preserve original functionality and structure
        - Apply professional judgment, not blind compliance
        """
    )

        prompt = f"""Review this Kubernetes manifest and apply security improvements using your professional judgment.

        Provided analysis (use as guidance, not strict requirements):
        {issues_context}

        MANIFEST TO REVIEW:
        ```yaml
        {manifest_content}
        ```

        Instructions:
        - Apply security improvements that make genuine sense for this resource type
        - Skip suggestions that don't apply or would cause operational issues
        - Return the improved manifest or empty string if no meaningful improvements needed
        - Use your expertise to balance security with functionality"""


        user_prompt = self.prompt_builder.generate_user_prompt(prompt)

        messages = self.evaluator.chat(
            messages=user_prompt,
            system_prompt=system_prompt,
        )

        self.logger.debug(f"Received review for {manifest_path}: {messages.model_dump_json()}")

        # Process the messages from the LLM
        messages = self.evaluator.pre_process_response(messages.content)  # type: ignore

        return " ".join(messages).strip()  # type: ignore
