import os
import os
import pytest
import tempfile
import yaml
from unittest.mock import Mock, patch, MagicMock
from validation.manifests_validator import ManifestsValidator


@pytest.fixture
def validator():
    embeddings_engine = Mock()
    return ManifestsValidator(embeddings_engine)


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


def test_generate_no_path_cluster(validator):
    llm_manifests_path = "../../output/manifests/llm/k8s"
    heuristics_manifests_path = "../../output/manifests/manual/k8s"

    with pytest.raises(NotADirectoryError):
        validator._generate_cluster(llm_manifests_path)

    with pytest.raises(NotADirectoryError):
        validator._generate_cluster(heuristics_manifests_path)


def test_generate_with_path_cluster(validator):
    llm_manifests_path = os.path.join(
        os.path.dirname(__file__), "../../output/manifests/llm/final_manifests/k8s"
    )
    heuristics_manifests_path = os.path.join(
        os.path.dirname(__file__), "../../output/manifests/manual/k8s"
    )

    if os.path.exists(llm_manifests_path) and os.path.exists(heuristics_manifests_path):
        llm_cluster = validator._generate_cluster(llm_manifests_path)
        heuristics_cluster = validator._generate_cluster(heuristics_manifests_path)
        
        assert llm_cluster != {}
        assert heuristics_cluster != {}


def test_generate_cluster_empty_directory(validator, temp_dir):
    cluster = validator._generate_cluster(temp_dir)
    assert cluster == {}


def test_generate_cluster_with_yaml_files(validator, temp_dir, sample_yaml_content):
    # Create YAML files
    with open(os.path.join(temp_dir, 'deployment.yaml'), 'w') as f:
        yaml.dump(sample_yaml_content['deployment'], f)
    
    with open(os.path.join(temp_dir, 'config.yml'), 'w') as f:
        yaml.dump(sample_yaml_content['configmap'], f)
    
    cluster = validator._generate_cluster(temp_dir)
    
    assert 'test-app' in cluster
    assert 'deployment' in cluster['test-app']


def test_generate_cluster_invalid_yaml(validator, temp_dir):
    # Create invalid YAML file
    with open(os.path.join(temp_dir, 'invalid.yaml'), 'w') as f:
        f.write('invalid: yaml: content: [')
    
    with pytest.raises(ValueError, match="Error parsing YAML file"):
        validator._generate_cluster(temp_dir)


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


def test_validate_resources_identical(validator):
    summary = {"resources_analyzed": 0, "resources_extra": 0, "resources_missing": [], "differences": {}, "similarities": {}}
    heuristics_resource = {'spec': {'replicas': 3, 'image': 'nginx'}}
    llm_resource = {'spec': {'replicas': 3, 'image': 'nginx'}}
    
    result = validator._validate_resources(heuristics_resource, llm_resource, summary, "test")
    
    assert result is True
    assert len(summary["resources_missing"]) == 0
    assert len(summary["differences"]) == 0


def test_validate_resources_missing_key(validator):
    summary = {"resources_analyzed": 0, "resources_extra": 0, "resources_missing": [], "differences": {}, "similarities": {}}
    heuristics_resource = {'spec': {'replicas': 3, 'image': 'nginx'}}
    llm_resource = {'spec': {'replicas': 3}}
    
    result = validator._validate_resources(heuristics_resource, llm_resource, summary, "test")
    
    assert result is False
    assert len(summary["resources_missing"]) > 0


def test_validate_resources_different_values(validator):
    summary = {"resources_analyzed": 0, "resources_extra": 0, "resources_missing": [], "differences": {}, "similarities": {}}
    heuristics_resource = {'spec': {'replicas': 3}}
    llm_resource = {'spec': {'replicas': 5}}
    
    result = validator._validate_resources(heuristics_resource, llm_resource, summary, "test")
    
    assert result is False
    assert len(summary["differences"]) > 0


def test_validate_microservices_missing_service(validator):
    validator.embeddings_engine.compare_words.return_value = 0.5
    
    heuristics_cluster = {'service1': {'deployment': {}}}
    llm_cluster = {}
    
    with patch.object(validator, '_validate_resources') as mock_validate:
        validator._validate_microservices(llm_cluster, heuristics_cluster)
        # Should not call _validate_resources for missing services
        mock_validate.assert_not_called()


def test_validate_microservices_similar_service_name(validator):
    validator.embeddings_engine.compare_words.return_value = 0.9
    
    heuristics_cluster = {'service1': {'deployment': {}}}
    llm_cluster = {'service-1': {'deployment': {}}}
    
    with patch.object(validator, '_validate_resources', return_value=True) as mock_validate:
        validator._validate_microservices(llm_cluster, heuristics_cluster)


def test_validate_method(validator):
    with patch.object(validator, '_generate_cluster') as mock_generate:
        with patch.object(validator, '_validate_microservices') as mock_validate:
            mock_generate.return_value = {}
            
            validator.validate("llm_path", "heuristics_path")
            
            assert mock_generate.call_count == 2
            mock_validate.assert_called_once()


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
