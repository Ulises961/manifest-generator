import gc
import time
from typing import Any, Dict, List
from sentence_transformers import SentenceTransformer
import torch
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
    manifest_builder = ManifestBuilder()
    enriched_services: List[Dict[str, Any]] = []
    for child in repository_tree.children:
        logging.info(f"Generating manifests for child... {child.name}")
        microservice = treebuilder.prepare_microservice(child)
        enriched_services.append(microservice)
        manifest_builder.generate_manifests(microservice)

    # Unload the model
    del treebuilder
    del manifest_builder
    del secret_classifier
    del service_classifier
    del label_classifier
    del embeddings_engine
    del embeddings_model

    ### Phase 3: Generate inferred manifests from the repository tree ###
    # Load the inference models
    inference_model, tokenizer, device = setup_inference_models()

    if inference_model is None or tokenizer is None:
        logger.error("Failed to load inference model or tokenizer.")
        raise RuntimeError("Inference model or tokenizer not loaded.")

    # Load the inference engine
    inference_engine = InferenceEngine(inference_model, tokenizer, device)

    # Load the prompt builder
    prompt_builder = PromptBuilder(enriched_services)

    inference_config = {
        "max_new_tokens": 1024,  # Limit output length to avoid rambling
        "temperature": 0.01,  # Lower temperature = more deterministic
        "top_p": 0.85,  # Reduce sampling pool
        "do_sample": True,  # Keep on for diversity, but limit randomness
        "repetition_penalty": 1.1,  # Avoid loops
        "no_repeat_ngram_size": 3,  # Prevent local repetition
    }

    for microservice in enriched_services:
        logging.info(f"Generating manifests for child... {microservice['name']}")
        prompt = prompt_builder.generate_prompt(microservice)

        # Generate the response
        response = inference_engine.generate(prompt, inference_config)
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

    ### Phase 4: Refine the generated manifests ###

    # Compile the helm charts generated in phase 2 and compare the generated manifests with the original ones

    # Second pass on the generated manifests.
    prompt_builder.generate_second_pass_prompt()

    generated_manifests_dir = os.path.join(
        os.getenv("TARGET_PATH", "target"),
        os.getenv("MANIFESTS_PATH", "manifests"),
        os.getenv("LLM_MANIFESTS_PATH", "llm"),
        "first_pass",
    )

    for root, dirs, files in os.walk(generated_manifests_dir):
        for file in files:
            if file.endswith(".yaml") or file.endswith(".yml"):
                file_path = os.path.join(root, file)
                with open(file_path, "r") as f:
                    attached_file = AttachedFile(
                        name=file,
                        type="yaml",
                        size=os.path.getsize(file_path),
                        content=f.read(),
                    )
                    prompt_builder.attach_file(attached_file)
                    logging.info(f"Attached file: {file_path}")
                    # Attach the file to the prompt

    prompt_builder.include_attached_files()
    # Generate the response
    response = inference_engine.generate(prompt_builder.get_prompt())
    # Process the response
    processed_response = inference_engine.process_response(response)

    for manifest in processed_response:
        logging.info(f"Generated manifest: {manifest['name']}")

        target_dir = os.path.join(
            os.getenv("TARGET_PATH", "target"),
            os.getenv("MANIFESTS_PATH", "manifests"),
            os.getenv("LLM_MANIFESTS_PATH", "llm"),
            "second_pass",
        )

        os.makedirs(target_dir, exist_ok=True)
        # Save the response to a file
        manifest_path = os.path.join(target_dir, f"{manifest['name']}.yaml")
        with open(manifest_path, "w") as f:
            f.write(manifest["manifest"])
        logging.info(f"Saved manifest to {target_dir}/{manifest['name']}.yaml")
