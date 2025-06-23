from typing import Any, Dict, List
from sentence_transformers import SentenceTransformer
from embeddings.embeddings_engine import EmbeddingsEngine
from embeddings.label_classifier import LabelClassifier
from embeddings.secret_classifier import SecretClassifier
from embeddings.service_classifier import ServiceClassifier
from inference.inference_engine import InferenceEngine
from inference.prompt_builder import PromptBuilder
from manifests_generation.helm_renderer import HelmRenderer
from manifests_generation.manifest_builder import ManifestBuilder
from tree.attached_file import AttachedFile
from tree.microservices_tree import MicroservicesTree
from utils.file_utils import (
    load_environment,
    setup_inference_models,
    setup_sentence_transformer,
)
from utils.logging_utils import setup_logging
import logging
import os
from accelerate import Accelerator

# Get module-specific logger
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    # Load environment variables
    load_environment()

    # Set up logging
    setup_logging(
        log_dir="src/logs",
        log_file_name="microservices_tree.log",
        max_size_mb=10,  # 10MB per file
        console_output=True,
    )

    target_repository = os.getenv("TARGET_REPOSITORY", "")

    logger.info("Starting microservices manifest generator")
    
    # Load the SentenceTransformer model
    embeddings_model: SentenceTransformer = setup_sentence_transformer()

    # Load the embeddings engine
    embeddings_engine = EmbeddingsEngine(embeddings_model)
    # Load the secret classifier
    secret_classifier = SecretClassifier(embeddings_engine)
    # Load the service classifier
    service_classifier = ServiceClassifier(embeddings_engine)
    # Load the label classifier
    label_classifier = LabelClassifier(embeddings_engine)
    # Generate a tree with the microservices detected in the repository

    ### Phase 1: Build the microservices tree ###
    treebuilder = MicroservicesTree(
        target_repository,
        embeddings_engine,
        secret_classifier,
        service_classifier,
        label_classifier,
    )

    repository_tree = treebuilder.build()
    treebuilder.print_tree(repository_tree)  # Print the tree structure

    ### Phase 2: Generate the manifests from the repository tree ###
    accelerator = Accelerator()
    manifest_builder = ManifestBuilder(accelerator)
    enriched_services: List[Dict[str, Any]] = []
    for child in repository_tree.children:
        logging.info(f"Generating manifests for child... {child.name}")
        microservice = treebuilder.prepare_microservice(child)
        enriched_services.append(microservice)
        manifest_builder.generate_manifests(microservice)

    # Add Skaffold config to build its image
    manifest_builder.generate_skaffold_config(enriched_services)
    
    ### Phase 3: Generate inferred manifests from the repository tree ###
    # Load the inference models
    inference_model, tokenizer, device = setup_inference_models()

    if inference_model is None or tokenizer is None:
        logger.error("Failed to load inference model or tokenizer.")
        raise RuntimeError("Inference model or tokenizer not loaded.")

    # Load the inference engine
    inference_engine = InferenceEngine(inference_model, tokenizer, embeddings_engine, device)

    # Load the prompt builder
    prompt_builder = PromptBuilder()



    for microservice in enriched_services:
        logging.info(f"Generating manifests for child... {microservice['name']}")
        for manifest in microservice["manifests"]:
            # Attach the files to the prompt            
            for attached_file in microservice.get("attached_files", {}):
                prompt_builder.attach_file(attached_file)
        prompt = prompt_builder.generate_prompt(microservice, enriched_services)

        # Generate the response
        response = inference_engine.generate(prompt)
        # Process the response
        processed_response = inference_engine.process_response(response)

        for manifest in processed_response:
            logging.info(f"Generated manifest: {microservice['name']}")

            target_dir = os.path.join(
                os.getenv("TARGET_PATH", "target"),
                os.getenv("MANIFESTS_PATH", "manifests"),
                os.getenv("LLM_MANIFESTS_PATH", "llm"),
                "first_pass",
                microservice["name"],
            )

            os.makedirs(target_dir, exist_ok=True)

            # Save the response to a file
            manifest_path = os.path.join(target_dir, f"{manifest['name']}.yaml")

            with open(manifest_path, "w") as f:
                f.write(manifest["manifest"])

            logging.info(f"Saved manifest to {target_dir}/{manifest['name']}.yaml")

