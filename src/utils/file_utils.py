import json
import os
import re
from typing import Any, List, Optional, cast
import torch
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
import shlex
from io import StringIO


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
            if value == "":
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


def setup_sentence_transformer(force_cpu: bool = False) -> Any:
    """Setup and return a SentenceTransformer model."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    models_dir = os.path.realpath(
        os.path.join(current_dir, "..", "resources", "models")
    )
    model_name: str = os.getenv("EMBEDDINGS_MODEL", "all-MiniLM-L6-v2")
    model_path = os.path.join(models_dir, model_name)

    # Check CUDA availability
    device = "cpu" if force_cpu else ("cuda" if torch.cuda.is_available() else "cpu")

    if device == "cuda":
        torch.backends.cudnn.benchmark = True
        torch.backends.cuda.matmul.allow_tf32 = True

    # First try loading from local path
    if os.path.exists(model_path):
        return SentenceTransformer(model_name_or_path=model_path, device=device)  # type: ignore

    # Download and save if not found locally
    os.makedirs(model_path, exist_ok=True)
    model = SentenceTransformer(model_name_or_path=model_name, device=device)  # type: ignore
    model.save(model_path)

    return model


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
