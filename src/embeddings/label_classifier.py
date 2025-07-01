from typing import Optional, cast

from embeddings.embeddings_client import EmbeddingsClient


class LabelClassifier:
    def __init__(self, embeddings_client: EmbeddingsClient) -> None:
        self.embeddings_client: EmbeddingsClient = embeddings_client

    def classify_label(
        self,
        label_key,
    ) -> Optional[str]:
        if (result := self.embeddings_client.classify_label(label_key)) is not None:
            return cast(str, result.get("decision", "unknown"))
        else:
            return None
