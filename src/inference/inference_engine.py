import re
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
from typing import Dict, Any, List, Optional
import logging

from embeddings.embeddings_engine import EmbeddingsEngine

class InferenceEngine:
    """Engine for LLM text generation using local models."""

    def __init__(self, model: AutoModelForCausalLM, tokenizer: AutoTokenizer, device: str="cpu", embeddings_engine: EmbeddingsEngine) -> None:
        """Initialize the language model and tokenizer.

        Args:
            model_name_or_path: Hugging Face model name or local path to model
        """
        self.logger = logging.getLogger(__name__)
        self._model = model
        self._tokenizer = tokenizer
        self.device = device
        self.embeddings_engine = embeddings_engine

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
            "eos_token_id": self.tokenizer.eos_token_id,
            "pad_token_id": self.tokenizer.pad_token_id or self.tokenizer.eos_token_id,
        }

        config = {**default_config, **(generation_config or {})}

        inputs = self._tokenizer(prompt, return_tensors="pt").to(self.device)
        self.logger.info(f"Input tokens: {len(inputs.input_ids[0])}")
        
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
        manifests = [manifest.strip() for manifest in manifests]
        named_manifests: List[Dict[str, Any]] = []
        for manifest in manifests:
            res = re.search(r"^[kK]ind:\s*(.*)$", manifest, re.MULTILINE)
            if res:
                name = res.group(1).strip()
            else:
                name = "default"
            
            named_manifest = {
                "name": name,
                "manifest": manifest,
            }
            named_manifests.append(named_manifest)
        return named_manifests
