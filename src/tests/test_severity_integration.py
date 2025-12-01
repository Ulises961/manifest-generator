#!/usr/bin/env python3
"""
Test script to verify severity integration in ManifestsValidator
"""
import json
from validation.manifests_validator import ManifestsValidator

def test_severity_in_diff_report():
    """Test that severity information is added to diff reports"""
    
    # Example diff result with modifications
    diff_result = {
        'resources_extra': {},
        'resources_missing': {},
        'resource_differences': {
            'details': [
                {
                    'path': 'details//deployment//spec//replicas',
                    'value': {'replicas': 1}
                }
            ],
            'productpage': [
                {
                    'path': 'productpage//service//spec//type',
                    'value': {'type': 'ClusterIP'}
                }
            ]
        }
    }
    
    validator = ManifestsValidator()
    
    # Run the analysis
    added_lines, removed_lines, modified_lines, report = validator.count_diff_lines(diff_result, verbose=False)
    
    print("=" * 80)
    print("TEST RESULTS: Severity Integration")
    print("=" * 80)
    print(f"\nTotal modifications: {modified_lines}")
    print(f"Details found: {len(report['modifications']['details'])}")
    
    # Check that severity information is present
    for detail in report['modifications']['details']:
        print(f"\n{'-' * 80}")
        print(f"Resource: {detail['resource']}")
        print(f"Path: {detail['path']}")
        print(f"Lines: {detail['lines']}")
        
        if 'severity' in detail:
            severity = detail['severity']
            print(f"\nSeverity Information:")
            print(f"  Level: {severity.get('severity', 'N/A')}")
            print(f"  Component: {severity.get('component', 'N/A')}")
            print(f"  Issue Type: {severity.get('issue_type', 'N/A')}")
            print(f"  Description: {severity.get('description', 'N/A')}")
            if severity.get('reviewed_level'):
                print(f"  Reviewed Level: {severity.get('reviewed_level')}")
            if severity.get('comments'):
                print(f"  Comments: {severity.get('comments')}")
        else:
            print("\n⚠️  WARNING: No severity information found!")
    
    print("\n" + "=" * 80)
    
    # Export to verify JSON structure
    output_path = '/tmp/test_severity_report.json'
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\nFull report exported to: {output_path}")
    
    return report

if __name__ == "__main__":
    test_severity_in_diff_report()
