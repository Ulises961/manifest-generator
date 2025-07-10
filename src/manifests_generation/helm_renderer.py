import subprocess
import os
from typing import Any, Dict, List
import logging


class HelmRenderer:
    def __init__(self):
        self.values_path = os.path.join(
            os.getenv("TARGET_PATH", "target"),
            os.getenv("HELM_CHARTS_PATH", "helm_charts"),
            os.getenv("VALUES_PATH", "values.yaml")
        )
        self.logger = logging.getLogger(__name__)

    def render(
        self, chart_path: str, namespace: str = "default", release_name: str = "my-release"
    ) -> str:
        # This is a placeholder for the actual Helm rendering logic.
        # In a real implementation, you would call the Helm CLI or use a library to render the chart.
        cmd = [
            "helm",
            "template",
            release_name,
            chart_path,
            "--namespace",
            namespace,
            "--values",
            self.values_path,
        ]

        try:
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True)
            return output
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Helm template failed: {e.output}")

