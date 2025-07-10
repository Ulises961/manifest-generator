import csv
import json
import logging
import subprocess
from typing import Any, Dict, List


class KubescapeValidator:
    """
    Validates Kubernetes manifests using Kubescape.
    """

    def __init__(self, kubescape_path: str = "kubescape"):
        """
        Initializes the KubescapeValidator with the path to the Kubescape binary.
        """
        self.kubescape_path = kubescape_path
        self.logger = logging.getLogger(__name__)

    def validate_file(self, manifest_path: str) -> Dict[str, Any]:
        """
        Validates a Kubernetes manifest file using Kubescape.

        Args:
            manifest_path (str): Path to the Kubernetes manifest file.

        Returns:
            bool: True if the manifest is valid, False otherwise.
        """
        command = [
            self.kubescape_path,
            "scan",
            "framework",
            "nsa",
            "--format",
            "json",
            "--file",
            manifest_path,
        ]
        result = subprocess.run(command, capture_output=True, text=True)

        if result.returncode != 0:
            raise RuntimeError(f"Kubescape scan failed: {result.stderr}")

        report = json.loads(result.stdout)

        controls = report.get("controls", [])

        metrics = {
            "file": manifest_path,
            "compliance_score": report.get("summary", {}).get("complianceScore", 0),
            "total_controls": len(controls),
            "failed_controls": [],
            "severity_counts": {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "info": 0,
            },
        }

        for control in controls:
            if control["status"]["status"] == "failed":
                severity = control.get("baseScore", "unknown").lower()
                severity = (
                    severity if severity in metrics["severity_counts"] else "info"
                )
                metrics["severity_counts"][severity] += 1

                metrics["failed_controls"].append(
                    {
                        "name": control["name"],
                        "description": control["description"],
                        "severity": severity,
                        "id": control["controlID"],
                    }
                )

        return metrics

    def save_metrics_to_csv(
        self, metrics_list: List[Dict], output_file: str = "scan_results.csv"
    ):
        fieldnames = [
            "file",
            "compliance_score",
            "critical",
            "high",
            "medium",
            "low",
            "info",
            "total_controls",
            "failed_count",
        ]

        with open(output_file, mode="w", newline="") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
            writer.writeheader()

            for m in metrics_list:
                row = {
                    "file": m["file"],
                    "compliance_score": m["compliance_score"],
                    "critical": m["severity_counts"]["critical"],
                    "high": m["severity_counts"]["high"],
                    "medium": m["severity_counts"]["medium"],
                    "low": m["severity_counts"]["low"],
                    "info": m["severity_counts"]["info"],
                    "total_controls": m["total_controls"],
                    "failed_count": len(m["failed_controls"]),
                }
                writer.writerow(row)
