from copy import deepcopy
import logging
import os
from typing import Any, Dict, List, Optional

from numpy import log, vstack
from torch import Tensor
from embeddings.embeddings_engine import EmbeddingsEngine
from utils.file_utils import load_json_file


class ServiceClassifier:
    def __init__(self, embeddings_engine: EmbeddingsEngine) -> None:
        """Initialize the ServiceClassifier with an embeddings engine."""
        self.logger = logging.getLogger(__name__)
        self._engine: EmbeddingsEngine = embeddings_engine

        # Load the services knowledge base
        self._services = self._load_services(
            os.environ.get(
                "MICROSERVICES_PATH",
                "src/resources/knowledge_base/microservices.json",
            )
        )

    @property
    def services(self) -> List[Dict[str, Any]]:
        """Get the services knowledge base."""
        return self._services

    def calculate_threshold(self, embeddings_size) -> float:
        # Calculate the threshold for the microservices embeddings
        self._microservices_threshold: float = 0.8 - (
            (log(embeddings_size) / embeddings_size) * 0.1
        )

        # Ensure threshold is between 0.1 and 0.9
        return max(0.1, min(self._microservices_threshold, 0.9))

    def _load_services(self, path: str) -> List[Dict[str, Any]]:
        """Push embeddings to services knowledge base."""
        services: Dict[str, List[Dict[str, Any]]] = load_json_file(path)

        for service in services["services"]:
            # Add the microservice label to the keywords list
            if service["name"] not in service["keywords"]:
                service["keywords"] = service["keywords"] + [service["name"]]

            embeddings_list: List[Tensor] = []

            # Compute the embedding for the keywords
            for keyword in service["keywords"]:
                # Compute embedding for each individual value in the array
                embedding = self._engine.encode(keyword)
                embeddings_list.append(embedding)

            service["embeddings"] = vstack(
                embeddings_list
            )  # Stack vertically into one array

        return services["services"]

    def decide_service(
        self,
        query: str,
        ports: Optional[List[int]] = None,
        threshold: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Decide the service based on the query and a given threshold."""
        self.logger.info(f"Deciding service for query: {query} with ports: {ports}")
        # Compute the embedding for the query
        query_embedding: Tensor = self._engine.encode(query)    
        threshold = threshold or self.calculate_threshold(len(query_embedding))
        most_similar: Optional[Dict[str, Any]] = None
        max_similarity: float = -1.0

        # Iterate through the dictionary
        for service in self._services:
            similarity: float = self._engine.compute_similarity(
                query_embedding, service["embeddings"]
            )
            if ports and len(service["ports"]) > 0:
                for port in ports:
                    if port in service["ports"]:
                        similarity += 0.1
            # Check if the similarity is greater than the threshold
            if similarity > max_similarity and similarity >= threshold:
                most_similar = service
                max_similarity = similarity

        most_similar = deepcopy(most_similar)
        if most_similar:
            most_similar.pop("embeddings", None)  #  Remove embeddings from the result
        # Check if the most similar service is above the threshold
        self.logger.debug(""f"Most similar service: {most_similar}")
        return most_similar
