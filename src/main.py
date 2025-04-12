import json
import os
from sentence_transformers import SentenceTransformer
from embeddings.embeddings_engine import EmbeddingsEngine
from embeddings.label_classifier import LabelClassifier
from embeddings.secret_classifier import SecretClassifier
from embeddings.service_classifier import ServiceClassifier
from tree.microservices_tree import MicroservicesTree


if __name__ == "__main__":

    # Load the SentenceTransformer model
    model: SentenceTransformer = SentenceTransformer(
        os.getenv("EMBEDDINGS_MODEL", "all-MiniLM-L6-v2")
    )

    # Load the embeddings engine
    embeddings_engine = EmbeddingsEngine(model)
    # Load the secret classifier
    secret_classifier = SecretClassifier(embeddings_engine)
    # Load the service classifier
    service_classifier = ServiceClassifier(embeddings_engine)
    # Load the label classifier
    label_classifier = LabelClassifier(embeddings_engine)
    # Generate a tree with the microservices detected in the repository
    treebuilder = MicroservicesTree(
        os.path.dirname(__file__),
        embeddings_engine,
        secret_classifier,
        service_classifier,
        label_classifier,
    )
    
    repository_tree = treebuilder.build()
