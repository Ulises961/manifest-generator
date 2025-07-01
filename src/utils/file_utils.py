import json
import os
import re
from typing import Any, Dict, List, Optional, cast
from dotenv import load_dotenv
import shlex
import logging

logger = logging.getLogger(__name__)


def load_file(path: str) -> Any:
    """Load a JSON file."""
    with open(path, "r") as file:
        return json.load(file)


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
        if value is not None and value != {} and value != []
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
