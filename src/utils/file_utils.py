import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple, cast
from dotenv import load_dotenv
import shlex
import logging
from sentence_transformers import SentenceTransformer
import torch
import yaml

logger = logging.getLogger(__name__)


def load_json_file(path: str) -> Any:
    """Load a JSON file."""
    with open(path, "r") as file:
        return json.load(file)
    
def load_yaml_file(path: str) -> dict:
    """Load a YAML file."""
    with open(path, "r") as file:
        return yaml.safe_load(file)
    
def _get_model_paths(model_env_var: str, default_model: str) -> Tuple[str, str]:
    """Get model name and path from environment variables."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.realpath(
        os.path.join(current_dir, "..", "resources", "models")
    )
    model_name: str = os.getenv(model_env_var, default_model)
    model_path = os.path.join(models_dir, model_name)
    return model_name, model_path


def remove_none_values(d) -> Optional[Dict[str, Any]] | Any:
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
        if value is not None and value != {} and value != [] and value != [None]
    }


def load_environment():
    """Load environment variables from .env file."""
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    load_dotenv(env_path)



def normalize_command_field(field: Optional[str | List[str]]) -> List[str]:
    """Normalize Docker CMD/ENTRYPOINT field into list."""
    if not field:
        return []

    if isinstance(field, list):
        return ["/bin/sh", "-c"] + field if check_shell_in_commands(field) else field

    if isinstance(field, str):
        field = field.strip()

        if field.startswith("[") and field.endswith("]"):
            try:
                commands = cast(list, json.loads(field))
                return (
                    ["/bin/sh", "-c", field]
                    if check_shell_in_commands(commands)
                    else commands
                )
            except json.JSONDecodeError:
                logger.debug("failed deserializing", field)
                return []

        # Raw string command: detect shell logic
        return (
            ["/bin/sh", "-c", field] if needs_shell_parsing(field) else shlex.split(field)
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
    model.save(model_path) # type: ignore

    return model



