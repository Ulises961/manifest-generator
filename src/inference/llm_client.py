from typing import Any, Dict, List, Optional


class LLMClient:
    def __init__(self, client: Optional[object] = None):
        self.client = client

    def chat(self, messages: List[Dict[str, str]], system_prompt: Optional[List[Dict[str, Any]]] = None) -> Any:
        """Send a list of chat messages and return the assistant's reply."""
        raise NotImplementedError
    
    def pre_process_response(self, response: Any) -> List[Any]:
        """Process the model's response and return a list of named manifests."""
        raise NotImplementedError
    
    def process_response(self, response: Any) -> List[Dict[str, Any]]:
        """Process the model's response and return a list of named manifests."""
        raise NotImplementedError