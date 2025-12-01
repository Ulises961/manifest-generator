import os
import re
from typing import Any, Dict, List, Optional, Tuple
from utils.file_utils import load_yaml_file
import logging


logger = logging.getLogger(__name__)

class Severity:
    """Enhanced severity class with nuanced classification support."""

    def __init__(
        self,
        level: str,
        description: str = "",
        component: str = "",
        issue_type: str = "",
        reviewed_level: str = "",
        comments: str = "",
        reference_value: Optional[Any] = None,
        analyzed_value: Optional[Any] = None,
    ):
        self.level = level
        self.description = description
        self.component = component  # e.g., "ports", "env", "image"
        self.issue_type = (
            issue_type  # e.g., "missing", "incorrect_value", "missing_attribute"
        )
        self.reviewed_level = reviewed_level
        self.comments = comments
        self.reference_value = reference_value
        self.analyzed_value = analyzed_value

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
            "reviewed_level": self.reviewed_level,
            "comments": self.comments,
            "reference_value": self.reference_value,
            "analyzed_value": self.analyzed_value,
        }
    
    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Severity":
        """Create Severity object from dictionary."""
        return Severity(
            level=data.get("severity", "MEDIUM"),
            description=data.get("description", ""),
            component=data.get("component", ""),
            issue_type=data.get("issue_type", ""),
            reviewed_level=data.get("reviewed_level", ""),
            comments=data.get("comments", ""),
            reference_value=data.get("reference_value", None),
            analyzed_value=data.get("analyzed_value", None),
        )

# Enhanced severity analysis function
def analyze_component_severity(
    component: str, issue_type: str, attribute: Optional[str] = None, reference_value: Optional[str] = None, analyzed_value: Optional[str] = None, path: str = ""
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
        return DefaultRules.get(component, issue_type, attribute, reference_value, analyzed_value=analyzed_value)

    attr_rules = severity_rules.get(component, {})
    if issue_type == "missing_attribute":
        missing_attributes = attr_rules.get("missing_attribute", {})
        if attribute and attribute in missing_attributes.keys():
            if attribute == "app":
                    if reference_value in ["app", "app.kubernetes.io/name"]:
                        # If the 'app' label follows a standard naming convention, lower severity
                        return Severity(missing_attributes[attribute]["level"], missing_attributes[attribute]["description"], component, f"missing_attribute:{attribute}", "INFO", "The 'app' label uses a standard naming convention.", reference_value=reference_value, analyzed_value=analyzed_value)
            return Severity(missing_attributes[attribute]["level"], missing_attributes[attribute]["description"], component, f"missing_attribute:{attribute}", reference_value=reference_value, analyzed_value=analyzed_value)
        return DefaultRules.get(component, issue_type, attribute, reference_value, analyzed_value=analyzed_value)
    rule = attr_rules.get(issue_type)
  
    if rule:
        if component == "selector" or component == "matchLabels" or component == "labels":
            if reference_value in ["app", "app.kubernetes.io/name"]:
                    # If the selector uses a standard naming convention, lower severity
                    return Severity(rule["level"], rule["description"], component, issue_type, "INFO", "The selector uses a standard naming convention.", reference_value=reference_value, analyzed_value=analyzed_value)
        return Severity(rule["level"], rule["description"], component, issue_type, reference_value=reference_value, analyzed_value=analyzed_value)

    return DefaultRules.get(component, issue_type, attribute, reference_value=reference_value, analyzed_value=analyzed_value)


def get_issue_type(path: str, issues: Any) -> Tuple[str, Optional[str]]:
    """
    Analyze the path and missing values to determine the specific issue type and attribute.

    Args:
        path: The path where the issue occurs (e.g., "microservice//deployment//spec//template//spec//containers//0//ports")
        issues: The missing values/structure from the diff

    Returns:
        Tuple of (issue_type, specific_attribute)
    """
    path_parts = reversed(path.split("//"))

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
            if isinstance(issues, dict):
                # Check what env attributes are missing
                if "name" in missing_keys:
                    return "missing_attribute", "name"
                if "value" in missing_keys and "valueFrom" not in missing_keys:
                    return "missing_attribute", "value"
                if "valueFrom" in missing_keys:
                    return "missing_attribute", "valueFrom"

        # Ports configuration
        if part_lower == "ports":
            if isinstance(issues, list):
                return "missing", None
            if isinstance(issues, dict) or missing_keys:
                # Check specific port attributes
                if "containerPort" in missing_keys:
                    return "missing_attribute", "containerPort"
                if "name" in missing_keys:
                    return "missing_attribute", "name"
                if "protocol" in missing_keys:
                    return "missing_attribute", "protocol"
                if "targetPort" in missing_keys:
                    return "missing_attribute", "targetPort"
                if "nodePort" in missing_keys:
                    return "missing_attribute", "nodePort"
                if "type" in missing_keys:
                    return "missing_attribute", "type"
            if part in missing_keys:
                return "missing", part

        # Image
        if part_lower == "image":
            return "missing", None

        # Resources
        if part_lower == "resources":
            if "limits" in missing_keys:
                return "missing_attribute", "limits"
            if "requests" in missing_keys:
                return "missing_attribute", "requests"
            if "memory" in missing_keys:
                return "missing_attribute", "memory"
            if "cpu" in missing_keys:
                return "missing_attribute", "cpu"
            if part in missing_keys:
                return "missing", part
            return "missing", None

        # Volume Mounts
        if part_lower == "volumemounts":
            if "mountPath" in missing_keys:
                return "missing_attribute", "mountPath"
            if "name" in missing_keys:
                return "missing_attribute", "name"
            if "readOnly" in missing_keys:
                return "missing_attribute", "readOnly"
            if part in missing_keys:
                return "missing", part
            return "missing", None


        # Security Context
        if part_lower == "securitycontext":
            if part in missing_keys:
                return "missing", part
            if "runAsUser" in missing_keys:
                return "missing_attribute", "runAsUser"
            if "runAsNonRoot" in missing_keys:
                return "missing_attribute", "runAsNonRoot"
            if "allowPrivilegeEscalation" in missing_keys:
                return "missing_attribute", "allowPrivilegeEscalation"
            return "missing", None
        
        # Probes
        if part_lower in ["readinessprobe", "livenessprobe"]:
            if "httpGet" in missing_keys:
                return "missing_attribute", "httpGet"
            if "initialDelaySeconds" in missing_keys:
                return "missing_attribute", "initialDelaySeconds"
            if "periodSeconds" in missing_keys:
                return "missing_attribute", "periodSeconds"
            if "timeoutSeconds" in missing_keys:
                return "missing_attribute", "timeoutSeconds"
            if part in missing_keys:
                return "missing", part
            return "missing", None

        # Labels
        if part_lower == "labels":
            if "app" in missing_keys or "app.kubernetes.io/name" in missing_keys:
                return "missing_attribute", "app"
            if "version" in missing_keys:
                return "missing_attribute", "version"
            if part in missing_keys:
                return "missing", part
            return "missing", None

        # Volumes
        if part_lower == "volumes":
            if "name" in missing_keys:
                return "missing_attribute", "name"
            if "persistentVolumeClaim" in missing_keys:
                return "missing_attribute", "persistentVolumeClaim"
            if part in missing_keys:
                return "missing", part
            return "missing", None

        # Service Account
        if part_lower == "serviceaccount":
            return "missing", part

        if part_lower == "serviceaccountname":
            return "missing", part
        
        # Command/Args
        if part_lower in ["command", "args"]:
            return "missing", part

        # Working Directory
        if part_lower == "workingdir":
            return "missing", part

        # Init Containers
        if part_lower == "initcontainers":
            return "missing", part

        
        # Annotations
        if part_lower == "annotations":
            return "missing", part

        # Affinity
        if part_lower == "affinity":
            return "missing", part

        # Node Selector
        if part_lower == "nodeselector":
            return "missing", part

        # Tolerations
        if part_lower == "tolerations":
            return "missing", part

        if part_lower == "terminationgraceperiodseconds":
            return "missing", part
        
        if part_lower == "restartpolicy":
            return "missing", part
        
        # Match Labels
        if part_lower == "matchlabels":
            if "app" in missing_keys in missing_keys:
                return "missing", "app"
            if "app.kubernetes.io/name" in missing_keys:
                return "missing", "app.kubernetes.io/name"
            if "version" in missing_keys:
                return "missing_attribute", "version"
            return "missing", part
        
        if part_lower in [
            "deployment",
            "service",
            "configmap",
            "secret",
            "statefulset",
            "persistentvolumeclaim",
            "pod"
        ]:
            return "missing", part
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
        component: str, issue_type: str, attribute: Optional[str] = None, reference_value: Optional[str] = None, analyzed_value: Optional[str] = None
    ) -> Severity:
        desc = f"{issue_type.replace('_', ' ').capitalize()} in {component}"
        level = DefaultRules.default_rules.get(issue_type, "MEDIUM")
        issue_key = f"{issue_type}:{attribute}" if attribute else issue_type
        return Severity(level, desc, component, issue_key, reference_value=reference_value, analyzed_value=analyzed_value)