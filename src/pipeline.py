from calendar import c
from itertools import count
import json
from math import log
from typing import Any, Dict, List, Optional

from inference.anthropic_client import AnthropicClient
from embeddings.embeddings_engine import EmbeddingsEngine
from embeddings.label_classifier import LabelClassifier
from embeddings.secret_classifier import SecretClassifier
from embeddings.service_classifier import ServiceClassifier
from embeddings.volumes_classifier import VolumesClassifier
from inference.feedback_loop import ManifestFeedbackLoop
from manifests_generation.manifest_builder import ManifestBuilder
from overrides.overrider import Overrider
from tree.compose_mapper import ComposeMapper
from tree.microservices_tree import MicroservicesTree
from tree.node_types import NodeType
from utils.file_utils import save_json, setup_sentence_transformer
from utils.logging_utils import setup_logging
import logging
import os

from validation.metrics_analyzer import MetricsAnalyzer
from validation.kubescape_validator import KubescapeValidator
from validation.manifests_validator import ManifestsValidator
from validation.skaffold_validator import SkaffoldValidator
from tree.node import Node

# Get module-specific logger
logger = logging.getLogger(__name__)


def run():
    """Main application logic"""

    # Set up logging
    setup_logging(
        log_dir="src/logs",
        log_file_name="microservices_tree.log",
        max_size_mb=10,  # 10MB per file
        console_output=True,
        log_level=(
            logging.DEBUG
            if os.getenv("VERBOSE", "false").lower() == "true"
            else logging.INFO
        ),
    )

    target_repository = os.getenv("TARGET_REPOSITORY", "")

    logger.info("Starting microservices manifest generator")

    embedding_model = setup_sentence_transformer()

    # Load the embeddings engine
    embeddings_engine = EmbeddingsEngine(embedding_model)
    # Load the secret classifier
    secret_classifier = SecretClassifier(embeddings_engine)
    # Load the service classifier
    service_classifier = ServiceClassifier(embeddings_engine)
    # Load the label classifier
    label_classifier = LabelClassifier(embeddings_engine)
    # Load the volumes classifier
    volumes_classifier = VolumesClassifier()
    # Load the composer mapper
    composer_mapper = ComposeMapper(
        secret_classifier, volumes_classifier, label_classifier
    )

    # Load the overrider
    overrides_path = os.getenv("OVERRIDES_PATH", "")
    overrider = Overrider(overrides_path)
    # Load the manifest builder
    manifest_builder = ManifestBuilder(overrider)
    # Load the feedback loop components
    generator = AnthropicClient()
    validator = KubescapeValidator()
    # Initialize the feedback loop
    feedback_loop = ManifestFeedbackLoop(
        generator, validator, manifest_builder, overrider
    )

    ### Phase 1: Build the microservices tree ###
    tree_builder = MicroservicesTree(
        embeddings_engine,
        secret_classifier,
        service_classifier,
        label_classifier,
        volumes_classifier,
        composer_mapper,
    )

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
    logger.info(f"Found {len(repositories)} repositories: {repositories}")

    for repo in repositories:
        repository_tree, collected_files = tree_builder.build(
            os.path.join(target_repository, repo)
        )
        tree_builder.print_tree(repository_tree)  # Print the tree structure

        ### Phase 2: First generation with collected files only ###
        logger.info("Generating manifests based on collected files only.")

        generate_without_ir(feedback_loop, collected_files, repo)

        ### Phase 3: Generate the manifests from the repository tree ###
        logger.info("Generating manifests with IR.")
        stage = "with-ir"

        manifests_path = os.path.join(
            os.getenv("OUTPUT_DIR", "output"),
            repo,
            stage,
            os.getenv("MANIFESTS_PATH", "manifests"),
        )

        os.makedirs(manifests_path, exist_ok=True)

        alternative_manifests_path = os.path.join(
            os.getenv("OUTPUT_DIR", "output"),
            repo,
            "with-corrections",
            os.getenv("MANIFESTS_PATH", "manifests"),
        )
        os.makedirs(alternative_manifests_path, exist_ok=True)

        generate_with_ir(
            feedback_loop,
            tree_builder,
            repository_tree,
            overrider,
            manifests_path,
            stage,
            repo,
            False,
            
        )


def generate_with_ir(
    feedback_loop: ManifestFeedbackLoop,
    tree_builder: MicroservicesTree,
    repository_tree: Node,
    overrider: Overrider,
    manifests_path: str,
    stage: str,
    repo: str,
    is_review: bool = False,
    alternative_path: Optional[str] = None,
):
    enriched_services: List[Dict[str, Any]] = []
    for child in repository_tree.children:
        # Then prepare microservices, which might depend on the previous resources
        if child.type == NodeType.MICROSERVICE:
            logging.info(f"Generating manifests for child... {child.name}")
            microservice = tree_builder.prepare_microservice(child)
            microservice["overrides"] = overrider.get_microservice_overrides(
                microservice["name"]
            )
            enriched_services.append(microservice)

    ## DYNAMIC VALIDATION WITH SKAFFOLD
    skaffold_validator = SkaffoldValidator()
    validation_results_path = os.path.join(
        os.getenv("OUTPUT_DIR", "output"), repo, stage, os.getenv("RESULTS", "results")
    )
    os.makedirs(validation_results_path, exist_ok=True)

    feedback_loop.generate_manifests(
        enriched_services, manifests_path, alternative_path
    )
    feedback_loop.prepare_for_execution(enriched_services, manifests_path)

    if alternative_path and alternative_path != "":
        # Prepare also with the alternative path to have the full set of manifests in case of corrections
        feedback_loop.prepare_for_execution(enriched_services, alternative_path)

    if os.getenv("DRY_RUN", "false").lower() == "true":
        logger.info("Dry run enabled, skipping validation.")
        return

    feedback_loop.review_manifests_hardening(manifests_path, validation_results_path)

    skaffold_results = skaffold_validator.validate_cluster_deployment(manifests_path)

    ## Save skaffold validation results
    save_json(
        skaffold_results,
        os.path.join(validation_results_path, "skaffold_validation_results.json"),
    )
    logger.debug(
        f"Saved skaffold results to { os.path.join(validation_results_path, "skaffold_validation_results.json")}"
    )
    logger.info("Done")


def generate_without_ir(
    feedback_loop: ManifestFeedbackLoop, collected_files: Dict[str, Any], repo: str
):
    skaffold_validator = SkaffoldValidator()
    stage = "without-ir"
    manifests_path = os.path.join(
        os.getenv("OUTPUT_DIR", "output"),
        repo,
        stage,
        os.getenv("MANIFESTS_PATH", "manifests"),
    )

    os.makedirs(manifests_path, exist_ok=True)

    validation_results_path = os.path.join(
        os.getenv("OUTPUT_DIR", "output"), repo, stage, os.getenv("RESULTS", "results")
    )
    os.makedirs(validation_results_path, exist_ok=True)

    feedback_loop.generate_manifests_blindly(collected_files, manifests_path)

    feedback_loop.prepare_for_execution(
        list(collected_files.values()), manifests_path, False
    )
    if os.getenv("DRY_RUN", "false").lower() == "true":
        return
    feedback_loop.review_manifests_hardening(manifests_path, validation_results_path)

    ## DYNAMIC VALIDATION WITH SKAFFOLD
    skaffold_results = skaffold_validator.validate_cluster_deployment(manifests_path)

    ## Save skaffold validation results
    save_json(
        skaffold_results,
        os.path.join(validation_results_path, "skaffold_validation_results.json"),
    )
    logger.debug(
        f"Saved skaffold results to { os.path.join(validation_results_path, "skaffold_validation_results.json")}"
    )
    logger.info("Done")


def validate_against_corrected_manifests(
    before_corrections_path: str,
    after_corrections_path: str,
    validation_results_path: str,
):
    """Validate the generated manifests against the ground truth manifests."""

    manifests_validator = ManifestsValidator()

    ## LLM (FINAL) - GROUND TRUTH
    validated_gt_llm_microservices = manifests_validator.validate(
        after_corrections_path, before_corrections_path
    )

    enriched_analysis = manifests_validator.evaluate_issue_severity(
        validated_gt_llm_microservices, after_corrections_path
    )

    ## Save the enriched analysis as csv
    manifests_validator.save_as_csv(
        enriched_analysis,
        os.path.join(
            validation_results_path,
            f"diff_validation_output.csv",
        ),
    )


def review_repository(manifests_path_root: str, reviewed_manifests_root: str):
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
    validator = KubescapeValidator()
    # Initialize the feedback loop
    feedback_loop = ManifestFeedbackLoop(
        generator, validator, manifest_builder
    )

    validation_results_path = os.path.join(
        reviewed_manifests_root, os.getenv("RESULTS", "results")
    )

    os.makedirs(validation_results_path, exist_ok=True)

    reviewed_manifests_path = os.path.join(
        reviewed_manifests_root, os.getenv("MANIFESTS_PATH", "manifests")
    )

    manifests_path = os.path.join(
        manifests_path_root, os.getenv("MANIFESTS_PATH", "manifests")
    )

    feedback_loop.review_manifests_hardening(
        reviewed_manifests_root, validation_results_path
    )

    validate_against_corrected_manifests(
        manifests_path, reviewed_manifests_path, validation_results_path
    )
    
    llm_evaluation = feedback_loop.review_with_llm(
        reviewed_manifests_path)
    
    save_json(
        llm_evaluation,
        os.path.join(validation_results_path, "llm_review_results.json"),
    )
    
    logger.debug(
        f"Saved LLM review results to { os.path.join(validation_results_path, 'llm_review_results.json')}"
    )

    skaffold_results = skaffold_validator.validate_cluster_deployment(
        reviewed_manifests_path
    )

    ## Save skaffold validation results
    save_json(
        skaffold_results,
        os.path.join(validation_results_path, "skaffold_validation_results.json"),
    )
    logger.debug(
        f"Saved skaffold results to { os.path.join(validation_results_path, "skaffold_validation_results.json")}"
    )
    logger.info("Done")
