from copy import deepcopy
from typing import Any, Dict, List, Optional
import json
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

from validation.kubescape_validator import KubescapeValidator
from validation.manifests_validator import ManifestsValidator
from validation.skaffold_validator import SkaffoldValidator
from tree.node import Node

# Get module-specific logger
logger = logging.getLogger(__name__)


def run_generation():
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
    overrider = Overrider()
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
    selected_repos = (
        [r.strip() for r in os.getenv("SELECTED_REPOSITORIES", "").split(",")]
        if os.getenv("SELECTED_REPOSITORIES", "") != ""
        else []
    )
    repositories = [
        repo
        for repo in os.listdir(target_repository)
        if (
            os.path.isdir(os.path.join(target_repository, repo))
            and (repo in selected_repos if len(selected_repos) > 0 else True)
        )
    ]
    repositories.sort()
    logger.info(f"Found {len(repositories)} repositories: {repositories}")

    for repo in repositories:
        repository_tree, collected_files = tree_builder.build(
            os.path.join(target_repository, repo)
        )
        
        tree_builder.print_tree(repository_tree)  # Print the tree structure
        
        overrider.config_path = os.path.join(
            target_repository, repo, os.getenv("OVERRIDES_FILE", "")
        )

        stages = [
            "without-ir",
             "with-ir",            
            ]
        if overrider.config_path and os.path.exists(overrider.config_path):
            stages.append("with-overrides")

        ### Phase 2: Generate manifests ###
        for stage in stages:

            ## Create output directories
            manifests_path = os.path.join(
                os.getenv("OUTPUT_DIR", "output"),
                repo,
                stage,
                os.getenv("MANIFESTS_PATH", "manifests"),
            )
            os.makedirs(manifests_path, exist_ok=True)
            
            corrected_manifests_path = None
            
            if stage != "without-ir":
                ## Create corrected manifests path
                corrected_manifests_path = os.path.join(
                    os.getenv("OUTPUT_DIR", "output"),
                    repo,
                    f"{stage}-corrected",
                    os.getenv("MANIFESTS_PATH", "manifests"),
                )
                os.makedirs(corrected_manifests_path, exist_ok=True)

            ## Create validation results path
            validation_results_path = os.path.join(
                os.getenv("OUTPUT_DIR", "output"),
                repo,
                stage,
                os.getenv("RESULTS", "results"),
            )
            os.makedirs(validation_results_path, exist_ok=True)

            ## Generate manifests based on the stage
            if stage == "without-ir":
                logger.info("Generating manifests based on collected files only.")
                generate_without_ir(feedback_loop, validation_results_path, manifests_path, collected_files)

            else:
                logger.info(f"Generating manifests for stage: {stage}.")
                generate_with_ir(
                    feedback_loop,
                    tree_builder,
                    repository_tree,
                    overrider,
                    manifests_path,
                    validation_results_path,
                    (stage == "with-overrides"),
                    corrected_manifests_path,
                    collected_files,
                )


def generate_with_ir(
    feedback_loop: ManifestFeedbackLoop,
    tree_builder: MicroservicesTree,
    repository_tree: Node,
    overrider: Overrider,
    manifests_path: str,
    validation_results_path: str,
    apply_overrides: bool = False,
    corrected_manifests_path: Optional[str] = None,
    collected_files: Optional[Dict[str, Any]] = None,
):
    enriched_services: List[Dict[str, Any]] = []
    enriched_services_with_overrides: List[Dict[str, Any]] = overrider.get_extra_manifests()
    for child in repository_tree.children:
        # Then prepare microservices, which might depend on the previous resources
        if child.type == NodeType.MICROSERVICE:
            logging.info(f"Generating manifests for child... {child.name}")
            microservice = tree_builder.prepare_microservice(child)
            enriched_services.append(microservice)

            if apply_overrides:
                microservice_with_overrides = deepcopy(microservice)
                microservice_with_overrides["overrides"] = overrider.get_microservice_overrides(
                    microservice["name"]
                )
                enriched_services_with_overrides.append(microservice_with_overrides)
    
    if apply_overrides:
        feedback_loop.generate_manifests(
            enriched_services_with_overrides, manifests_path, corrected_manifests_path
        )
    else:
        feedback_loop.generate_manifests(
            enriched_services, manifests_path, corrected_manifests_path
        )
    
    validate_output(
        feedback_loop,
        enriched_services,
        validation_results_path,
        manifests_path,
        corrected_manifests_path,
        collected_files=collected_files,
    )

    logger.info("Done")


def generate_without_ir(
    feedback_loop: ManifestFeedbackLoop,
    validation_results_path: str,
    manifests_path: str,
    collected_files: Dict[str, Any],
):

    feedback_loop.generate_manifests_blindly(collected_files, manifests_path)
    validate_output(
        feedback_loop,
        list(collected_files.values()),
        validation_results_path,
        manifests_path,
        collected_files=collected_files,
    )

    ## Save collected files for reference
    json.dump(collected_files, open(os.path.join(validation_results_path, "collected_files.json"), "w"), indent=4)

    logger.debug(
        f"Saved skaffold results to { os.path.join(validation_results_path, "skaffold_validation_results.json")}"
    )

    logger.info("Done")


def validate_output(
    feedback_loop: ManifestFeedbackLoop,
    microservices: List[Dict[str, Any]],
    validation_results_path: str,
    manifests_path: str,
    corrected_manifests_path: Optional[str] = None,
    collected_files: Optional[Dict[str, Any]] = None,
):
    feedback_loop.prepare_for_execution(microservices, manifests_path)
    if corrected_manifests_path:
        feedback_loop.prepare_for_execution(
            microservices, corrected_manifests_path
        )
    if os.getenv("DRY_RUN", "false").lower() == "true":
        logger.info("Dry run enabled, skipping validation.")
        return

    ## DYNAMIC VALIDATION WITH SKAFFOLD
    skaffold_validator = SkaffoldValidator()
    skaffold_results = skaffold_validator.validate_cluster_deployment(manifests_path)

    save_json(
        skaffold_results,
        os.path.join(validation_results_path, "skaffold_validation_results.json"),
    )

    if os.getenv("DRY_RUN", "false").lower() == "true":
        logger.info("Dry run enabled, skipping validation.")
        return

    ## STATIC VALIDATION WITH KUBESCAPE
    feedback_loop.review_manifests_hardening(manifests_path, validation_results_path)

    ## LLM Review
    if collected_files:
        llm_evaluation = feedback_loop.review_with_llm(manifests_path, collected_files)

        save_json(
            llm_evaluation,
            os.path.join(validation_results_path, "llm_review_results.json"),
        )
        logger.debug(
            f"Saved LLM review results to { os.path.join(validation_results_path, 'llm_review_results.json')}"
        )
