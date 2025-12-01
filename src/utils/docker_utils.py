import shlex
from typing import List


def parse_key_value_string(raw: str) -> dict:
    """Parse a string of key=value pairs into a dictionary."""
    tokens = normalize_command_field(raw)
    result = {}
    for token in tokens:
        if "=" in token:
            key, value = token.split("=", 1)
            result[key] = value
    return result

def normalize_spaced_values(raw:str) -> List[str]:
    """Normalize a space-separated string into a list of values."""
    return shlex.split(raw)
    

def normalize_multiline(raw: str) -> str:
    """Joins Dockerfile lines with trailing backslashes into one line."""
    return raw.replace("\\\n", " ").replace("\\\r\n", " ")  # handle both \n and \r\n

def normalize_command_field(raw: str) -> List[str]:
    """Normalize a command field by handling multiline and spaced values."""
    parsed = normalize_multiline(raw)
    return normalize_spaced_values(parsed)