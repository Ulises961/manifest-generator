from sentence_transformers import SentenceTransformer
from embeddings.embeddings_engine import EmbeddingsEngine
from embeddings.label_classifier import LabelClassifier
from embeddings.secret_classifier import SecretClassifier
from embeddings.service_classifier import ServiceClassifier
from manifest_builder import ManifestBuilder
from tree.microservices_tree import MicroservicesTree
from utils.file_utils import load_environment, setup_sentence_transformer
from utils.logging_utils import setup_logging
import logging

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
        console_output=True
    )
    
    logger.info("Starting microservices manifest generator")

    # Load the SentenceTransformer model
    model: SentenceTransformer = setup_sentence_transformer()

    # Load the embeddings engine
    embeddings_engine = EmbeddingsEngine(model)
    # Load the secret classifier
    secret_classifier = SecretClassifier(embeddings_engine)
    # Load the service classifier
    service_classifier = ServiceClassifier(embeddings_engine)
    # Load the label classifier
    label_classifier = LabelClassifier(embeddings_engine)
    # Generate a tree with the microservices detected in the repository
    target_repository = "/home/ulises/Documents/UniTn/2nd Year/2 semester/Tirocinio/microservices-demo/src"
    treebuilder = MicroservicesTree(
        target_repository,
        embeddings_engine,
        secret_classifier,
        service_classifier,
        label_classifier,
    )
    
    repository_tree = treebuilder.build()
    treebuilder.print_tree(repository_tree)  # Print the tree structure

    # Generate the manifests from the repository tree
    manifest_builder = ManifestBuilder(embeddings_engine)
    for child in repository_tree.children:
        logging.info(f"Generating manifests for child... {child.name}")
        microservice = treebuilder.prepare_microservice(child)
        manifest_builder.generate_manifests(microservice)