import re
from typing import Dict, Any, List
import logging
import re



class InferenceProcessor:
    """Engine for LLM text generation using local models."""

    def __init__(self) -> None:
        """Initialize the language model and tokenizer.

        Args:
            model_name_or_path: Hugging Face model name or local path to model
        """
        self.logger = logging.getLogger(__name__)



   
    def process_response(self, response: List[Any]) -> List[Dict[str, str]]:
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
                    content = getattr(block, "text", None)
                if not content or not isinstance(content, str) or not content.strip():
                    self.logger.warning("Received empty or invalid content block, skipping.")
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