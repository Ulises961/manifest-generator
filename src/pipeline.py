from typing import Any, Dict, List

from caseutil import to_snake
from embeddings.embeddings_engine import EmbeddingsEngine
from embeddings.label_classifier import LabelClassifier
from embeddings.secret_classifier import SecretClassifier
from embeddings.service_classifier import ServiceClassifier
from embeddings.volumes_classifier import VolumesClassifier
from inference.prompt_builder import PromptBuilder
from inference.inference_processor import InferenceProcessor
from manifests_generation.manifest_builder import ManifestBuilder
from overrides.overrider import Overrider
from tree.microservices_tree import MicroservicesTree
from utils.file_utils import setup_sentence_transformer
from utils.logging_utils import setup_logging
import logging
import os
from huggingface_hub import InferenceClient
import anthropic

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
        os.getenv("TARGET_PATH", "target"),
        os.getenv("MANIFESTS_PATH", "manifests"),
        os.getenv("MANUAL_MANIFESTS_PATH", "manual"),
    )

    manifest_builder.generate_skaffold_config(enriched_services, manual_manifests_path)

    # ### Phase 3: Generate inferred manifests from the repository tree ###

    # Prepare a http client to query the LLM
    base_url = "http://localhost:8080"
    endpoint = os.getenv("LLM_ENDPOINT", f"{base_url}/v1/chat/completions")

    inference_client = InferenceClient(
        model=endpoint,
        headers={"Content-Type": "application/json"},
    )
    inference_client = anthropic.Anthropic()


    if os.getenv("DRY_RUN", "false").lower() == "true":
        logger.info("Running in dry run mode, skipping LLM inference.")
    
    
    prompt_builder = PromptBuilder()
    inference_processor = InferenceProcessor()
    for microservice in enriched_services:
        logging.info(f"Generating manifests for child... {microservice['name']}")
        for manifest in microservice["manifests"]:
            ## Attach the files to the prompt
            for attached_file in microservice.get("attached_files", {}):
                prompt_builder.attach_file(attached_file)
        prompt = prompt_builder.generate_prompt(microservice, enriched_services)

        if os.getenv("DRY_RUN", "false").lower() == "true":
            logging.info(f"Dry mode enabled, skipping LLM inference.\n\n----\n")
            continue

        ## Generate the response
        response = inference_client.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=3000,
            temperature=0,
            system=prompt_builder._generate_system_prompt(),  # type: ignore
            messages=prompt # type: ignore
            )
   
        logging.debug(f"Response from LLM: {response.model_dump_json()}")
        logging.info(f"Content from LLM: {response.content}")

        processed_response = inference_processor.process_response(response.content) # type: ignore
        
        logger.info(f"Received response for {microservice['name']}: {processed_response}")

        # Save the manifests to the target directory
        llm_manifests_path = os.path.join( os.getenv("TARGET_PATH", "target"),
                os.getenv("MANIFESTS_PATH", "manifests"),
                os.getenv("LLM_MANIFESTS_PATH", "llm"))

        os.makedirs(llm_manifests_path, exist_ok=True)


        for manifest in processed_response:
            logging.info(f"Generated manifest: {microservice['name']}")

            target_dir = os.path.join(
                llm_manifests_path,
                os.getenv("K8S_MANIFESTS_PATH", "k8s"),
                to_snake(manifest['name'])
            )

            os.makedirs(target_dir, exist_ok=True)

            # Save the response to a file
            manifest_path = os.path.join(target_dir, f"{microservice['name']}.yaml")
            
            with open(manifest_path, "w") as f:
                f.write(manifest["manifest"])

            logging.info(f"Saved manifest to {manifest_path}")


        # Introduce extra manifests included in the overrides.yaml file
        if config := overrider.override_config:
            if config.get("customManifests", None):
                for manifest_name, manifest_content in config["customManifests"].items():
                    # Log the manifest name and content
                    logger.debug(f"Processing custom manifest: {manifest_name}")

                    # Save the custom manifest
                    manifest_path = os.path.join(llm_manifests_path, os.getenv("K8S_MANIFESTS_PATH", "k8s"), f"{manifest_name}.yaml")
                    manifest_builder._save_yaml(manifest_content, manifest_path)
                    logger.info(f"Custom manifest saved: {manifest_path}")

        manifest_builder.generate_skaffold_config(
            enriched_services, # For the Dockerfile paths of the repository scanned
            llm_manifests_path
        )