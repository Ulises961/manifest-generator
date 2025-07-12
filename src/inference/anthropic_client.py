import logging
import re
from typing import Dict, List, cast, Any
from llm_client import LLMClient
from anthropic import Anthropic


class AnthropicClient(LLMClient):
    def __init__(self, model_name: str = "claude-3-5-haiku-latest"):
        super().__init__(Anthropic())
        self.model_name = model_name
        self.client: Anthropic = cast(Anthropic, super().client)
        self.logger = logging.getLogger(__name__)

    def chat(self, messages: List[Dict[str, Any]], system_prompt=None) -> Any:
        response = self.client.messages.create(
            model="claude-3-5-haiku-latest",
            max_tokens=3000,
            temperature=0,
            system=system_prompt,  # type: ignore
            messages=messages,  # type: ignore
        )
        return response

    def generate_named_manifests(self, response: List[Any]) -> List[Dict[str, str]]:
        """
        Process the model's response from Anthropic API (list of TextBlock or YAML strings).
        Returns a list of dicts with 'name' and 'manifest' (YAML string, indentation preserved).
        """
        named_manifests: List[Dict[str, str]] = []

        for block in response:
            # Accept either a string or an object with .text
            if isinstance(block, str):
                content = block
            else:
                content = getattr(block, "text", None) # type: ignore
            if not content or not isinstance(content, str) or not content.strip():
                self.logger.warning(
                    "Received empty or invalid content block, skipping."
                )
                continue

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
