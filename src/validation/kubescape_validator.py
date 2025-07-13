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

    def validate_file(self, manifest_path: str, timeout: int = 300) -> Dict[str, Any]:
        """
        Validates a Kubernetes manifest file using Kubescape.

        Args:
            manifest_path (str): Path to the Kubernetes manifest file.
            timeout (int): Maximum time to wait for kubescape to complete (seconds).

        Returns:
            Dict[str, Any]: Validation metrics and results.
        """
        command = [
            self.kubescape_path,
            "scan",
            "framework",
            "all",
            "--format",
            "json",
            manifest_path,
        ]

        try:
            # subprocess.run() is synchronous and waits for completion
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,  # Don't raise exception on non-zero return code
            )
        except subprocess.TimeoutExpired as e:
            self.logger.error(
                f"Kubescape scan timed out after {timeout} seconds for {manifest_path}"
            )
            raise RuntimeError(
                f"Kubescape scan timed out after {timeout} seconds"
            ) from e
        except FileNotFoundError as e:
            self.logger.error(f"Kubescape binary not found at {self.kubescape_path}")
            raise RuntimeError(
                f"Kubescape binary not found at {self.kubescape_path}"
            ) from e

        if result.returncode != 0:
            self.logger.error(
                f"Kubescape scan failed for {manifest_path}: {result.stderr}"
            )
            raise RuntimeError(f"Kubescape scan failed: {result.stderr}")

        try:
            report = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            self.logger.error(
                f"Failed to parse Kubescape output as JSON: {result.stdout[:200]}..."
            )
            raise RuntimeError(f"Failed to parse Kubescape output as JSON") from e

        summary = report.get("summaryDetails", {})
        controls_dict = summary.get("controls", {})
        report_results = report.get("results", [])

        metrics = {
            "file": manifest_path,
            "compliance_score": summary.get("complianceScore", 0),
            "total_controls": len(controls_dict),
            "failed_controls": [],
            "severity_counts": {
                "critical": summary.get("controlsSeverityCounters", 0).get(
                    "criticalSeverity", 0
                ),
                "high": summary.get("controlsSeverityCounters", 0).get(
                    "highSeverity", 0
                ),
                "medium": summary.get("controlsSeverityCounters", 0).get(
                    "mediumSeverity", 0
                ),
                "low": summary.get("controlsSeverityCounters", 0).get("lowSeverity", 0),
            },
        }

        for result in report_results:
            controls = result.get("controls", [])
            for control in controls:
                # Skip controls that don't have complete data
                if not control.get("status") or not control.get("name"):
                    continue

                if control.get("status", {}).get("status", "Unknown") == "failed":
                    suggested_remediation = self._get_suggested_remediation(control)
                    metrics["failed_controls"].append(
                        {
                            "name": control.get("name", "Unknown"),
                            "id": control.get("controlID", "Unknown"),
                            "suggested_remediation": suggested_remediation,
                        }
                    )
        
        self.logger.debug(
            f"Validation metrics for {manifest_path}: {metrics}"
        )
        
        return metrics

    def _get_suggested_remediation(self, control: Dict[str, Any]) -> List[Dict]:
        """Extract suggested remediation from control details."""
        rules = control.get("rules", {})
        if not rules:
            return []
        remediation: List[Dict[str, str]] = []
        for rule in rules:
            paths = rule.get("paths", [])
            for path in paths:
                remediation.append(path.get("fixPath", {}))
        return remediation

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
