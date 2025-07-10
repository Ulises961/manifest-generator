from typing import Any, Dict
from git import List, Optional


class LLMClient:
    def __init__(self, client: Optional[object] = None):
        self.client = client

    def chat(self, messages: List[Dict[str, str]], system_prompt: Optional[List[Dict[str, Any]]] = None) -> Any:
        """Send a list of chat messages and return the assistant's reply."""
        raise NotImplementedError
