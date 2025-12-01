#!/usr/bin/env python3
"""Test script to verify the collect_data function"""

import sys
import os
import json

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from cli.functions.analyze_special_diffs_helper import collect_data

def test_collect_data():
    """Test the collect_data function with sample data"""
    
    # Test with the microcalc without-ir results
    test_path = "/home/ulises/Documents/UniTn/2nd Year/2 semester/Tirocinio/Results/microcalc/without-ir/results"
    
    if not os.path.exists(test_path):
        print(f"Test path does not exist: {test_path}")
        return
    
    print("="*80)
    print("Testing collect_data function")
    print("="*80)
    print(f"\nTest path: {test_path}")
    
    result = collect_data(test_path)
    
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Total issues: {result['summary']['total_issues']}")
    print(f"\nSeverity distribution:")
    for severity, count in sorted(result['summary']['by_severity'].items()):
        print(f"  {severity}: {count}")
    
    print(f"\nStage distribution:")
    for stage, count in sorted(result['summary']['by_stage'].items()):
        print(f"  {stage}: {count}")
    
    print(f"\nIssue type distribution (top 10):")
    sorted_types = sorted(result['summary']['by_issue_type'].items(), 
                         key=lambda x: x[1], reverse=True)[:10]
    for issue_type, count in sorted_types:
        print(f"  {issue_type}: {count}")
    
    print(f"\nReviewed level distribution:")
    for level, count in sorted(result['summary']['by_reviewed_level'].items()):
        print(f"  {level}: {count}")
    
    print(f"\nMicroservices affected: {len(result['microservices'])}")
    print("\nTop 5 microservices by issue count:")
    sorted_ms = sorted(result['microservices'].items(), 
                      key=lambda x: x[1]['total_issues'], reverse=True)[:5]
    for ms_name, ms_data in sorted_ms:
        print(f"  {ms_name}: {ms_data['total_issues']} issues")
        for severity, count in sorted(ms_data['by_severity'].items()):
            print(f"    - {severity}: {count}")
    
    # Export sample result
    output_path = "/tmp/test_severity_collection.json"
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"\n{'='*80}")
    print(f"Full result exported to: {output_path}")
    print("="*80)
    
    return result

if __name__ == "__main__":
    test_collect_data()
