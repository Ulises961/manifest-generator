#!/usr/bin/env python3
"""Test suite for severity data collection and analysis"""

import pytest
import os
import json
import tempfile
from typing import Dict, Any

from cli.functions.analyze_special_diffs_helper import collect_data, print_data_table


@pytest.fixture
def sample_csv_content():
    """Fixture providing sample CSV content for testing"""
    return """Stage,Microservice,Issue Type,Path,Reference Value,Analyzed Value,Severity Level,Severity Description,Reviewed Level,Comments
Modification,service1,value_difference,service1//deployment//spec//replicas,1,2,MEDIUM,Different replica count,,
Modification,service1,value_difference,service1//deployment//spec//image,image:v1,image:v2,HIGH,Different image version,INFO,Non breaking
Addition,service2,extra,service2//deployment//spec//resources,N/A,{limits: {cpu: 100m}},LOW,Extra resource configuration,,
Removal,service1,missing,service1//service//spec//type,ClusterIP,N/A,CRITICAL,Missing service type,HIGH,Breaking change
Modification,service2,value_difference,service2//deployment//spec//env//0//value,http://api:8080,http://api:9090,HIGH,Different env value,INFO,Non breaking
"""


@pytest.fixture
def temp_csv_file(sample_csv_content):
    """Fixture that creates a temporary CSV file"""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "diff_report_with_reference.csv")
        with open(csv_path, 'w') as f:
            f.write(sample_csv_content)
        yield tmpdir


def test_collect_data_with_valid_csv(temp_csv_file):
    """Test collect_data with a valid CSV file"""
    result = collect_data(temp_csv_file)
    
    # Verify structure
    assert "total_issues" in result
    assert "severity" in result
    assert "issues_by_severity" in result
    
    # Verify total count
    assert result["total_issues"] == 5
    
    # Verify severity counts (using reviewed level when available)
    assert result["severity"]["MEDIUM"] == 1  # First modification has no reviewed level
    assert result["severity"]["INFO"] == 2    # Two modifications with INFO reviewed level
    assert result["severity"]["LOW"] == 1     # Addition
    assert result["severity"]["HIGH"] == 1    # Removal with HIGH reviewed level


def test_collect_data_with_missing_csv():
    """Test collect_data when CSV file doesn't exist"""
    result = collect_data("/nonexistent/path")
    
    assert result == {}


def test_collect_data_empty_csv():
    """Test collect_data with empty CSV (only header)"""
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "diff_report_with_reference.csv")
        with open(csv_path, 'w') as f:
            f.write("Stage,Microservice,Issue Type,Path,Reference Value,Analyzed Value,Severity Level,Severity Description,Reviewed Level,Comments\n")
        
        result = collect_data(tmpdir)
        
        assert result["total_issues"] == 0
        assert result["severity"] == {}
        assert result["issues_by_severity"] == {}


def test_collect_data_malformed_rows(temp_csv_file):
    """Test collect_data handles malformed rows gracefully"""
    # Add a malformed row
    csv_path = os.path.join(temp_csv_file, "diff_report_with_reference.csv")
    with open(csv_path, 'a') as f:
        f.write("incomplete,row\n")
    
    result = collect_data(temp_csv_file)
    
    # Should still process valid rows - malformed row is counted in total but skipped for processing
    # Total includes all rows except header, but severity only counts valid ones
    assert result["total_issues"] == 6  # 5 valid + 1 malformed
    # Verify the valid rows were still processed correctly
    total_severity_count = sum(result["severity"].values())
    assert total_severity_count == 5  # Only 5 valid rows processed


def test_collect_data_severity_priority():
    """Test that reviewed_level takes priority over severity_level"""
    csv_content = """Stage,Microservice,Issue Type,Path,Reference Value,Analyzed Value,Severity Level,Severity Description,Reviewed Level,Comments
Modification,service1,value_difference,service1//path,old,new,CRITICAL,Critical issue,LOW,Actually not critical
"""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "diff_report_with_reference.csv")
        with open(csv_path, 'w') as f:
            f.write(csv_content)
        
        result = collect_data(tmpdir)
        
        # Should use reviewed_level (LOW) instead of severity_level (CRITICAL)
        assert result["severity"].get("LOW") == 1
        assert result["severity"].get("CRITICAL") is None


def test_collect_data_issues_by_severity_structure(temp_csv_file):
    """Test that issues_by_severity contains actual issue objects"""
    result = collect_data(temp_csv_file)
    
    # Check that issues are properly categorized
    for severity, issues in result["issues_by_severity"].items():
        assert isinstance(issues, list)
        for issue in issues:
            assert "stage" in issue
            assert "microservice" in issue
            assert "issue_type" in issue
            assert "path" in issue


def test_print_data_table_basic():
    """Test print_data_table doesn't crash with basic data"""
    data = {
        "without_ir": {
            "repo1": {
                "total_issues": 10,
                "severity": {"HIGH": 5, "MEDIUM": 3, "LOW": 2}
            }
        },
        "with_ir": {
            "repo1": {
                "total_issues": 5,
                "severity": {"HIGH": 2, "MEDIUM": 2, "LOW": 1}
            }
        }
    }
    repositories = ["repo1"]
    
    # Should not raise any exceptions
    try:
        print_data_table(data, repositories)
    except Exception as e:
        pytest.fail(f"print_data_table raised an exception: {e}")


def test_collect_data_all_severity_levels():
    """Test that all severity levels are properly counted"""
    csv_content = """Stage,Microservice,Issue Type,Path,Reference Value,Analyzed Value,Severity Level,Severity Description,Reviewed Level,Comments
Modification,svc,type1,path1,a,b,CRITICAL,Desc,,
Modification,svc,type2,path2,a,b,HIGH,Desc,,
Modification,svc,type3,path3,a,b,MEDIUM,Desc,,
Modification,svc,type4,path4,a,b,LOW,Desc,,
Modification,svc,type5,path5,a,b,INFO,Desc,,
"""
    
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = os.path.join(tmpdir, "diff_report_with_reference.csv")
        with open(csv_path, 'w') as f:
            f.write(csv_content)
        
        result = collect_data(tmpdir)
        
        assert result["severity"]["CRITICAL"] == 1
        assert result["severity"]["HIGH"] == 1
        assert result["severity"]["MEDIUM"] == 1
        assert result["severity"]["LOW"] == 1
        assert result["severity"]["INFO"] == 1


def test_collect_data_with_real_data():
    """Integration test with real data if available"""
    real_path = "/home/ulises/Documents/UniTn/2nd Year/2 semester/Tirocinio/Results/microcalc/without-ir/results"
    
    if not os.path.exists(real_path):
        pytest.skip("Real test data not available")
    
    result = collect_data(real_path)
    
    # Basic assertions about the structure
    assert isinstance(result, dict)
    assert "total_issues" in result
    assert "severity" in result
    assert isinstance(result["total_issues"], int)
    
    # If data exists, should have some issues
    if result["total_issues"] > 0:
        assert len(result["severity"]) > 0
        assert len(result["issues_by_severity"]) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
