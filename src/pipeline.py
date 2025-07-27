import json
from typing import Any, Dict, List
from inference.anthropic_client import AnthropicClient
from embeddings.embeddings_engine import EmbeddingsEngine
from embeddings.label_classifier import LabelClassifier
from embeddings.secret_classifier import SecretClassifier
from embeddings.service_classifier import ServiceClassifier
from embeddings.volumes_classifier import VolumesClassifier
from inference.feedback_loop import ManifestFeedbackLoop
from manifests_generation.manifest_builder import ManifestBuilder
from overrides.overrider import Overrider
from tree.microservices_tree import MicroservicesTree
from utils.file_utils import setup_sentence_transformer
from utils.logging_utils import setup_logging
import logging
import os

from validation.metrics_analyzer import MetricsAnalyzer
from validation.kubescape_validator import KubescapeValidator
from validation.manifests_validator import ManifestsValidator

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
        log_level=logging.DEBUG if os.getenv("VERBOSE", "false").lower() == "true" else logging.INFO
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
    # Generate a tree with the microservices detected in the repository

    ### Phase 1: Build the microservices tree ###
    treebuilder = MicroservicesTree(
        target_repository,
        embeddings_engine,
        secret_classifier,
        service_classifier,
        label_classifier,
        volumes_classifier, 
    )

    repository_tree = treebuilder.build()
    treebuilder.print_tree(repository_tree)  # Print the tree structure

    ### Phase 2: Generate the manifests from the repository tree ###
    overrider = Overrider(os.getenv("OVERRIDES_FILE_PATH", ""))

    manifest_builder = ManifestBuilder(overrider)

    enriched_services: List[Dict[str, Any]] = []

    for child in repository_tree.children:
        logging.info(f"Generating manifests for child... {child.name}")
        microservice = treebuilder.prepare_microservice(child)
        enriched_services.append(microservice)
        manifest_builder.generate_manifests(microservice)

    # Introduce extra manifests included in the overrides.yaml file
    if config := overrider.override_config:
        if config.get("customManifests", None):
            for manifest_name, manifest_content in config["customManifests"].items():
                # Log the manifest name and content
                logger.debug(f"Processing custom manifest: {manifest_name}")

                # Save the custom manifest
                manifest_path = os.path.join(manifest_builder.k8s_manifests_path, f"{manifest_name}.yaml")
                manifest_builder._save_yaml(manifest_content, manifest_path)
                logger.info(f"Custom manifest saved: {manifest_path}")
               
    ## Add Skaffold config to build its image
    manual_manifests_path = os.path.join(
        os.getenv("OUTPUT_DIR", "target"),
        os.getenv("MANIFESTS_PATH", "manifests"),
        os.getenv("MANUAL_MANIFESTS_PATH", "manual"),
    )

    manifest_builder.generate_skaffold_config(enriched_services, manual_manifests_path)

    # # ### Phase 3: Generate manifests from the repository tree ###
    generator = AnthropicClient()
    evaluator = AnthropicClient()
    validator = KubescapeValidator()

    if os.getenv("DRY_RUN", "false").lower() == "true":
        logger.info("Running in dry run mode, skipping LLM inference.")
    
    else:
        logger.info("Running in production mode, generating manifests with LLM.")
        feedback_loop = ManifestFeedbackLoop(
            generator,
            evaluator,
            validator,
            manifest_builder,
            overrider
        )

        feedback_loop.generate_manifests(enriched_services)

        feedback_loop.refine_manifests(enriched_services)
    

    # ### Phase 4: Validate the generated manifests ###
    logger.info("Validating generated manifests by comparison.")
    manifests_validator = ManifestsValidator(embeddings_engine)
    metrics_analyzer = MetricsAnalyzer()

    manual_manifests_path = os.path.join(manual_manifests_path, "k8s")
    llm_manifests_path_v0 = os.path.join(
        os.getenv("OUTPUT_DIR", "target"),
        os.getenv("MANIFESTS_PATH", "manifests"),
        os.getenv("LLM_MANIFESTS_PATH", "llm"),
        os.getenv("V0", "v0")
    )

    llm_manifests_path_final = os.path.join(
        os.getenv("OUTPUT_DIR", "target"),
        os.getenv("MANIFESTS_PATH", "manifests"),
        os.getenv("LLM_MANIFESTS_PATH", "llm"),
        os.getenv("REVIEWED_MANIFESTS", "final_manifests")
    )

    ground_truth_manifests = os.path.join(
        os.getenv("TARGET_REPOSITORY", "target"),
        "..",
        "kubernetes-manifests",
        "k8s"
    )

    validation_results_path =  os.path.join(os.getenv("OUTPUT_DIR", "target"), os.getenv("RESULTS", "results"))
    os.makedirs(validation_results_path, exist_ok= True)

    ## LLM (V0) - MWC 
    validated_llm_mwc_microservices = manifests_validator.validate(llm_manifests_path_v0, manual_manifests_path)
    enriched_analysis =    manifests_validator.evaluate_issue_severity(validated_llm_mwc_microservices)
    # Save the summary of the validation
    manifests_validator.save_analysis(
        enriched_analysis,
        os.path.join(validation_results_path, "llm_v0_mwc_validation_output.json")
    )
    # Generate a csv summary of the validation
    analysis = metrics_analyzer.analyze(validated_llm_mwc_microservices)
    metrics_analyzer.save_summary(analysis, os.path.join(validation_results_path, "llm_v0_mwc_diff_analysis.csv"))

    ## LLM (V0)- GROUND TRUTH
    validated_gt_llm_microservices = manifests_validator.validate(llm_manifests_path_v0, ground_truth_manifests)
    enriched_analysis = manifests_validator.evaluate_issue_severity(validated_gt_llm_microservices)
    # Save the summary of the validation
    manifests_validator.save_analysis(
        enriched_analysis,
        os.path.join(validation_results_path, "gt_llm_v0_validation_output.json")
    )
    # Generate a csv summary of the validation
    analysis = metrics_analyzer.analyze(validated_gt_llm_microservices)
    metrics_analyzer.save_summary(analysis, os.path.join(validation_results_path, "ground_truth_llm_v0_summary.csv"))


    ## LLM (FINAL) - MWC 
    validated_llm_mwc_microservices = manifests_validator.validate(llm_manifests_path_final, manual_manifests_path)
    enriched_analysis =    manifests_validator.evaluate_issue_severity(validated_llm_mwc_microservices)
    # Save the summary of the validation
    manifests_validator.save_analysis(
        enriched_analysis,
        os.path.join(validation_results_path, "llm_final_mwc_validation_output.json")
    )
    # Generate a csv summary of the validation
    analysis = metrics_analyzer.analyze(validated_llm_mwc_microservices)
    metrics_analyzer.save_summary(analysis, os.path.join(validation_results_path, "llm_final_mwc_diff_analysis.csv"))

    ## LLM (FINAL) - GROUND TRUTH
    validated_gt_llm_microservices = manifests_validator.validate(llm_manifests_path_final, ground_truth_manifests)
    enriched_analysis = manifests_validator.evaluate_issue_severity(validated_gt_llm_microservices)
    # Save the summary of the validation
    manifests_validator.save_analysis(
        enriched_analysis,
        os.path.join(validation_results_path, "gt_llm_final_validation_output.json")
    )
    # Generate a csv summary of the validation
    analysis = metrics_analyzer.analyze(validated_gt_llm_microservices)
    metrics_analyzer.save_summary(analysis, os.path.join(validation_results_path, "ground_truth_llm_final_summary.csv"))


    ## MWC - GROUND TRUTH
    validated_gt_mwc_microservices = manifests_validator.validate(manual_manifests_path, ground_truth_manifests)
    enriched_analysis = manifests_validator.evaluate_issue_severity(validated_gt_mwc_microservices)
    # Save the summary of the validation
    manifests_validator.save_analysis(
        enriched_analysis,
        os.path.join(validation_results_path, "gt_mwc_validation_output.json")
    )
    # Generate a csv summary of the validation
    analysis = metrics_analyzer.analyze(validated_gt_mwc_microservices)
    metrics_analyzer.save_summary(analysis, os.path.join(validation_results_path, "ground_truth_mwc_summary.csv"))

