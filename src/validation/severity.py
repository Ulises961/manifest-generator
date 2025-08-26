import json
import os
from typing import Any, Dict, List, Optional, Tuple

import yaml

from utils.file_utils import load_yaml_file


class Severity:
    """Enhanced severity class with nuanced classification support."""

    def __init__(
        self,
        level: str,
        description: str = "",
        component: str = "",
        issue_type: str = "",
        reviewed: bool = False,
        false_positive: bool = False,
        comments: str = "",
    ):
        self.level = level
        self.description = description
        self.component = component  # e.g., "ports", "env", "image"
        self.issue_type = (
            issue_type  # e.g., "missing", "incorrect_value", "missing_attribute"
        )
        self.reviewed = reviewed
        self.false_positive = false_positive
        self.comments = comments

    def __str__(self):
        return self.level

    def __repr__(self):
        return f"Severity(level={self.level}, component={self.component}, issue_type={self.issue_type})"

    def __eq__(self, other):
        if not isinstance(other, Severity):
            return False
        return self.level == other.level

    def __hash__(self) -> int:
        return hash(self.level)

    def to_dict(self) -> dict:
        """Convert Severity object to dictionary for JSON serialization."""
        return {
            "severity": self.level,
            "description": self.description,
            "component": self.component,
            "issue_type": self.issue_type,
            "reviewed": self.reviewed,
            "false_positive": self.false_positive,
            "comments": self.comments,
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Severity":
        """Create Severity object from dictionary."""
        return Severity(
            level=data.get("severity", "MEDIUM"),
            description=data.get("description", ""),
            component=data.get("component", ""),
            issue_type=data.get("issue_type", ""),
            reviewed=data.get("reviewed", False),
            false_positive=data.get("false_positive", False),
            comments=data.get("comments", ""),
        )

# Enhanced severity analysis function
def analyze_component_severity(
    component: str, issue_type: str, attribute: Optional[str] = None
) -> Severity:
    """
    Analyze severity with nuanced classification based on component and issue type.

    Args:
        component: The K8s component (e.g., "ports", "env", "image")
        issue_type: Type of issue ("missing", "extra", "value_difference", "missing_attribute")
        path: Full path for additional context
    """

    # Nuanced severity rules
    severity_config = load_yaml_file(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            os.getenv("SEVERITY_CONFIG", "resources/validation/severity_config.yaml"),
        )
    )
    severity_rules = severity_config["severity_rules"]

    if not severity_rules:
        return DefaultRules.get(component, issue_type, attribute)

    if issue_type == "missing_attribute":
        attr_rules = severity_rules.get("missing_attribute", {})
        if attribute and attribute in attr_rules:
            level, desc = attr_rules[attribute]
            return Severity(level, desc, component, f"missing_attribute:{attribute}")
        return DefaultRules.get(component, issue_type, attribute)

    rule = severity_rules.get(issue_type)
    if rule:
        level, desc = rule
        return Severity(level, desc, component, issue_type)

    return DefaultRules.get(component, issue_type, attribute)


def get_issue_type(path: str, issues: Any) -> Tuple[str, Optional[str]]:
    """
    Analyze the path and missing values to determine the specific issue type and attribute.

    Args:
        path: The path where the issue occurs (e.g., "microservice//deployment//spec//template//spec//containers//0//ports")
        issues: The missing values/structure from the diff

    Returns:
        Tuple of (issue_type, specific_attribute)
    """
    path_parts = path.split("//")

    # Convert issues to a flat structure for analysis
    missing_keys = _extract_missing_keys(issues)

    # Analyze based on path context
    for i, part in enumerate(path_parts):
        part_lower = part.lower()

        # Environment variables
        if part_lower == "env":
            if isinstance(issues, list):
                # Missing entire env array
                return "missing", None
            elif isinstance(issues, dict):
                # Check what env attributes are missing
                if "name" in missing_keys:
                    return "missing_attribute", "name"
                elif "value" in missing_keys and "valueFrom" not in missing_keys:
                    return "missing_attribute", "value"
                elif "valueFrom" in missing_keys:
                    return "missing_attribute", "valueFrom"
            return "missing", None

        # Ports configuration
        elif part_lower == "ports":
            if isinstance(issues, list):
                return "missing", None
            elif isinstance(issues, dict) or missing_keys:
                # Check specific port attributes
                if "containerPort" in missing_keys:
                    return "missing_attribute", "containerPort"
                elif "name" in missing_keys:
                    return "missing_attribute", "name"
                elif "protocol" in missing_keys:
                    return "missing_attribute", "protocol"
                elif "targetPort" in missing_keys:
                    return "missing_attribute", "targetPort"
            return "missing", None

        # Image
        elif part_lower == "image":
            return "missing", None

        # Resources
        elif part_lower == "resources":
            if "limits" in missing_keys:
                return "missing_attribute", "limits"
            elif "requests" in missing_keys:
                return "missing_attribute", "requests"
            elif "memory" in missing_keys:
                return "missing_attribute", "memory"
            elif "cpu" in missing_keys:
                return "missing_attribute", "cpu"
            return "missing", None

        # Volume Mounts
        elif part_lower == "volumemounts":
            if "mountPath" in missing_keys:
                return "missing_attribute", "mountPath"
            elif "name" in missing_keys:
                return "missing_attribute", "name"
            elif "readOnly" in missing_keys:
                return "missing_attribute", "readOnly"
            return "missing", None

        # Security Context
        elif part_lower == "securitycontext":
            if "runAsUser" in missing_keys:
                return "missing_attribute", "runAsUser"
            elif "runAsNonRoot" in missing_keys:
                return "missing_attribute", "runAsNonRoot"
            elif "allowPrivilegeEscalation" in missing_keys:
                return "missing_attribute", "allowPrivilegeEscalation"
            return "missing", None

        # Probes
        elif part_lower in ["readinessprobe", "livenessprobe"]:
            probe_type = (
                "readinessProbe" if "readiness" in part_lower else "livenessProbe"
            )
            if "httpGet" in missing_keys:
                return "missing_attribute", "httpGet"
            elif "initialDelaySeconds" in missing_keys:
                return "missing_attribute", "initialDelaySeconds"
            elif "periodSeconds" in missing_keys:
                return "missing_attribute", "periodSeconds"
            elif "timeoutSeconds" in missing_keys:
                return "missing_attribute", "timeoutSeconds"
            return "missing", None

        # Labels
        elif part_lower == "labels":
            if "app" in missing_keys or "app.kubernetes.io/name" in missing_keys:
                return "missing_attribute", "app"
            elif "version" in missing_keys:
                return "missing_attribute", "version"
            return "missing", None

        # Service Account
        elif part_lower == "serviceaccount":
            return "missing", None

        # Command/Args
        elif part_lower in ["command", "args"]:
            return "missing", None

        # Working Directory
        elif part_lower == "workingdir":
            return "missing", None

        # Init Containers
        elif part_lower == "initcontainers":
            return "missing", None

        # Volumes
        elif part_lower == "volumes":
            if "name" in missing_keys:
                return "missing_attribute", "name"
            elif "persistentVolumeClaim" in missing_keys:
                return "missing_attribute", "persistentVolumeClaim"
            return "missing", None

        # Annotations
        elif part_lower == "annotations":
            return "missing", None

        # Affinity
        elif part_lower == "affinity":
            return "missing", None

        # Node Selector
        elif part_lower == "nodeselector":
            return "missing", None

        # Tolerations
        elif part_lower == "tolerations":
            return "missing", None

    # Default fallback
    return "missing", None


def _extract_missing_keys(issues: Any) -> List[str]:
    """
    Extract all missing keys from the issues structure.

    Args:
        issues: The missing values/structure from the diff

    Returns:
        List of missing key names
    """
    missing_keys = []

    if isinstance(issues, dict):
        # If it's a dict, the keys are what's missing
        missing_keys.extend(issues.keys())
        # Recursively extract from nested structures
        for value in issues.values():
            if isinstance(value, dict):
                missing_keys.extend(_extract_missing_keys(value))
    elif isinstance(issues, list):
        # If it's a list, check each item
        for item in issues:
            if isinstance(item, dict):
                missing_keys.extend(_extract_missing_keys(item))
            elif isinstance(item, str):
                missing_keys.append(item)
    elif isinstance(issues, str):
        missing_keys.append(issues)

    return missing_keys


__all__ = ["Severity", "analyze_component_severity"]


class DefaultRules:
    """Fallback severity rules when a component or issue type is not found."""

    severity_config = load_yaml_file(
        os.path.join(
            os.path.dirname(__file__),
            "..",
            os.getenv("SEVERITY_CONFIG", "resources/validation/severity_config.yaml")
        )
    )
    default_rules = severity_config["default_rules"]

    @staticmethod
    def get(
        component: str, issue_type: str, attribute: Optional[str] = None
    ) -> Severity:
        desc = f"{issue_type.replace('_', ' ').capitalize()} in {component}"
        level = DefaultRules.default_rules.get(issue_type, "MEDIUM")
        issue_key = f"{issue_type}:{attribute}" if attribute else issue_type
        return Severity(level, desc, component, issue_key)
