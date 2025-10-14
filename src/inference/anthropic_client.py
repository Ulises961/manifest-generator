import logging
import os
import re
from typing import Dict, List, cast, Any
from inference.llm_client import LLMClient
from anthropic import Anthropic


class AnthropicClient(LLMClient):
    def __init__(self):
        super().__init__(Anthropic())
        self.model_name = os.getenv("LLM_MODEL", "claude-3-5-haiku-latest")
        self.client: Anthropic  # Type annotation for clarity
        self.logger = logging.getLogger(__name__)

    def chat(self, messages: List[Dict[str, Any]], system_prompt=None) -> Any:
        # Prepare the request parameters
        request_params = {
            "model":self.model_name,
            "max_tokens": 3000,
            "temperature": 0,
            "messages": messages,
        }

        # Only add system parameter if system_prompt is provided and not None
        if system_prompt is not None:
            request_params["system"] = system_prompt

        response = self.client.messages.create(**request_params)
        return response

    def generate_named_manifests(self, response: List[Any]) -> List[Dict[str, Any]]:
        """
        Process the model's response from Anthropic API (list of TextBlock or YAML strings).
        Returns a list of dicts with 'name' and 'manifest' (YAML string, indentation preserved).
        """
        named_manifests: List[Dict[str, Any]] = []

        for content in response:
            # Split on YAML document separator
            manifests = content.split("---")
            manifest_number = 0

            for manifest in manifests:
                manifest = manifest.strip()
                if not manifest:
                    continue
                # Try to extract the kind as the name
                res = re.search(r"^[kK]ind:\s*(.*)$", manifest, re.MULTILINE)
                if res:
                    name = res.group(1).strip()
                else:
                    name = "default-" + str(manifest_number)

                manifest_number += 1
                named_manifest = {
                    "name": name,
                    "manifest": manifest,  # preserve indentation
                }

                named_manifests.append(named_manifest)
                self.logger.debug(f"Post processed manifest {named_manifest}")
        return named_manifests

    def pre_process_response(self, response: Any) -> List[str]:
        """
        Process the model's response and return a list of named manifests.
        This method is a wrapper around generate_named_manifests for compatibility.
        """
        result: List[str] = []
        for block in response:
            text = getattr(block, "text", None)  # type: ignore
            text = self.clean_response(text) if text else None

            if not text or not isinstance(text, str) or not text.strip():
                self.logger.warning(
                    f"Received empty or invalid text block. Details:\nType: {type(text)}\nValue: {text}.\nSkipping."
                )
                continue

            result.append(text)
        return result

    def process_response(self, response: Any) -> List[Dict[str, str]]:
        """
        Process the model's response and return a list of named manifests.
        This method is a wrapper around pre_process_response for compatibility.
        """
        response = self.pre_process_response(response)
        if isinstance(response, list):
            return self.generate_named_manifests(response)
        else:
            return []

    def clean_response(self, response: str) -> str:
        """
        Clean the response from the model by removing leading and trailing whitespace.
        This is useful for ensuring the response is properly formatted.
        """
        response = response.strip()
        # Remove pre and post text that is not part of the YAML
        response = re.sub(r"^.*?```yaml", "", response, flags=re.DOTALL)
        response = re.sub(r"```.*?$", "", response, flags=re.DOTALL)
        return response.strip()
