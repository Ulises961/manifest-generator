import logging
import os
from typing import Any, Dict, List, Optional, cast
import requests


class EmbeddingsClient:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.logger = logging.getLogger(__name__)
        self.api_url = os.getenv("EMBEDDINGS_ENDPOINT","http://localhost:8000/v1")
        self.headers = {"Content-Type": "application/json"}

    def request_classification(
        self, payload: Dict[str, Any], endpoint: str
    ) -> Optional[Dict[str, Any]]:
        """Request classification of a text using the embeddings model."""
        try:
            response = requests.post(
                f"{self.api_url}/{endpoint}",
                json=payload,
                headers=self.headers,
            )
            response.raise_for_status()
            result = response.json()

            return cast(Dict[str,Any], result)

        except requests.RequestException as e:
            self.logger.error(f"Error classifying text '{payload}': {e}")
            return None

    def get_similarity(self, text1: str, text2: str) -> Optional[Dict[str, Any]]:
        """Compare two texts using the embeddings model."""
        payload = {"text1": text1, "text2": text2}
        self.logger.debug(f"Comparing '{text1}' with '{text2}'")
        return self.request_classification(payload, endpoint="similarity/compare")

    def decide_secret(self, secret: str) -> Optional[Dict[str, Any]]:
        """Classify a secret using the embeddings model."""
        payload = {"content": secret}
        self.logger.debug(f"Classifying secret: {secret}")
        return self.request_classification(payload, endpoint="decide/secret")

    def classify_label(self, label: str) -> Optional[Dict[str, Any]]:
        """Classify a label using the embeddings model."""
        payload = {"content": label}
        self.logger.debug(f"Classifying label: {label}")
        return self.request_classification(payload, endpoint="classify/label")

    def classify_service(
        self,
        service: str,
        ports: Optional[List[int]],
        threshold: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Classify a service using the embeddings model."""
        payload = {"content": {"service": service, "ports": ports}, "threshold": threshold}
        self.logger.debug(f"Classifying service: {service}")
        return self.request_classification(payload, endpoint="classify/service")

    def decide_volume(
        self, volume: str
    ) -> Optional[Dict[str, Any]]:
        """Decide if a volume is persistent using the embeddings model."""
        payload = {"content":  volume}
        self.logger.debug(f"Deciding volume: {volume}")
        return self.request_classification(payload, endpoint="decide/volume_persistence")