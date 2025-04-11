import json
import os
from sentence_transformers import SentenceTransformer
from tree.microservices_tree import MicroservicesTree


if __name__ == "__main__":
    
    # Load the SentenceTransformer model
    model:SentenceTransformer = SentenceTransformer(os.getenv("EMBEDDINGS_MODEL", "all-MiniLM-L6-v2"))

    # Generate a tree with the microservices detected in the repository
    treebuilder = MicroservicesTree(os.path.dirname(__file__), model)
    lest = treebuilder.build()
