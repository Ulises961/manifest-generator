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
from validation.skaffold_validator import SkaffoldValidator
    
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

    # for child in repository_tree.children:
    #     logging.info(f"Generating manifests for child... {child.name}")
    #     microservice = treebuilder.prepare_microservice(child)
    #     microservice["overrides"] = overrider.get_microservice_overrides(microservice['name'])
    #     enriched_services.append(microservice)

    # generator = AnthropicClient()
    # evaluator = AnthropicClient()
    # validator = KubescapeValidator()

    # feedback_loop = ManifestFeedbackLoop(
    #     generator,
    #     evaluator,
    #     validator,
    #     manifest_builder,
    #     overrider
    # )

    # feedback_loop.generate_manifests(enriched_services)

    # feedback_loop.review_manifests(enriched_services)
    

    # # ### Phase 4: Validate the generated manifests ###
    # logger.info("Validating generated manifests by comparison.")
    manifests_validator = ManifestsValidator(embeddings_engine)
    metrics_analyzer = MetricsAnalyzer()

    llm_manifests_path_final = os.path.join(
        os.getenv("OUTPUT_DIR", "output"),
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

    validation_results_path =  os.path.join(os.getenv("OUTPUT_DIR", "output"), os.getenv("RESULTS", "results"))
    os.makedirs(validation_results_path, exist_ok= True)


    ## LLM (FINAL) - GROUND TRUTH
    validated_gt_llm_microservices = manifests_validator.validate(llm_manifests_path_final, ground_truth_manifests)
    enriched_analysis = manifests_validator.evaluate_issue_severity(validated_gt_llm_microservices)
    #Add validation stage
    enriched_analysis.update({"stage": "before_manual_intervention"})
    # Save the summary of the validation
    manifests_validator.save_analysis(
        enriched_analysis,
        os.path.join(validation_results_path, "gt_llm_final_validation_output.json")
    )

    # Save the enriched analysis as csv
    manifests_validator.save_as_csv(enriched_analysis, os.path.join(validation_results_path, "gt_llm_final_validation_output.csv"))
        
    # Generate a csv summary of the validation
    analysis = metrics_analyzer.analyze(validated_gt_llm_microservices)
    analysis_csv = metrics_analyzer.summary_to_csv(analysis)
    metrics_analyzer.save_csv(analysis_csv, os.path.join(validation_results_path, "ground_truth_llm_final_summary.csv"))


    # ## DYNAMIC VALIDATION WITH SKAFFOLD
    # skaffold_validator = SkaffoldValidator()
    # skaffold_results = skaffold_validator.validate_cluster_deployment(llm_manifests_path_final)
    
    # # Save skaffold validation results
    # with open(os.path.join(validation_results_path, "skaffold_validation_results.json"), 'w') as f:
    #     json.dump(skaffold_results, f, indent=2)
    
