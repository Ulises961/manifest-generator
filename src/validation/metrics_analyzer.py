import logging
from typing import Any, Dict

from numpy import isin

from validation import severity


class MetricsAnalyzer:
    def __init__(self):
        """
        Initialize the MetricsAnalyzer.
        """
        self.logger = logging.getLogger(__name__)

    def analyze(self, metrics: Dict[str, Any]) -> Dict[str, int]:
        """
        Count the issues in the metrics and return a summary.
        """
        summary = {
            "total_metrics": 0,
            "critical_issues": 0,
            "high_issues": 0,
            "medium_issues": 0,
            "low_issues": 0,
            "info_issues": 0,
            "false_positives": 0
    }

        for category, metric in metrics.items():
            if category != "resources_analyzed":
                for _, issues in metric.items():
                    if isinstance(issues, list):
                        for issue in issues:
                            if isinstance(issue, dict) and "severity" in issue:
                                severity = issue["severity"]
                                if severity.level == "CRITICAL":
                                    summary["critical_issues"] += 1
                                    summary["total_metrics"] += 1
                                elif severity.level == "HIGH":
                                    summary["high_issues"] += 1
                                    summary["total_metrics"] += 1
                                elif severity.level == "MEDIUM":
                                    summary["medium_issues"] += 1
                                    summary["total_metrics"] += 1
                                elif severity.level == "LOW":
                                    summary["low_issues"] += 1
                                    summary["total_metrics"] += 1
                                elif severity.level == "INFO":
                                    summary["info_issues"] += 1
                                    summary["total_metrics"] += 1
                                if issue.get("reviewed") and issue.get("false_positive"):
                                    summary["false_positives"] += 1

                                    
                    # A whole component is an issue (missing or extra)
                    elif isinstance(issues, dict) and "severity" in issues:
                        severity = issues["severity"]
                        if severity.level == "CRITICAL":
                            summary["critical_issues"] += 1
                            summary["total_metrics"] += 1
                        elif severity.level == "HIGH":
                            summary["high_issues"] += 1
                            summary["total_metrics"] += 1
                        elif severity.level == "MEDIUM":
                            summary["medium_issues"] += 1
                            summary["total_metrics"] += 1
                        elif severity.level == "LOW":
                            summary["low_issues"] += 1
                            summary["total_metrics"] += 1
                        elif severity.level == "INFO":
                            summary["info_issues"] += 1
                            summary["total_metrics"] += 1
                        if issues.get("reviewed") and issues.get("false_positive"):
                            summary["false_positives"] += 1

        return summary

    def summary_to_csv(self, summary: Dict[str, int]) -> str:
        """
        Convert the metrics to a CSV format.
        """
        csv_lines = [
            "Metric,Value",
            f"Total Metrics,{summary['total_metrics']}",
            f"Critical Issues,{summary['critical_issues']}",
            f"High Issues,{summary['high_issues']}",
            f"Medium Issues,{summary['medium_issues']}",
            f"Low Issues,{summary['low_issues']}",
            f"Info Issues,{summary['info_issues']}",
            f"False Positives,{summary['false_positives']}"
        ]
        return "\n".join(csv_lines)


    def save_csv(self, csv_content: str, file_path: str) -> None:
        """
        Save the summary to a file.
        """
        with open(file_path, 'w') as file:
            file.write(csv_content)
            self.logger.info(f"Summary saved to {file_path}")

    def calculate_static_score(self, static_analysis: Dict[str, int]) -> float:
        """
        Calculate normalized static score based on severity-weighted differences 
        relative to cluster size (number of items compared).
        
        Args:
            static_analysis (dict): Counts of issues by severity.
            total_items (int): Total number of items compared (e.g., ports, env vars, labels).
        
        Returns:
            float: Static score between 0 and 100.
        """
        weights = {
            "critical_issues": 10,
            "high_issues": 7,
            "medium_issues": 4,
            "low_issues": 2,
            "info_issues": 1
        }

        total_items = static_analysis.get("total_metrics", 0)
        
        # Calculate weighted penalty
        total_penalty = sum(static_analysis.get(severity, 0) * weight for severity, weight in weights.items())
        
        # Max possible penalty = all items are critical
        max_possible_penalty = total_items * weights["critical_issues"]
        
        if max_possible_penalty == 0:
            return 100.0  # Avoid division by zero, assume perfect cluster
        
        # Normalized score
        score = 100 * (1 - (total_penalty / max_possible_penalty))
        return round(max(0, score), 2)


    def calculate_dynamic_score(self, dynamic_validation: Dict[str, Any]) -> float:
        """
        Calculate dynamic score based on Skaffold results.
        Normalized to 0-100.
        """
        checks = {
            "skaffold_config_valid": 25,
            "manifests_renderable": 25,
            "deployment_successful": 30,
            "pods_ready": 10,
            "services_accessible": 10
        }
        
        # Extract actual results from input
        results = {
            "skaffold_config_valid": dynamic_validation.get("config_validation", {}).get("valid", False),
            "manifests_renderable": dynamic_validation.get("dry_run_results", {}).get("success", False),
            "deployment_successful": dynamic_validation.get("deployment_results", {}).get("success", False),
            "pods_ready": dynamic_validation.get("service_health_checks", {}).get("pods_ready", False),
            "services_accessible": dynamic_validation.get("service_health_checks", {}).get("services_accessible", False)
        }
        
        # Calculate score
        score = sum(weight for check, weight in checks.items() if results.get(check, False))
        
        # Normalize (should already be 0-100, but in case weights change)
        max_score = sum(checks.values())
        return round((score / max_score) * 100, 2)


    def combine_static_dynamic_metrics(self, static_analysis: Dict[str, Any], skaffold_results: Dict[str, Any]) -> Dict[str, Any]:
        """Combine static analysis with dynamic Skaffold validation results."""
        combined = static_analysis.copy()
        
        # Add dynamic validation metrics
        combined["dynamic_validation"] = {
            "skaffold_config_valid": skaffold_results.get("config_validation", {}).get("valid", False),
            "manifests_renderable": skaffold_results.get("dry_run_results", {}).get("success", False),
            "deployment_successful": skaffold_results.get("deployment_results", {}).get("success", False),
            "services_healthy": skaffold_results.get("service_health_checks", {}).get("pods_ready", False),
            "overall_deployability": skaffold_results.get("overall_status") == "passed"
        }
        
        # Calculate scores
        static_score = self.calculate_static_score(static_analysis)
        dynamic_score = self.calculate_dynamic_score(combined["dynamic_validation"])
        compliance_score = self.calculate_compliance_score(skaffold_results.get("kubescape_results", {}))

        combined["static_score"] = static_score
        combined["dynamic_score"] = dynamic_score
        combined["compliance_score"] = compliance_score
        combined["overall_score"] = self.calculate_overall_score(static_score, dynamic_score, compliance_score)

        return combined

    def calculate_compliance_score(self, kubescape_results: Dict[str, int]) -> float:
        """
        Calculate normalized compliance score based on Kubescape results.
        Args:
            kubescape_results: Dict with issue counts by severity and total_controls.        
        Returns:
            float: Score between 0 and 100.
        """

        weights = {
            "critical": 10,
            "high": 7,
            "medium": 4,
            "low": 2,
            "info": 0
        }
        
        total_penalty = sum(kubescape_results.get(severity, 0) * weight for severity, weight in weights.items())
        total_controls = kubescape_results.get("total_controls", 0)
        
        max_possible_penalty = total_controls * weights["critical"]
        
        if max_possible_penalty == 0:
            return 100.0
        
        score = 100 * (1 - (total_penalty / max_possible_penalty))
        return round(max(0, score), 2)

    def calculate_overall_score(self, static_score: float, dynamic_score: float, compliance_score: float) -> float:
        """
        Combine scores with predefined weights.
        """
        weights = {"static": 0.4, "dynamic": 0.4, "compliance": 0.2}
        overall = (static_score * weights["static"] +
                dynamic_score * weights["dynamic"] +
                compliance_score * weights["compliance"])
        return round(overall, 2)
    
    def prepare_results_for_reporting(self, combined_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """ Prepare a flat dictionary for reporting purposes."""
        report = {
            "static_score": combined_metrics.get("static_score", 0),
            "dynamic_score": combined_metrics.get("dynamic_score", 0),
            "compliance_score": combined_metrics.get("compliance_score", 0),
            "overall_score": combined_metrics.get("overall_score", 0),
            "total_metrics": combined_metrics.get("total_metrics", 0),
            "critical_issues": combined_metrics.get("critical_issues", 0),
            "high_issues": combined_metrics.get("high_issues", 0),
            "medium_issues": combined_metrics.get("medium_issues", 0),
            "low_issues": combined_metrics.get("low_issues", 0),
            "info_issues": combined_metrics.get("info_issues", 0),
            "false_positives": combined_metrics.get("false_positives", 0),
            "skaffold_config_valid": combined_metrics.get("dynamic_validation", {}).get("skaffold_config_valid", False),
            "manifests_renderable": combined_metrics.get("dynamic_validation", {}).get("manifests_renderable", False),
            "deployment_successful": combined_metrics.get("dynamic_validation", {}).get("deployment_successful", False),
            "services_healthy": combined_metrics.get("dynamic_validation", {}).get("services_healthy", False),
            "overall_deployability": combined_metrics.get("dynamic_validation", {}).get("overall_deployability", False)
        }
        return report