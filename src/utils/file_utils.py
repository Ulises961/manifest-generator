import gc
import json
import os
import re
import time
from typing import Any, List, Optional, cast, Tuple
import torch
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import shlex
from transformers import AutoModelForCausalLM, AutoTokenizer
import logging
from transformers import BitsAndBytesConfig

logger = logging.getLogger(__name__)


def load_file(path: str) -> Any:
    """Load a JSON file."""
    with open(path, "r") as file:
        return json.load(file)


def remove_none_values(d):
    """Recursively remove all None values from dictionary"""
    if not isinstance(d, dict):
        return d

    if d == {} or d == []:
        return None

    for key, value in d.items():
        if isinstance(value, dict) and value != {}:
            d[key] = remove_none_values(value)
        elif isinstance(value, list) and value != []:
            d[key] = [remove_none_values(item) for item in value if item is not None]
        elif isinstance(value, str):
            if value == "" or value == " " or value is None:
                d[key] = None
            d[key] = value.strip()

    return {
        key: value
        for key, value in d.items()
        if value is not None and value != {} and value != []
    }


def load_environment():
    """Load environment variables from .env file."""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    load_dotenv(env_path)


def _get_model_paths(model_env_var: str, default_model: str) -> Tuple[str, str]:
    """Get model name and path from environment variables."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.realpath(
        os.path.join(current_dir, "..", "resources", "models")
    )
    model_name: str = os.getenv(model_env_var, default_model)
    model_path = os.path.join(models_dir, model_name)
    return model_name, model_path


def setup_cuda(force_cpu: bool = False) -> str:
    """Setup CUDA for PyTorch."""
    device = "cpu" if force_cpu else ("cuda" if torch.cuda.is_available() else "cpu")

    if device == "cuda":
        logger.info("CUDA is available. Using GPU for inference.")
        torch.backends.cudnn.benchmark = True
        torch.backends.cuda.matmul.allow_tf32 = True

    else:
        logger.info("CUDA is not available. Using CPU for inference.")

    return device


def setup_sentence_transformer(force_cpu: bool = False) -> Any:
    """Setup and return a SentenceTransformer model."""
    model_name, model_path = _get_model_paths("EMBEDDINGS_MODEL", "all-MiniLM-L6-v2")

    device = setup_cuda(force_cpu)

    if os.path.exists(model_path):
        return SentenceTransformer(model_name_or_path=model_path, device=device)  # type: ignore

    os.makedirs(model_path, exist_ok=True)

    model = SentenceTransformer(model_name_or_path=model_name, device=device)  # type: ignore
    model.save(model_path)

    return model


def setup_inference_models(force_cpu: bool = False) -> Tuple[Any, Any, str]:
    """Setup and return a AutoModelForCausalLM model and tokenizer."""

    device = setup_cuda(force_cpu)

    # Check if in development or production mode
    is_dev_mode = os.getenv("DEV_MODE", "true").lower() == "true"

    if is_dev_mode:
        # Development mode - use smaller model with quantization
        model_name, model_path = _get_model_paths(
            "INFERENCE_MODEL", "microsoft/phi-1.5"
        )
        logger.info("Running in DEVELOPMENT mode with smaller model: %s", model_name)

        # Use 8-bit quantization to reduce memory footprint
        quantization_config = BitsAndBytesConfig(
            load_in_8bit=True,
            llm_int8_threshold=6.0,
            llm_int8_has_fp16_weight=True,  
        )

    else:
        # Production mode - use full-size model
        model_name, model_path = _get_model_paths(
            "PRODUCTION_INFERENCE_MODEL",     "deepseek-ai/deepseek-coder-33b-instruct",
        )
        logger.info("Running in PRODUCTION mode with model: %s", model_name)
        quantization_config = None

    try:
        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            device_map=device,
            quantization_config=quantization_config if is_dev_mode else None,
            torch_dtype=torch.float16,
            low_cpu_mem_usage=True,
        )

        model.eval()

        tokenizer = AutoTokenizer.from_pretrained(model_name)

        if not os.path.exists(model_path):
            model.save_pretrained(model_path)

        return model, tokenizer, device
    except Exception as e:
        logger.error(f"Failed to load model {model_name}: {e}")

        # Run the model in cpu instead of gpu
        if is_dev_mode:
            logger.info(f"Falling back to cpu device")
            return (
                AutoModelForCausalLM.from_pretrained(model_name, device_map="cpu"),
                AutoTokenizer.from_pretrained(model_name, device_map="cpu"),
                "cpu",
            )
        else:
            # In production, we want to fail rather than use an inadequate model
            raise RuntimeError(f"Failed to load production model: {model_name}")


def normalize_command_field(field: Optional[str | List[str]]) -> List[str]:
    """Normalize Docker CMD/ENTRYPOINT field into list."""
    if not field:
        return []

    if isinstance(field, list):
        return ["/bin/sh -c"] + field if check_shell_in_commands(field) else field

    if isinstance(field, str):
        field = field.strip()

        if field.startswith("[") and field.endswith("]"):
            try:
                commands = cast(list, json.loads(field))
                return (
                    ["/bin/sh -c", field]
                    if check_shell_in_commands(commands)
                    else commands
                )
            except json.JSONDecodeError:
                print("failed deserializing", field)
                return []

        # Raw string command: detect shell logic
        return (
            ["/bin/sh -c", field] if needs_shell_parsing(field) else shlex.split(field)
        )

    return []


def needs_shell_parsing(command: str) -> bool:
    """Return True if command string likely needs to be run under a shell."""
    shell_pattern = re.compile(
        r"\$|\&\&|\|\||[|;&><*]|2>|&>|-c\b|(?<!(\w)\.)(?:bash|zsh|fish|tcsh|csh|ksh|dash|sh)\b"
    )
    return bool(shell_pattern.search(command))


def check_shell_in_commands(commands: List[str]) -> bool:
    for word in commands:
        if needs_shell_parsing(word):
            return True
    return False
