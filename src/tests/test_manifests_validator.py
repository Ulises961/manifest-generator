import os
import json
import pytest
import tempfile
import yaml
from unittest.mock import Mock, patch, MagicMock
from validation.manifests_validator import ManifestsValidator


@pytest.fixture
def validator():
    return ManifestsValidator()


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_yaml_content():
    return {
        'deployment': {
            'apiVersion': 'apps/v1',
            'kind': 'Deployment',
            'metadata': {
                'name': 'test-app',
                'labels': {'app': 'test-service'}
            },
            'spec': {
                'template': {
                    'spec': {
                        'containers': [{'name': 'app', 'image': 'nginx'}]
                    }
                }
            }
        },
        'configmap': {
            'apiVersion': 'v1',
            'kind': 'ConfigMap',
            'metadata': {'name': 'test-config'},
            'data': {'key1': 'value1', 'key2': 'value2'}
        }
    }


def test_generate_cluster_for_levenshtein_empty_directory(validator, temp_dir):
    cluster = validator._generate_cluster_for_levenshtein(temp_dir)
    assert cluster == {}


def test_generate_cluster_for_levenshtein_with_yaml_files(validator, temp_dir, sample_yaml_content):
    # Create YAML files
    with open(os.path.join(temp_dir, 'deployment.yaml'), 'w') as f:
        yaml.dump(sample_yaml_content['deployment'], f)
    
    with open(os.path.join(temp_dir, 'config.yml'), 'w') as f:
        yaml.dump(sample_yaml_content['configmap'], f)
    
    cluster = validator._generate_cluster_for_levenshtein(temp_dir)
    
    assert 'test-app' in cluster
    assert 'deployment' in cluster['test-app']


def test_get_microservice_name(validator):
    # Test with app label
    resource = {
        'metadata': {
            'name': 'test-deployment',
            'labels': {'app': 'my-service'}
        }
    }
    assert validator._get_microservice_name(resource) == 'test-deployment'
    
    # Test with name label
    resource = {
        'metadata': {
            'labels': {'name': 'another-service'}
        }
    }
    with pytest.raises(ValueError):
        validator._get_microservice_name(resource)

def test_merge_env_vars_with_configmap(validator):
    container = {
        'envFrom': [
            {'configMapRef': {'name': 'test-config'}}
        ]
    }
    supporting_resources = {
        'test-config': {
            'data': {'KEY1': 'value1', 'KEY2': 'value2'}
        }
    }
    
    validator._merge_env_vars(container, supporting_resources)
    
    assert 'env' in container
    assert len(container['env']) == 2
    assert {'name': 'KEY1', 'value': 'value1'} in container['env']
    assert 'envFrom' not in container


def test_merge_env_vars_with_secret(validator):
    container = {
        'envFrom': [
            {'secretRef': {'name': 'test-secret'}}
        ]
    }
    supporting_resources = {
        'test-secret': {
            'data': {'SECRET_KEY': 'secret_value'}
        }
    }
    
    validator._merge_env_vars(container, supporting_resources)
    
    assert 'env' in container
    assert {'name': 'SECRET_KEY', 'value': 'secret_value'} in container['env']


def test_merge_env_vars_with_value_from(validator):
    container = {
        'env': [
            {
                'name': 'CONFIG_VAL',
                'valueFrom': {
                    'configMapKeyRef': {
                        'name': 'test-config',
                        'key': 'config-key'
                    }
                }
            }
        ]
    }
    supporting_resources = {
        'test-config': {
            'data': {'config-key': 'config-value'}
        }
    }
    
    validator._merge_env_vars(container, supporting_resources)
    
    assert container['env'][0]['value'] == 'config-value'
    assert 'valueFrom' not in container['env'][0]





def test_merge_supporting_resources_deployment(validator):
    resource = {
        'kind': 'Deployment',
        'spec': {
            'template': {
                'spec': {
                    'containers': [{'name': 'app'}]
                }
            }
        }
    }
    supporting_resources = {}
    
    with patch.object(validator, '_merge_pod_supporting_resources') as mock_merge:
        validator._merge_supporting_resources(resource, supporting_resources)
        mock_merge.assert_called_once()


def test_merge_supporting_resources_pod(validator):
    resource = {
        'kind': 'Pod',
        'spec': {
            'containers': [{'name': 'app'}]
        }
    }
    supporting_resources = {}
    
    with patch.object(validator, '_merge_pod_supporting_resources') as mock_merge:
        validator._merge_supporting_resources(resource, supporting_resources)
        mock_merge.assert_called_once()


def test_count_value_lines_simple_dict(validator):
    """Test counting lines in a simple dictionary"""
    value = {'key1': 'value1', 'key2': 'value2'}
    details = {
        'dict_keys': 0, 'list_items': 0,
        'string_lines': 0, 'multiline_strings': 0,
        'primitive_values': 0, 'items': []
    }
    
    count = validator.count_value_lines(value, details=details)
    
    # Should count 2 string values (value1, value2)
    assert count == 2
    assert details['string_lines'] == 2


def test_count_value_lines_nested_dict(validator):
    """Test counting lines in a nested dictionary"""
    value = {
        'spec': {
            'replicas': 3,
            'template': {
                'metadata': {'name': 'app'}
            }
        }
    }
    details = {
        'dict_keys': 0, 'list_items': 0,
        'string_lines': 0, 'multiline_strings': 0,
        'primitive_values': 0, 'items': []
    }
    
    count = validator.count_value_lines(value, details=details)
    
    # Counts: spec key (1), template key (1), metadata key (1), replicas value (1), name value (1) = 5
    assert count == 5
    assert details['dict_keys'] == 3  # spec, template, and metadata all contain dict values
    assert details['primitive_values'] == 1  # replicas=3 (int)
    assert details['string_lines'] == 1  # name='app' (string)


def test_count_value_lines_list(validator):
    """Test counting lines in a list"""
    value = ['item1', 'item2', 'item3']
    details = {
        'dict_keys': 0, 'list_items': 0,
        'string_lines': 0, 'multiline_strings': 0,
        'primitive_values': 0, 'items': []
    }
    
    count = validator.count_value_lines(value, details=details)
    
    assert count == 3
    assert details['list_items'] == 3
    assert details['string_lines'] == 3


def test_count_value_lines_multiline_string(validator):
    """Test counting lines in a multiline string"""
    value = "line1\nline2\nline3"
    details = {
        'dict_keys': 0, 'list_items': 0,
        'string_lines': 0, 'multiline_strings': 0,
        'primitive_values': 0, 'items': []
    }
    
    count = validator.count_value_lines(value, details=details)
    
    assert count == 3
    assert details['string_lines'] == 3
    assert details['multiline_strings'] == 1


def test_count_cluster_lines_single_microservice(validator):
    """Test counting total lines in a cluster with one microservice"""
    cluster = {
        'test-service': {
            'deployment': {
                'apiVersion': 'apps/v1',
                'kind': 'Deployment',
                'metadata': {'name': 'test-service'},
                'spec': {'replicas': 3}
            },
            'service': {
                'apiVersion': 'v1',
                'kind': 'Service',
                'spec': {'type': 'ClusterIP'}
            }
        }
    }
    
    total = validator.count_cluster_lines(cluster)
    
    # Breakdown:
    # deployment: apiVersion(1) + kind(1) + metadata key(1) + name(1) + spec key(1) + replicas(1) = 6
    # service: apiVersion(1) + kind(1) + spec key(1) + type(1) = 4
    # Total: 6 + 4 = 10
    assert total == 10


def test_count_cluster_lines_multiple_microservices(validator):
    """Test counting total lines in a cluster with multiple microservices"""
    cluster = {
        'service1': {
            'deployment': {
                'metadata': {'name': 'service1'},
                'spec': {'replicas': 2}
            }
        },
        'service2': {
            'deployment': {
                'metadata': {'name': 'service2'},
                'spec': {'replicas': 5}
            }
        }
    }
    
    total = validator.count_cluster_lines(cluster)
    
    # Each deployment: metadata key(1) + name(1) + spec key(1) + replicas(1) = 4
    # service1: 4 lines
    # service2: 4 lines
    # Total: 4 + 4 = 8
    assert total == 8


def test_count_cluster_lines_empty_cluster(validator):
    """Test counting lines in an empty cluster"""
    cluster = {}
    
    total = validator.count_cluster_lines(cluster)
    
    assert total == 0


def test_count_cluster_lines_bug_fix_verification(validator):
    """
    Test that verifies the bug fix: total should NOT be multiplied 
    by the number of resources in each microservice.
    
    This test would have failed before the bug fix because the old code
    was adding ms_total inside the resource loop, causing incorrect multiplication.
    """
    cluster = {
        'web-service': {
            'deployment': {
                'spec': {'replicas': 1}
            },
            'service': {
                'spec': {'type': 'ClusterIP'}
            },
            'configmap': {
                'data': {'key': 'value'}
            }
        }
    }
    
    total = validator.count_cluster_lines(cluster)
    
    # Correct calculation (AFTER bug fix):
    # deployment: spec key(1) + replicas value(1) = 2
    # service: spec key(1) + type value(1) = 2
    # configmap: data key(1) + key value(1) = 2
    # Total: 2 + 2 + 2 = 6
    #
    # WRONG calculation (BEFORE bug fix):
    # After deployment: total += 2 → total = 2
    # After service: total += (2+2) = 4 → total = 6
    # After configmap: total += (2+2+2) = 6 → total = 12
    # This would have given 12 instead of 6!
    
    assert total == 6, f"Expected 6 lines, but got {total}. The bug may have returned!"


def test_count_diff_lines_with_additions(validator):
    """Test counting lines when there are additions"""
    diff_result = {
        'resources_extra': {
            'test-service': [
                {
                    'path': 'test-service//deployment//spec//replicas',
                    'value': 3
                },
                {
                    'path': 'test-service//service//spec//type',
                    'value': 'LoadBalancer'
                }
            ]
        },
        'resources_missing': {},
        'resource_differences': {}
    }
    
    added, removed, modified, report = validator.count_diff_lines(diff_result, verbose=False)
    
    # Two primitive values added: 3 (int) and 'LoadBalancer' (string)
    assert added == 2
    assert removed == 0
    assert modified == 0
    assert report['additions']['total'] == 2
    assert report['additions']['by_resource']['test-service'] == 2


def test_count_diff_lines_with_removals(validator):
    """Test counting lines when there are removals"""
    diff_result = {
        'resources_extra': {},
        'resources_missing': {
            'redis-cart': {
                'path': 'redis-cart',
                'value': {
                    'deployment': {
                        'metadata': {'name': 'redis'},
                        'spec': {'replicas': 1}
                    }
                }
            }
        },
        'resource_differences': {}
    }
    
    added, removed, modified, report = validator.count_diff_lines(diff_result, verbose=False)
    
    # deployment key(1) + metadata key(1) + name value(1) + spec key(1) + replicas value(1) = 5
    assert added == 0
    assert removed == 5
    assert modified == 0
    assert report['removals']['total'] == 5
    assert report['removals']['by_resource']['redis-cart'] == 5


def test_count_diff_lines_with_modifications(validator):
    """Test counting lines when there are modifications"""
    diff_result = {
        'resources_extra': {},
        'resources_missing': {},
        'resource_differences': {
            'details': [
                {
                    'path': 'details//deployment//spec//replicas',
                    'value': 1,
                    'reference_value': 2,
                    'analyzed_value': 1
                },
                {
                    'path': 'reviews//deployment//spec//template//spec//containers//0//env//0//value',
                    'value': 'false',
                    'reference_value': 'true',
                    'analyzed_value': 'false'
                }
            ]
        }
    }
    
    added, removed, modified, report = validator.count_diff_lines(diff_result, verbose=False)
    
    # Two primitive values modified: 1 (int) and 'false' (string)
    assert added == 0
    assert removed == 0
    assert modified == 2
    assert report['modifications']['total'] == 2
    assert report['modifications']['by_resource']['details'] == 2


def test_count_diff_lines_mixed_changes(validator):
    """Test counting lines with mixed additions, removals, and modifications"""
    diff_result = {
        'resources_extra': {
            'new-service': [
                {'path': 'new-service//deployment', 'value': {'spec': {'replicas': 1}}}
            ]
        },
        'resources_missing': {
            'old-service': [
                {'path': 'old-service//service', 'value': {0: {'spec': {'type': 'ClusterIP'}}}}
            ]
        },
        'resource_differences': {
            'modified-service': [
                {'path': 'modified-service//deployment//spec//replicas', 'value': 5}
            ]
        }
    }
    
    added, removed, modified, report = validator.count_diff_lines(diff_result, verbose=False)
    
    # Added: spec key(1) + replicas value(1) = 2
    assert added == 2
    # Removed: spec key(1) + type value(1) = 2
    assert removed == 2
    # Modified: replicas value(1) = 1
    assert modified == 1
    assert report['additions']['total'] == 2
    assert report['removals']['total'] == 2
    assert report['modifications']['total'] == 1
    assert report['additions']['by_resource']['new-service'] == 2
    assert report['removals']['by_resource']['old-service'] == 2
    assert report['modifications']['by_resource']['modified-service'] == 1


def test_structure_diff_with_identical_clusters(validator):
    """Test structure diff with identical clusters"""
    cluster = {
        'test-service': {
            'deployment': {
                'metadata': {'name': 'test'},
                'spec': {'replicas': 3}
            }
        }
    }
    
    diff = validator._structure_diff(cluster, cluster)
    
    assert len(diff['resources_extra']) == 0
    assert len(diff['resources_missing']) == 0
    assert len(diff['resource_differences']) == 0


def test_structure_diff_with_extra_resource(validator):
    """Test structure diff when analyzed has extra resources"""
    reference = {
        'service1': {
            'deployment': {'spec': {'replicas': 1}}
        }
    }
    analyzed = {
        'service1': {
            'deployment': {'spec': {'replicas': 1}}
        },
        'service2': {
            'deployment': {'spec': {'replicas': 2}}
        }
    }
    
    diff = validator._structure_diff(analyzed, reference)
    
    assert 'service2' in diff['resources_extra']
    assert len(diff['resources_missing']) == 0


def test_structure_diff_with_missing_resource(validator):
    """Test structure diff when analyzed is missing resources"""
    reference = {
        'service1': {'deployment': {'spec': {'replicas': 1}}},
        'service2': {'deployment': {'spec': {'replicas': 2}}}
    }
    analyzed = {
        'service1': {'deployment': {'spec': {'replicas': 1}}}
    }
    
    diff = validator._structure_diff(analyzed, reference)
    
    assert 'service2' in diff['resources_missing']
    assert len(diff['resources_extra']) == 0


def test_structure_diff_with_value_difference(validator):
    """Test structure diff when values differ"""
    reference = {
        'service1': {
            'deployment': {'spec': {'replicas': 3}}
        }
    }
    analyzed = {
        'service1': {
            'deployment': {'spec': {'replicas': 1}}
        }
    }
    
    diff = validator._structure_diff(analyzed, reference)
    
    assert 'service1' in diff['resource_differences']
    assert len(diff['resource_differences']['service1']) > 0


def test_manifest_similarity_identical(validator):
    """Test similarity calculation for identical manifests"""
    manifest1 = '{"spec": {"replicas": 3}}'
    manifest2 = '{"spec": {"replicas": 3}}'
    
    similarity = validator.manifest_similarity(manifest1, manifest2)
    
    assert similarity == 1.0


def test_manifest_similarity_different(validator):
    """Test similarity calculation for different manifests"""
    manifest1 = '{"spec": {"replicas": 3}}'
    manifest2 = '{"spec": {"replicas": 5}}'
    
    similarity = validator.manifest_similarity(manifest1, manifest2)
    
    assert 0 < similarity < 1.0


def test_manifest_similarity_empty(validator):
    """Test similarity calculation with empty strings"""
    similarity = validator.manifest_similarity('', '')
    
    assert similarity == 0.0


def test_analyze_diff_for_levenshtein(validator):
    """Test the complete diff analysis for Levenshtein calculation"""
    diff_result = {
        'resources_extra': {
            'new-service': [
                {'path': 'new-service//deployment', 'value': {'spec': {'replicas': 2}}}
            ]
        },
        'resources_missing': {},
        'resource_differences': {
            'modified-service': [
                {'path': 'modified-service//deployment//spec//replicas', 'value': 5}
            ]
        }
    }
    
    result = validator.analyze_diff_for_levenshtein(diff_result, verbose=False)
    
    assert 'added_lines' in result
    assert 'removed_lines' in result
    assert 'modified_lines' in result
    assert 'total_operations' in result
    assert 'detailed_report' in result
    assert 'resources_affected' in result
    assert result['total_operations'] == result['added_lines'] + result['removed_lines'] + result['modified_lines']


def test_real_world_diff_scenario(validator):
    """Test a realistic diff scenario matching the CSV output from the user"""
    # Simulate the differences from the user's CSV:
    # - details: replicas 2->1
    # - productpage: service type LoadBalancer->ClusterIP
    # - reviews: replicas 5->1, env value true->false
    
    reference = {
        'details': {
            'deployment': {
                'spec': {
                    'replicas': 2,
                    'template': {
                        'spec': {
                            'containers': [{'name': 'details', 'image': 'details:v1'}]
                        }
                    }
                }
            }
        },
        'productpage': {
            'service': {
                'spec': {
                    'type': 'LoadBalancer',
                    'ports': [{'port': 9080}]
                }
            }
        },
        'reviews': {
            'deployment': {
                'spec': {
                    'replicas': 5,
                    'template': {
                        'spec': {
                            'containers': [{
                                'name': 'reviews',
                                'env': [{'name': 'ENABLE_FEATURE', 'value': 'true'}]
                            }]
                        }
                    }
                }
            }
        }
    }
    
    analyzed = {
        'details': {
            'deployment': {
                'spec': {
                    'replicas': 1,  # Changed from 2
                    'template': {
                        'spec': {
                            'containers': [{'name': 'details', 'image': 'details:v1'}]
                        }
                    }
                }
            }
        },
        'productpage': {
            'service': {
                'spec': {
                    'type': 'ClusterIP',  # Changed from LoadBalancer
                    'ports': [{'port': 9080}]
                }
            }
        },
        'reviews': {
            'deployment': {
                'spec': {
                    'replicas': 1,  # Changed from 5
                    'template': {
                        'spec': {
                            'containers': [{
                                'name': 'reviews',
                                'env': [{'name': 'ENABLE_FEATURE', 'value': 'false'}]  # Changed from true
                            }]
                        }
                    }
                }
            }
        }
    }
    
    # Generate the diff
    diff = validator._structure_diff(analyzed, reference)
    
    # Verify that differences were detected
    assert 'details' in diff['resource_differences']
    assert 'productpage' in diff['resource_differences']
    assert 'reviews' in diff['resource_differences']
    
    # Count the lines
    result = validator.analyze_diff_for_levenshtein(diff, verbose=False)
    
    # Should have 4 modifications (replicas x2, service type, env value)
    assert result['modified_lines'] == 4
    assert result['added_lines'] == 0
    assert result['removed_lines'] == 0
    assert result['resources_affected'] == 3  # details, productpage, reviews
    
    # Verify Levenshtein similarity
    ref_json = json.dumps(reference, sort_keys=True)
    analyzed_json = json.dumps(analyzed, sort_keys=True)
    similarity = validator.manifest_similarity(ref_json, analyzed_json)
    
    # Should be high similarity since only 4 values changed
    assert 0.9 < similarity < 1.0
