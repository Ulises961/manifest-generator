from typing import Any, Dict, List
from embeddings.embeddings_client import EmbeddingsClient
from embeddings.label_classifier import LabelClassifier
from embeddings.secret_classifier import SecretClassifier
from embeddings.service_classifier import ServiceClassifier
from inference.prompt_builder import PromptBuilder
from inference.inference_processor import InferenceProcessor
from manifests_generation.manifest_builder import ManifestBuilder
from tree.microservices_tree import MicroservicesTree
from utils.file_utils import (
    load_environment
)
from utils.logging_utils import setup_logging
import logging
import os
from huggingface_hub import InferenceClient
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
    )

    target_repository = os.getenv("TARGET_REPOSITORY", "")

    logger.info("Starting microservices manifest generator")

    # Load the embeddings engine
    embeddings_engine = EmbeddingsClient(os.getenv("EMBEDDINGS_MODEL", "all-MiniLM-L6-v2"))
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
    manifest_builder = ManifestBuilder(os.getenv("OVERRIDES_FILE_PATH", ""))
    enriched_services: List[Dict[str, Any]] = []
    for child in repository_tree.children:
        logging.info(f"Generating manifests for child... {child.name}")
        microservice = treebuilder.prepare_microservice(child)
        microservice = manifest_builder.apply_config_overrides(
            os.getenv("OVERRIDES_FILE_PATH", ""), microservice
        )
        enriched_services.append(microservice)
        manifest_builder.generate_manifests(microservice)

    ## Add Skaffold config to build its image
    manifest_builder.generate_skaffold_config(enriched_services)

    # ### Phase 3: Generate inferred manifests from the repository tree ###

    # Prepare a http client to query the LLM
    base_url = "http://localhost:8080"
    endpoint = "https://stivo.disi.unitn.it/user/ulisesemiliano.sosa/code-server/proxy/8080/" #os.getenv("LLM_ENDPOINT", f"{base_url}/v1/chat/completions")

    inference_client = InferenceClient(
        model=base_url,
        headers={"Content-Type": "application/json"},
    )

    prompt_builder = PromptBuilder()
    inference_processor = InferenceProcessor()
    for microservice in enriched_services:
        logging.info(f"Generating manifests for child... {microservice['name']}")
        for manifest in microservice["manifests"]:
            ## Attach the files to the prompt
            for attached_file in microservice.get("attached_files", {}):
                prompt_builder.attach_file(attached_file)
        prompt = prompt_builder.generate_prompt(microservice, enriched_services)

        ## Generate the response
        try:
            response = inference_client.chat_completion(
                messages= prompt,   
                max_tokens=3000)
        ## Process the response
        except Exception as e:
            logging.error(e)
            exit(0)

        processed_response = inference_processor.process_response(response.choices[0]['message']['content'])
        
        logger.info(f"Received response for {microservice['name']}: {processed_response}")
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
