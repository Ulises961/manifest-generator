import csv
import json
import logging
import os
import subprocess
from typing import Any, Dict, List
import traceback


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
            "nsa,cis-v1.23-t1.0.1",
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
            self.logger.warning(
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

        # Count controls by status
        relevant_controls = 0
        passed_controls = 0
        failed_controls = 0
        irrelevant_controls = 0

        calculated_compliance_score = 100.0  # Default to fully compliant

        # Iterate through Summary controls to count relevant controls
        for control in controls_dict.values():
            if control.get("statusInfo", {}).get("status") == "passed":
                passed_controls += 1
                if control.get("statusInfo", {}).get("subStatus") == "irrelevant":
                    irrelevant_controls += 1
            else:
                failed_controls += 1

        relevant_controls = failed_controls + passed_controls

        # Calculate meaningful compliance score after the loop
        if relevant_controls > 0:
            calculated_compliance_score = (passed_controls / relevant_controls) * 100
           

        metrics = {
            "file": manifest_path,
            "resource_type": self._detect_resource_type(manifest_path),
            "compliance_score": summary.get("complianceScore", calculated_compliance_score),
            "calculated_compliance_score": calculated_compliance_score,
            "total_controls": len(controls_dict),
            "relevant_controls": relevant_controls,
            "irrelevant_controls": irrelevant_controls,
            "passed_controls": passed_controls,
            "failed_controls": failed_controls,
            "failed_controls_details": [],
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
                    metrics["failed_controls_details"].append(
                        {
                            "name": control.get("name", "Unknown"),
                            "id": control.get("controlID", "Unknown"),
                            "suggested_remediation": suggested_remediation,
                        }
                    )

        self.logger.debug(f"Validation metrics for {manifest_path}: {metrics}")

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
        self,
        iteration_metrics: Dict[str, Dict],
        iteration: int,
        output_file: str = "scan_results.csv",
    ):
        """Save validation metrics to CSV file."""

        fieldnames = [
            "iteration",
            "name",
            "file", 
            "resource_type",
            "compliance_score",
            "calculated_compliance_score",
            "relevant_controls",
            "irrelevant_controls",
            "passed_controls",
            "failed_controls",
            "total_controls",
            "critical",
            "high", 
            "medium",
            "low",
            "failed_controls_details",
        ]

        try:
            # Create file with headers if it doesn't exist
            file_exists = os.path.exists(output_file)

            with open(output_file, mode="a", newline="") as csv_file:
                writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

                # Write header only if file is new
                if not file_exists:
                    writer.writeheader()
                    self.logger.info(f"Created new CSV file: {output_file}")

                # Write metrics data
                for metric_name, metrics in iteration_metrics.items():
                    try:
                        row = {
                            "iteration": iteration,
                            "name": metric_name,
                            "file": metrics.get("file", "Unknown"),
                            "resource_type": metrics.get("resource_type", "Unknown"),
                            "compliance_score": metrics.get("compliance_score", 0),
                            "calculated_compliance_score": metrics.get("calculated_compliance_score", 0),
                            "relevant_controls": metrics.get("relevant_controls", 0),
                            "irrelevant_controls": metrics.get("irrelevant_controls", 0),
                            "passed_controls": metrics.get("passed_controls", 0),
                            "failed_controls": metrics.get("failed_controls", 0),
                            "total_controls": metrics.get("total_controls", 0),
                            "critical": metrics.get("severity_counts", {}).get("critical", 0),
                            "high": metrics.get("severity_counts", {}).get("high", 0),
                            "medium": metrics.get("severity_counts", {}).get("medium", 0),
                            "low": metrics.get("severity_counts", {}).get("low", 0),
                            "failed_controls_details": metrics.get("failed_controls_details", []),
                        }

                        writer.writerow(row)

                        self.logger.debug(
                            f"Metrics saved for {metrics.get('file', 'Unknown')} to {output_file}"
                        )

                    except Exception as e:
                        self.logger.error(
                            f"Failed to write metrics row: {traceback.format_exc()}"
                        )
                        continue

            self.logger.info(
                f"Successfully saved {len(iteration_metrics.items())} metrics to {output_file}"
            )

        except IOError as e:
            self.logger.error(f"Failed to write to CSV file {output_file}: {e}")
            raise RuntimeError(f"Failed to save metrics to CSV: {e}")

    def _detect_resource_type(self, manifest_path: str) -> str:
        """Detect the Kubernetes resource type from the manifest file."""
        try:
            with open(manifest_path, 'r') as f:
                import yaml
                docs = list(yaml.safe_load_all(f))
                if docs and docs[0]:
                    return docs[0].get('kind', 'Unknown')
        except Exception as e:
            self.logger.warning(f"Could not detect resource type for {manifest_path}: {e}")
        return "Unknown"