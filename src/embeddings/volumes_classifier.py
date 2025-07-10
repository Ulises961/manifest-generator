import os
from typing import List


class VolumesClassifier:
    def __init__(self):
        self.volumes = self.load_volumes()

    def load_volumes(self) -> List[str]:
        volumes_path = os.path.join(
            os.path.dirname(__file__),
            "..",
            os.getenv("LABELS_PATH", "resources/knowledge_base/volumes.json")
        )
        """Load volumes from a JSON file."""
        if not os.path.exists(volumes_path):
            raise FileNotFoundError(f"Volumes file not found at {volumes_path}")
        with open(volumes_path, "r") as file:
            volumes_data = file.read()
        return [volume.strip() for volume in volumes_data.splitlines() if volume.strip()]
        
    def decide_volume_persistence(self, volume_path: str) -> bool:
        """Classify volumes based on their type."""
        return volume_path in self.volumes
