import os
from typing import Dict

from numpy import ndarray
from embeddings.embeddings_engine import EmbeddingsEngine
from utils.file_utils import load_file


class LabelClassifier:
    def __init__(self, embeddings_engine: EmbeddingsEngine) -> None:
        self._engine: EmbeddingsEngine = embeddings_engine
        self._label_embeddings: Dict[str, Dict[str, ndarray]] = self._encode_labels()

    def classify_label(self, label_key, threshold=0.8) -> str | None:
        key_embedding = self._engine.encode_word(label_key)

        # Compute cosine similarity with known labels
        label_similarities = {
            k: self._engine.compute_similarity(key_embedding, v) for k, v in self._label_embeddings['labels'].items()
        }
        annotation_similarities = {
            k: self._engine.compute_similarity(key_embedding, v) for k, v in self._label_embeddings['annotations'].items()
        }

        label_similarities = {
            k: v for k, v in label_similarities.items() if v >= threshold
        }

        annotation_similarities = {
            k: v for k, v in annotation_similarities.items() if v >= threshold
        }

        # Find best match
        best_label = max(label_similarities)
        best_annotation = max(annotation_similarities)

    
        # Choose based on highest similarity
        if best_label != None and best_annotation != None:
            if best_label > best_annotation:
                return "label"
            else:
                return "annotation"

        elif best_label != None:
            return "label"

        else:
            return "annotation"
    
    def _encode_labels(self) -> Dict[str, Dict[str, ndarray]]:
        """Encode labels using the SentenceTransformer model."""

        labels_path = os.path.join(
            os.path.dirname(__file__),
            os.getenv("LABELS_PATH", "resources/docker_labels.json"),
        )
        
        labels: Dict[str, Dict[str, str]] = load_file(labels_path)

        return {
            category_name: {label: self._engine.encode_word(label) for label in label_dict.keys()}
            for category_name, label_dict in labels.items()
        }