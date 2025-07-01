import logging
from typing import Any, Dict, List, Optional, cast

from embeddings.embeddings_client import EmbeddingsClient


class ServiceClassifier:
    def __init__(self, embeddings_client: EmbeddingsClient) -> None:
        """Initialize the ServiceClassifier with an embeddings engine."""
        self.logger = logging.getLogger(__name__)
        self.embeddings_client: EmbeddingsClient = embeddings_client

     
    def decide_service(self, query: str, ports: Optional[List[int]] = None) -> Optional[Dict[str, Any]]:
        """Decide the service based on the query and a given threshold."""
        if (result := self.embeddings_client.classify_service(query, ports)) is not None:
            self.logger.info(f"Service classification result: {result}")
            return cast(Dict[str,Any],result.get("classification", None))
        return None
      
