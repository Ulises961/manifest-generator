import logging
from typing import Any, Dict

from numpy import isin


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
            "total_metrics": len(metrics.get("resources_analyzed", [])),
            "critical_issues": 0,
            "high_issues": 0,
            "medium_issues": 0,
            "low_issues": 0,
        }

        for category, metric in metrics.items():
            if category != "resources_analyzed":
                for _, issues in metric.items():
                    if isinstance(issues, list):
                        for issue in issues:
                            if isinstance(issue, dict) and "severity" in issue:
                                if issue["severity"].level == "CRITICAL":
                                    summary["critical_issues"] += 1
                                elif issue["severity"].level == "HIGH":
                                    summary["high_issues"] += 1
                                elif issue["severity"].level == "MEDIUM":
                                    summary["medium_issues"] += 1
                                elif issue["severity"].level == "LOW":
                                    summary["low_issues"] += 1
                                    
                    # A whole component is an issue (missing or extra)
                    elif isinstance(issues, dict) and "severity" in issues:
                        if issues["severity"].level == "CRITICAL":
                            summary["critical_issues"] += 1
                        elif issues["severity"].level == "HIGH":
                            summary["high_issues"] += 1
                        elif issues["severity"].level == "MEDIUM":
                            summary["medium_issues"] += 1
                        elif issues["severity"].level == "LOW":
                            summary["low_issues"] += 1

        return summary

    def to_csv(self, summary: Dict[str, int]) -> str:
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
        ]
        return "\n".join(csv_lines)
    
    def save_summary(self, summary: Dict[str, int], file_path: str) -> None:
        """
        Save the summary to a file.
        """
        with open(file_path, 'w') as file:
            csv_content = self.to_csv(summary)
            file.write(csv_content)
            self.logger.info(f"Summary saved to {file_path}")