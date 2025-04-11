import json


def load_file(path: str) -> dict:
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
           
        
        return {key: value for key, value in d.items() if value is not None and value != {} and value != []}