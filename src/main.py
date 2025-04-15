
from sentence_transformers import SentenceTransformer
from embeddings.embeddings_engine import EmbeddingsEngine
from embeddings.label_classifier import LabelClassifier
from embeddings.secret_classifier import SecretClassifier
from embeddings.service_classifier import ServiceClassifier
from tree.microservices_tree import MicroservicesTree
from utils.file_utils import load_environment, setup_sentence_transformer
import logging
logger = logging.getLogger(__name__) 

if __name__ == "__main__":
    load_environment()  # Load env variables at initialization
    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        filename="src/logs/microservices_tree.log"
    )

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
    target_repository = "/home/ulises/Documents/UniTn/2nd Year/2 semester/Tirocinio/microservices-demo/src/"
    treebuilder = MicroservicesTree(
        target_repository,
        embeddings_engine,
        secret_classifier,
        service_classifier,
        label_classifier,
    )
    
    repository_tree = treebuilder.build()
    treebuilder.print_tree(repository_tree)