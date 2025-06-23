import re
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
from typing import Dict, Any, List, Optional
import logging
from embeddings.embeddings_engine import EmbeddingsEngine
import re
import yaml
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from kubernetes.client import ApiClient

from embeddings.embeddings_engine import EmbeddingsEngine

class InferenceEngine:
    """Engine for LLM text generation using local models."""

    def __init__(self, model: AutoModelForCausalLM, tokenizer: AutoTokenizer,  embeddings_engine: EmbeddingsEngine, device: str="cpu") -> None:
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
            "num_beams": 5,
            "early_stopping": True,
            "max_new_tokens": 3000,
            "do_sample": False,
            "eos_token_id": self.tokenizer.eos_token_id,
            "pad_token_id": self.tokenizer.pad_token_id or self.tokenizer.eos_token_id,
            "temperature": None,
            "top_p": None
        }

        config = {**default_config, **(generation_config or {})}
      
        inputs = self._tokenizer(prompt, return_tensors="pt").to(self.device)
        self.logger.info(f"Input tokens: {len(inputs.input_ids[0])}")
        
        with torch.no_grad():
            output = self._model.generate(**inputs, **config) # type: ignore

        if self.device == "cuda":
            torch.cuda.synchronize()
            
            decoded = self._tokenizer.decode(
                output[0][inputs.input_ids.shape[1] :], skip_special_tokens=True
            )
            self.logger.info(f"Generated output: {decoded}")
            return decoded
    
    def process_response(self, response: str) -> List[Dict[str, str]]:
        """Process the model's response.

        Args:
            response: Raw response from the model

        Returns:
            str: Processed response
        """
        self.logger.info(f"Processing response {response}")
        if response is None or not response.strip():
            self.logger.warning("Empty response received from the model.")
            return []
        # Clean and recover indentation of the YAML manifests
        manifests = self.clean_llm_kubernetes_yaml(response)
        manifests = self.recover_yaml_indentation(manifests)
        manifests = response.split("---")
        manifests = [manifest.strip() for manifest in manifests]
        named_manifests: List[Dict[str, Any]] = []
        manifest_number = 0 
        for manifest in manifests:
            res = re.search(r"^[kK]ind:\s*(.*)$", manifest, re.MULTILINE)
            if res:
                name = res.group(1).strip()
            else:
                name = "default" + "-" + str(manifest_number)
                manifest_number += 1
                
            named_manifest = {
                "name": name,
                "manifest": manifest,
            }
            named_manifests.append(named_manifest)
        return named_manifests

    def clean_llm_kubernetes_yaml(self, raw_content):
        # Step 1: Extract YAML content from code blocks if present
        yaml_block_pattern = r"```(?:yaml|yml)?\s*([\s\S]*?)```"
        code_blocks = re.findall(yaml_block_pattern, raw_content)
        
        if code_blocks:
            # Use the first code block or concatenate multiple blocks if needed
            content = code_blocks[0]
        else:
            # Assume the whole content is YAML but remove obvious non-YAML parts
            content = raw_content
        
        # Step 2: Remove conversation artifacts, comments that look like explanations
        explanations_pattern = r"(?:^|\n)(?!#\s*\w+:)#.*(?:\n|$)"
        content = re.sub(explanations_pattern, "\n", content)
        
        # Step 3: Remove leading/trailing conversation text
        content = re.sub(r"^.*?(?=apiVersion|kind|metadata)", "", content, flags=re.DOTALL)
        content = re.sub(r"(?<=\n\n).*$", "", content, flags=re.DOTALL)
        
        # Step 4: Normalize document separators
        content = re.sub(r"---\s*\n\s*---", "---", content)
        
        # Step 5: Validate YAML syntax
        try:
            docs = list(yaml.safe_load_all(content))
            # Reconstruct valid YAML
            return "\n---\n".join(yaml.dump(doc) for doc in docs)
        except yaml.YAMLError as e:
            print(f"YAML validation error: {e}")
            return content  # Return original cleaned content if YAML validation fails
        
    def fix_kubernetes_yaml_indentation(self, unindented_yaml_str):
        try:
            # Parse the YAML string
            yaml_objects = list(yaml.safe_load_all(unindented_yaml_str))
            
            # Initialize Kubernetes API client (for serialization)
            api_client = ApiClient()
            
            # Process each YAML document
            indented_yamls = []
            for yaml_obj in yaml_objects:
                # Convert to JSON (intermediate step)
                json_data = api_client.sanitize_for_serialization(yaml_obj)
                
                # Convert back to YAML with proper Kubernetes indentation
                indented_yaml = yaml.dump(
                    json_data,
                    default_flow_style=False,
                    indent=2
                )
                indented_yamls.append(indented_yaml)
                
            return "\n---\n".join(indented_yamls)
        except Exception as e:
            print(f"Error processing Kubernetes YAML: {e}")
            return None
        
    def rule_based_indentation(self, unindented_yaml_str):
        lines = unindented_yaml_str.strip().split("\n")
        indented_lines = []
        indent_level = 0
        
        # Common Kubernetes resource structure patterns
        resource_start = re.compile(r"^(apiVersion|kind|metadata):")
        nested_keys = re.compile(r"^(spec|data|annotations|labels|template|containers|volumes|env):")
        list_item = re.compile(r"^- ")
        
        for line in lines:
            stripped = line.strip()
            
            # Skip empty lines
            if not stripped:
                indented_lines.append("")
                continue
                
            # Resource top-level keys reset indent
            if resource_start.match(stripped):
                indent_level = 0
                
            # Nested structural keys increase indent
            elif nested_keys.match(stripped):
                indent_level = min(indent_level + 2, 12)  # Cap at reasonable max
                
            # List items maintain or slightly increase indent
            elif list_item.match(stripped):
                indent_level = min(indent_level + 2, 12)
                
            # Apply indentation
            indented_lines.append(" " * indent_level + stripped)
            
        return "\n".join(indented_lines)

    def recover_yaml_indentation(self, llm_yaml_str):
        try:
            # First try parsing approach
            result = self.fix_kubernetes_yaml_indentation(llm_yaml_str)
            if result:
                return result
        except Exception:
            pass
            
        # Fall back to rule-based approach if parsing fails
        return self.rule_based_indentation(llm_yaml_str)