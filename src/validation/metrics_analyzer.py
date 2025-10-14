from email import header
import json
import logging
from typing import Any, Dict

from numpy import isin
from rpds import List

from validation import severity


class MetricsAnalyzer:
    def __init__(self):
        """
        Initialize the MetricsAnalyzer.
        """
        self.logger = logging.getLogger(__name__)

    def analyze_results(self, metrics: Dict[str, Any]) -> Dict[str, int]:
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
                                if (severity.reviewed_level is not None and severity.reviewed_level == "CRITICAL") or severity.level == "CRITICAL":
                                    summary["critical_issues"] += 1
                                    summary["total_metrics"] += 1
                                elif (severity.reviewed_level is not None and severity.reviewed_level == "HIGH") or severity.level == "HIGH":
                                    summary["high_issues"] += 1
                                    summary["total_metrics"] += 1
                                elif (severity.reviewed_level is not None and severity.reviewed_level == "MEDIUM") or severity.level == "MEDIUM":
                                    summary["medium_issues"] += 1
                                    summary["total_metrics"] += 1
                                elif (severity.reviewed_level is not None and severity.reviewed_level == "LOW") or severity.level == "LOW":
                                    summary["low_issues"] += 1
                                    summary["total_metrics"] += 1
                                elif (severity.reviewed_level is not None and severity.reviewed_level == "INFO") or severity.level == "INFO":
                                    summary["info_issues"] += 1
                                    summary["total_metrics"] += 1
                                if  severity.reviewed_level is not None:
                                    summary["false_positives"] += 1

                                    
                    # A whole component is an issue (missing or extra)
                    elif isinstance(issues, dict) and "severity" in issues:
                        severity = issues["severity"]
                        if (severity.reviewed_level is not None and severity.reviewed_level == "CRITICAL") or severity.level == "CRITICAL":
                            summary["critical_issues"] += 1
                            summary["total_metrics"] += 1
                        elif (severity.reviewed_level is not None and severity.reviewed_level == "HIGH") or severity.level == "HIGH":
                            summary["high_issues"] += 1
                            summary["total_metrics"] += 1
                        elif (severity.reviewed_level is not None and severity.reviewed_level == "MEDIUM") or severity.level == "MEDIUM":
                            summary["medium_issues"] += 1
                            summary["total_metrics"] += 1
                        elif (severity.reviewed_level is not None and severity.reviewed_level == "LOW") or severity.level == "LOW":
                            summary["low_issues"] += 1
                            summary["total_metrics"] += 1
                        elif (severity.reviewed_level is not None and severity.reviewed_level == "INFO") or severity.level == "INFO":
                            summary["info_issues"] += 1
                            summary["total_metrics"] += 1
                        if severity.reviewed_level is not None:
                            summary["false_positives"] += 1

        return summary
    
    def analyse_kubescape_results(self, kubescape_results: list[list[str]]) -> Dict[str, int]:
        """
        Count the issues in the kubescape results and return a summary.
        """
        summary = {
            "critical": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "total_controls": 0
        }

        header = kubescape_results[0]
        critical = header.index("critical")
        high = header.index("high")
        medium = header.index("medium")
        low = header.index("low")
        total_controls_per_manifests = header.index("total_controls")
        for resource in kubescape_results[1:]:
            summary["critical"] += int(resource[critical])
            summary["high"] += int(resource[high])
            summary["medium"] += int(resource[medium])
            summary["low"] += int(resource[low])
            summary["total_controls"] += int(resource[total_controls_per_manifests])
        return summary
    
    def analyze_validation_csv(self, metrics: list[list[str]]) -> Dict[str, Any]:
        """
        Count the issues in the CSV metrics and return a summary.
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

        # Assuming the CSV has a header row, find the index of relevant columns
        header = metrics[0]
        severity_index = header.index("Severity Level")
        reviewed_index = header.index("Reviewed Level")
        for row in metrics[1:]:
            severity_level = row[severity_index]
            reviewed_level = row[reviewed_index]

            if reviewed_level == "CRITICAL" or (reviewed_level == "" and severity_level == "CRITICAL"):
                summary["critical_issues"] += 1
                summary["total_metrics"] += 1
            elif reviewed_level == "HIGH" or (reviewed_level == "" and severity_level == "HIGH"):
                summary["high_issues"] += 1
                summary["total_metrics"] += 1
            elif reviewed_level == "MEDIUM" or (reviewed_level == "" and severity_level == "MEDIUM"):
                summary["medium_issues"] += 1
                summary["total_metrics"] += 1
            elif reviewed_level == "LOW" or (reviewed_level == "" and severity_level == "LOW"):
                summary["low_issues"] += 1
                summary["total_metrics"] += 1
            elif reviewed_level == "INFO" or (reviewed_level == "" and severity_level == "INFO"):
                summary["info_issues"] += 1
                summary["total_metrics"] += 1

            if reviewed_level in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
                summary["false_positives"] += 1

        return summary

    def save_csv(self, csv_content: str, file_path: str) -> None:
        """
        Save the summary to a file.
        """
        with open(file_path, 'w') as file:
            file.write(csv_content)
            self.logger.info(f"Summary saved to {file_path}")

    def calculate_static_score(self, static_analysis: Dict[str, Any]) -> float:
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
            "info_issues": 0
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
            "manifests_renderable": 30,
            "deployment_successful": 40,
            "pods_ready": 15,
            "services_accessible": 15
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


    def combine_static_dynamic_metrics(self, static_analysis: list[list[str]], skaffold_results: Dict[str, Any], kubescape_results: Dict[str, int]) -> Dict[str, Any]:
        """Combine static analysis with dynamic Skaffold validation results."""
        combined: Dict[str, Any] = {"static_analysis": {}, "dynamic_analysis": {}, "kubescape_results": kubescape_results}

        # Add static analysis metrics
        combined["static_analysis"] = self.analyze_validation_csv(static_analysis)
                
        # Calculate scores
        static_score = self.calculate_static_score(combined["static_analysis"])
        dynamic_score = self.calculate_dynamic_score(skaffold_results)

        combined["static_score"] = static_score
        combined["dynamic_score"] = dynamic_score
        combined["compliance_score"] = self.calculate_compliance_score(kubescape_results)
        combined["overall_score"] = self.calculate_overall_score(static_score, dynamic_score, combined["compliance_score"])
        combined["skaffold_results"] = skaffold_results

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
        weights = {"static": 0.45, "dynamic": 0.55}
        overall = (static_score * weights["static"] +
                dynamic_score * weights["dynamic"])
        return round(overall, 2)
    
    def prepare_results_for_reporting(self, combined_metrics: Dict[str, Any]) -> str:
        """Prepare a CSV-formatted string for reporting purposes."""

        headers = [
            "Manual Inspection Final Score",
            "Dynamic (Skaffold) Score",
            "Weighted Average (Dynamic - Manual)Score",
            "Kubescape Compliance Score",
            "Manual Inspection Critical Issues",
            "Manual Inspection High Issues",
            "Manual Inspection Medium Issues",
            "Manual Inspection Low Issues",
            "Manual Inspection Info Issues",
            "Manual Inspection False Positives",
            "Total Analyzed Issues Metrics",
            "Manifests Renderable",
            "Deployment Successful",
            "Services Healthy",
            "Kubescape Critical Issues",
            "Kubescape High Issues",
            "Kubescape Medium Issues",
            "Kubescape Low Issues",
            "Kubescape Info Issues",
            "Total Kubescape Controls"
        ]

        values = [
            combined_metrics.get("static_score", 0),
            combined_metrics.get("dynamic_score", 0),
            combined_metrics.get("overall_score", 0),
            combined_metrics.get("compliance_score", 0),
            combined_metrics.get("static_analysis", {}).get("critical_issues", 0),
            combined_metrics.get("static_analysis", {}).get("high_issues", 0),
            combined_metrics.get("static_analysis", {}).get("medium_issues", 0),
            combined_metrics.get("static_analysis", {}).get("low_issues", 0),
            combined_metrics.get("static_analysis", {}).get("info_issues", 0),
            combined_metrics.get("static_analysis", {}).get("false_positives", 0),
            combined_metrics.get("static_analysis", {}).get("total_metrics", 0),
            combined_metrics.get("skaffold_results", {}).get("dry_run_results", {}).get("success", False),
            combined_metrics.get("skaffold_results", {}).get("deployment_results", {}).get("success", False),
            combined_metrics.get("skaffold_results", {}).get("service_health_checks", {}).get("pods_ready", False),
            combined_metrics.get("kubescape_results", {}).get("critical", 0),
            combined_metrics.get("kubescape_results", {}).get("high", 0),
            combined_metrics.get("kubescape_results", {}).get("medium", 0),
            combined_metrics.get("kubescape_results", {}).get("low", 0),
            combined_metrics.get("kubescape_results", {}).get("info", 0),
            combined_metrics.get("kubescape_results", {}).get("total_controls", 0)
        ]

        # Convert all values to string
        values = [str(v) for v in values]

        # Build CSV string with header and values
        csv_output = ",".join(headers) + "\n" + ",".join(values) + "\n"
        return csv_output
