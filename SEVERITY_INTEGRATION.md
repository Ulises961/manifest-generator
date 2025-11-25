# Severity Integration in ManifestsValidator

## Overview
Successfully integrated severity analysis into the `ManifestsValidator` class to provide severity information for each modification, addition, and removal in the human effort metrics.

## Changes Made

### 1. Import Severity Module
Added imports to `manifests_validator.py`:
```python
from validation.severity import analyze_component_severity, get_issue_type
```

### 2. Enhanced count_diff_lines Method

#### For Modifications (resource_differences):
- Extracts component from path using `_extract_component_from_path()`
- Determines issue type and attribute using `get_issue_type()`
- Analyzes severity using `analyze_component_severity()`
- Adds severity object to each detail entry

#### For Additions (resources_extra):
- Extracts component from path
- Uses "extra" as issue type
- Adds severity information for each addition

#### For Removals (resources_missing):
- Extracts component from path
- Determines issue type using `get_issue_type()`
- Adds severity information for both complete resource removals and indexed item removals

## Severity Object Structure

Each detail entry now includes a `severity` object with the following fields:

```json
{
  "severity": "HIGH|MEDIUM|LOW|INFO",
  "description": "Human-readable description of the issue",
  "component": "ports|env|image|volumes|etc",
  "issue_type": "missing|extra|value_difference|missing_attribute",
  "reviewed_level": "Optional reviewed severity level",
  "comments": "Optional comments about the severity"
}
```

## Example Output

```json
{
  "resource": "productpage",
  "path": "productpage//service//spec//type",
  "lines": 1,
  "breakdown": {
    "dict_keys": 0,
    "list_items": 0,
    "string_lines": 1,
    "multiline_strings": 0,
    "primitive_values": 0
  },
  "items": [
    {
      "type": "string",
      "path": "productpage.type",
      "value": "ClusterIP",
      "lines": 1,
      "is_multiline": false
    }
  ],
  "severity": {
    "severity": "MEDIUM",
    "description": "Missing in spec",
    "component": "spec",
    "issue_type": "missing:service",
    "reviewed_level": "",
    "comments": ""
  }
}
```

## Usage

The severity information is automatically included when running:

```python
validator = ManifestsValidator()
validator.levenshtein_manifests_distance(
    analyzed_cluster_path="path/to/analyzed",
    reference_cluster_path="path/to/reference"
)
```

The resulting `diff_report.json` will now contain severity information for all additions, removals, and modifications.

## Benefits

1. **Better Insight**: Understand the criticality of each change
2. **Prioritization**: Focus on HIGH severity issues first
3. **Documentation**: Clear descriptions of what each issue means
4. **Automation**: Severity is automatically calculated based on component and issue type
5. **Customization**: Severity rules can be configured via `severity_config.yaml`

## Testing

A test script has been provided at `test_severity_integration.py` to verify the integration works correctly.
