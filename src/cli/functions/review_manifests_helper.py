from typing import Any, Dict, List, Optional

from inference.anthropic_client import AnthropicClient
from inference.feedback_loop import ManifestFeedbackLoop
from manifests_generation.manifest_builder import ManifestBuilder
from tree.node_types import NodeType
from utils.file_utils import load_json_file, save_json, setup_sentence_transformer
from utils.logging_utils import setup_logging
import logging
import os

from validation import manifests_validator
from validation.kubescape_validator import KubescapeValidator
from validation.skaffold_validator import SkaffoldValidator
from validation.manifests_validator import ManifestsValidator
from tree.node import Node

logger = logging.getLogger(__name__)


def run_review_manifests():
    """Review the generated manifests using the LLM for best practices, security, and correctness."""
    # Set up logging
    setup_logging(
        log_dir="src/logs",
        log_file_name="microservices_validation.log",
        max_size_mb=10,  # 10MB per file
        console_output=True,
        log_level=(
            logging.DEBUG
            if os.getenv("VERBOSE", "false").lower() == "true"
            else logging.INFO
        ),
    )

    logger.info("Starting review of generated manifests")

    skaffold_validator = SkaffoldValidator()

    # Load the manifest builder
    manifest_builder = ManifestBuilder()
    # Load the feedback loop components
    generator = AnthropicClient()
    kubescabe_validator = KubescapeValidator()
    manifests_validator = ManifestsValidator()
    # Initialize the feedback loop
    feedback_loop = ManifestFeedbackLoop(generator, kubescabe_validator, manifest_builder)

    target_repository = os.getenv("OUTPUT_DIR", "")
    os.makedirs(target_repository, exist_ok=True)
    
    repositories = [
        repo
        for repo in os.listdir(target_repository)
        if (
            os.path.isdir(os.path.join(target_repository, repo))
            and repo in os.getenv("SELECTED_REPOSITORIES", "").split(",")
            if os.getenv("SELECTED_REPOSITORIES", "") != ""
            else True
        )
    ]
    repositories.sort()

    for repo in repositories:
        logging.info(f"Reviewing manifests for repository... {repo}")

        no_ir_results = os.path.join(
            target_repository,
            repo,
            "without-ir",
            os.getenv("RESULTS", "results"),
        )

        collected_files = load_json_file(
            os.path.join(no_ir_results, "collected_files.json")
        )
        for stage in [
            "with-ir",
            "with-overrides"
        ]:
            logging.info(f"Reviewing manifests for stage... {stage}")

            manifests_root = os.path.join(
                target_repository,
                repo,
                stage,
            )
            if not os.path.exists(manifests_root):
                logging.warning(
                    f"Manifests root path does not exist: {manifests_root}. Skipping."
                )
                continue

            reviewed_manifests_root = os.path.join(
                target_repository,
                repo,
                f"{stage}-corrected",
            )

            manifests_path = os.path.join(
                manifests_root,
                os.getenv("MANIFESTS_PATH", "manifests"),
            )

            validation_results_path__reviewed = os.path.join(
                reviewed_manifests_root, os.getenv("RESULTS", "results")
            )

            validation_results_path__not_reviewed = os.path.join(
                manifests_root, os.getenv("RESULTS", "results")
            )

            os.makedirs(validation_results_path__reviewed, exist_ok=True)
            os.makedirs(validation_results_path__not_reviewed, exist_ok=True)

            reviewed_manifests_path = os.path.join(
                reviewed_manifests_root, os.getenv("MANIFESTS_PATH", "manifests")
            )

            ## Kubescape
            feedback_loop.review_manifests_hardening(
                reviewed_manifests_path, validation_results_path__reviewed
            )

            ## Validate against corrected manifests
            manifests_validator.levenshtein_manifests_distance(
                manifests_path, reviewed_manifests_path
            )

            ## LLM Review
            llm_evaluation = feedback_loop.review_with_llm(reviewed_manifests_path, collected_files)

            save_json(
                llm_evaluation,
                os.path.join(validation_results_path__reviewed, "llm_review_results.json"),
            )

            logger.debug(
                f"Saved LLM review results to { os.path.join(validation_results_path__reviewed, 'llm_review_results.json')}"
            )

            ## Dynamic Validation with Skaffold
            skaffold_results = skaffold_validator.validate_cluster_deployment(
                reviewed_manifests_path
            )

            ## Save skaffold validation results
            save_json(
                skaffold_results,
                os.path.join(
                    validation_results_path__reviewed, "skaffold_validation_results.json"
                ),
            )
            logger.debug(
                f"Saved skaffold results to { os.path.join(validation_results_path__reviewed, "skaffold_validation_results.json")}"
            )
    logger.info("Done")
