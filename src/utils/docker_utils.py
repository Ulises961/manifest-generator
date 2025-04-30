import shlex
from typing import List


def parse_key_value_string(raw: str) -> dict:
    tokens = normalize_command_field(raw)
    result = {}
    for token in tokens:
        if "=" in token:
            key, value = token.split("=", 1)
            result[key] = value
    return result

def normalize_spaced_values(raw:str) -> List[str]:
    return shlex.split(raw)
    

def normalize_multiline(raw: str) -> str:
    """Joins Dockerfile lines with trailing backslashes into one line."""
    return raw.replace("\\\n", " ").replace("\\\r\n", " ")  # handle both \n and \r\n

def normalize_command_field(raw: str) -> List[str]:
    parsed = normalize_multiline(raw)
    return normalize_spaced_values(parsed)