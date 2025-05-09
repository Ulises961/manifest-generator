from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
from typing import Dict, Any, List, Optional
import logging

class InferenceEngine:
    """Engine for LLM text generation using local models."""

    def __init__(
        self,
        model: AutoModelForCausalLM,
        tokenizer: AutoTokenizer
    ) -> None:
        """Initialize the language model and tokenizer.

        Args:
            model_name_or_path: Hugging Face model name or local path to model
        """
        self.logger = logging.getLogger(__name__)
        self._model = model
        self._tokenizer = tokenizer
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


    @property
    def model(self) -> AutoModelForCausalLM:
        """Get the underlying model."""
        return self._model

    @property
    def tokenizer(self) -> AutoTokenizer:
        """Get the underlying tokenizer."""
        return self._tokenizer

    def generate(
        self, prompt: str, generation_config: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Generate text response based on prompt.

        Args:
            prompt: Input text/prompt to generate from
            generation_config: Configuration for text generation

        Returns:
            str: Generated text response
        """
        default_config = {
            "max_new_tokens": 1024,
            "temperature": 0.7,
            "top_p": 0.9,
            "do_sample": True,
        }

        config = {**default_config, **(generation_config or {})}

        inputs = self._tokenizer(prompt, return_tensors="pt").to(self.device)

        with torch.no_grad():
            output = self._model.generate(**inputs, **config)

        return self._tokenizer.decode(
            output[0][inputs.input_ids.shape[1] :], skip_special_tokens=True
        )

    def process_response(self, response: str) -> List[Dict[str, str]]:
        """Process the model's response.

        Args:
            response: Raw response from the model

        Returns:
            str: Processed response
        """
        self.logger.info(f"Processing response {response}")
        response.strip()
        manifests = response.split("---")
        manifests = [manifest.strip() for manifest in manifests if manifest.strip()]
        named_manifests = []
        for manifest in manifests:
            first_line = manifest.split("\n")[0]
            if first_line.startswith("#"): # It's the name of the object, use it as the name for the manifest
                first_line = first_line.split("#")[1].strip()           
            named_manifests.append({"name":first_line, "manifest": manifest.replace(first_line, "").strip()})
        return named_manifests

            