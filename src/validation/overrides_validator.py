import json
from typing import Any, Dict
from jsonschema import validate, ValidationError


class OverridesValidator:
    """
    Validates overrides for the configuration.
    """

    def __init__(self):
        self.schema = self._get_schema()
        

    def _get_schema(self) -> Any:
        with open("src/resources/schemas/overrides_schema.json", "r") as file:
            schema = json.load(file)
        return schema
    
    def validate(self, config: Dict[str,Any] ) -> bool:
        try:
            validate(instance=config, schema=self.schema)
            return True
        except ValidationError as e:
            print(f"Validation error: {e.message}")
            return False
    