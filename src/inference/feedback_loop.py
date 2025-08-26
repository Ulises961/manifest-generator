import logging
import os
from re import I
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
            os.getenv("OUTPUT_DIR", "output"),
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
                "- If needed, add Service, ServiceAccount, ConfigMap, Secret, or PVC.\n"
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

    def review_manifests(
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
            manifests_path,os.getenv("K8S_MANIFESTS_PATH", "k8s")
        )

        collected_metrics = {}

        for _, dirnames, _ in os.walk(converged_manifests_path):
            for dirname in dirnames:
                self.logger.info(f"Processing directory: {dirname}")
                dir_path = os.path.join(converged_manifests_path, dirname)

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

                    try:
                        # Validate the manifest
                        metrics = self.validator.validate_file(manifest_path)
                        iteration_metrics = collected_metrics
                        iteration_metrics.setdefault(manifest_file, metrics)
                        iteration_has_issues = True
                    
                    except Exception as e:
                        self.logger.error(
                            f"Failed to validate manifest {manifest_path}: {traceback.format_exc()}"
                        )
                    
        
        self.validator.save_metrics_to_csv(
            collected_metrics,
            output_file=os.path.join(manifests_path, "validation_results.csv"),
        )

     

    def prepare_for_execution(self, enriched_services: List[Dict[str, Any]], manifests_path: Optional[str] = None, include_overrides: bool = False):

        manifests_path = manifests_path or self.manifests_path
        converged_manifests_path = os.path.join(
            manifests_path,os.getenv("K8S_MANIFESTS_PATH", "k8s")
        )
        self.logger.info("Preparing for execution...")

        # Introduce extra manifests included in the overrides.yaml file
        if include_overrides and (config := self.overrider.override_config):
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