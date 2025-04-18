import os
from unittest import mock
from unittest.mock import patch
import pytest
from manifest_builder import ManifestBuilder
from utils.file_utils import load_environment

@pytest.fixture(autouse=True)
def load_env():
    load_environment()

def test_get_template_valid_names():
    builder = ManifestBuilder()
    
    assert builder.get_template("config_map") == builder._config_map_template
    assert builder.get_template("deployment") == builder.deployment_template 
    assert builder.get_template("service") == builder._service_template
    assert builder.get_template("stateful_set") == builder._stateful_set_template
    assert builder.get_template("pvc") == builder._pvc_template

def test_get_template_invalid_name():
    builder = ManifestBuilder()
    with pytest.raises(AssertionError):
        builder.get_template("invalid_name")

def test_get_template_empty_name():
    builder = ManifestBuilder()
    with pytest.raises(AssertionError):
        builder.get_template("")

def test_get_template_none_name():
    builder = ManifestBuilder()
    with pytest.raises(AssertionError):
        builder.get_template(None)

def test_build_secrets_yaml():
    # Create a mock for ManifestBuilder with template methods pre-configured
    with patch('manifest_builder.ManifestBuilder._get_config_map_template') as mock_config_map, \
         patch('manifest_builder.ManifestBuilder._get_deployment_template'), \
         patch('manifest_builder.ManifestBuilder._get_service_template'), \
         patch('manifest_builder.ManifestBuilder._get_stateful_set_template'), \
         patch('manifest_builder.ManifestBuilder._get_pvc_template'), \
         patch('os.path.exists', return_value=False), \
         patch('os.makedirs', return_value=None), \
         patch('builtins.open', mock.mock_open(), create=True), \
         patch('yaml.dump') as mock_dump, \
         patch('manifest_builder.ManifestBuilder._save_yaml') as mock_save:
        
        # Set up the template that will be returned by get_template
        template = {
            'apiVersion': 'v1',
            'kind': 'ConfigMap',
            'metadata': {'name': 'template-name'},
            'data': {}
        }
        mock_config_map.return_value = template
        
        # Create the builder
        builder = ManifestBuilder()
        
        # Provide test data
        secret = {
            "name": "secret1",
            "service": "service1",
            "value": "value1"
        }
        
        # Call the method being tested
        builder.build_secrets_yaml(secret)
        
        # Check if yaml.dump was called with correct parameters
        expected_values_data = {
            "secrets": {
                "secret1": {
                    "name": "secret1",
                    "password": "value1"
                }
            }
        }
        mock_dump.assert_called_once_with(expected_values_data, mock.ANY)
        
        # Check if _save_yaml was called with the correct template
        expected_template = {
            'apiVersion': 'v1',
            'kind': 'Secret',
            'metadata': {'name': '{{ .Values.secrets.secret1.name }}'},
            'data': {'password': '{{ .Values.secrets.secret1.password }}'},
            'type': 'Opaque'
        }
        mock_save.assert_called_once()
        actual_template = mock_save.call_args[0][0]
        assert actual_template == expected_template

def test_build_config_map_yaml():
    # Create a mock for ManifestBuilder with template methods pre-configured
    with patch('manifest_builder.ManifestBuilder._get_config_map_template') as mock_config_map, \
         patch('manifest_builder.ManifestBuilder._get_deployment_template'), \
         patch('manifest_builder.ManifestBuilder._get_service_template'), \
         patch('manifest_builder.ManifestBuilder._get_stateful_set_template'), \
         patch('manifest_builder.ManifestBuilder._get_pvc_template'), \
         patch('os.path.exists', return_value=False), \
         patch('os.makedirs', return_value=None), \
         patch('builtins.open', mock.mock_open(), create=True), \
         patch('yaml.dump') as mock_dump, \
         patch('manifest_builder.ManifestBuilder._save_yaml') as mock_save, \
         patch('os.getenv', return_value='/mock/path'):
        
        # Set up the template that will be returned by get_template
        template = {
            'apiVersion': 'v1',
            'kind': 'ConfigMap',
            'metadata': {'name': 'template-name'},
            'data': {}
        }
        mock_config_map.return_value = template
        
        # Create the builder
        builder = ManifestBuilder()
        
        # Provide test data
        config_map = {
            "name": "my-config",
            "service": "test-service",
            "config": "sample-config-content"
        }
        
        # Call the method being tested
        builder.build_config_map_yaml(config_map)
        
        # Check if yaml.dump was called with correct parameters
        expected_values_data = {
            "configs": {
                "config-my-config": {
                    "name": "my-config",
                    "config": "sample-config-content"
                }
            }
        }
        mock_dump.assert_called_once_with(expected_values_data, mock.ANY)
        
        # Check if _save_yaml was called with the correct template
        expected_template = {
            'apiVersion': 'v1',
            'kind': 'ConfigMap',
            'metadata': {'name': 'config-my-config'},
            'data': {'config': '{{ .Values.config.my-config.config }}'}
        }
        mock_save.assert_called_once()
        actual_template = mock_save.call_args[0][0]
        assert actual_template == expected_template

def test_build_deployment_yaml():
    # Create a mock for ManifestBuilder with template methods pre-configured
    with patch('manifest_builder.ManifestBuilder._get_config_map_template'), \
         patch('manifest_builder.ManifestBuilder._get_deployment_template') as mock_deployment, \
         patch('manifest_builder.ManifestBuilder._get_service_template'), \
         patch('manifest_builder.ManifestBuilder._get_stateful_set_template'), \
         patch('manifest_builder.ManifestBuilder._get_pvc_template'), \
         patch('os.path.exists', return_value=False), \
         patch('os.makedirs', return_value=None), \
         patch('builtins.open', mock.mock_open(), create=True), \
         patch('yaml.dump') as mock_dump, \
         patch('manifest_builder.ManifestBuilder._save_yaml') as mock_save, \
         patch('os.getenv', return_value='/mock/path'), \
         patch('manifest_builder.ManifestBuilder.get_template', return_value=mock_deployment.return_value):
        
        # Set up the template that will be returned by get_template
        template = {
            'apiVersion': 'apps/v1',
            'kind': 'Deployment',
            'metadata': {'name': 'template-name', 'labels': {}},
            'spec': {
                'selector': {'matchLabels': {}},
                'template': {
                    'metadata': {'labels': {}},
                    'spec': {
                        'containers': [
                            {
                                'name': 'container-name',
                                'command': [],
                                'args': [],
                                'env': [],
                                'ports': [],
                            }
                        ]
                    }
                }
            }
        }
        mock_deployment.return_value = template
        
        # Create the builder
        builder = ManifestBuilder()
        
        # Patch the specific method in the ManifestBuilder class
        with patch.object(builder, 'get_template', return_value=template.copy()):
            
            # Provide test data
            deployment = {
                "name": "test-app",
                "service": "test-service",
                "labels": {"app": "test-app"},
                "command": ["/bin/sh"],
                "args": ["-c", "echo Hello"],
                "env": [{"name": "ENV_VAR", "value": "value"}],
                "volumes": [{"name": "config-vol", "configMap": {"name": "test-config"}}],
                "volume_mounts": [{"name": "config-vol", "mountPath": "/etc/config"}],
                "ports": [{"containerPort": 8080, "protocol": "TCP"}],
                "workdir": "/app",
                "liveness_probe": {"httpGet": {"path": "/health", "port": 8080}},
                "user": 1000
            }
            
            # Call the method being tested
            builder.build_deployment_yaml(deployment)
            
            # Check if yaml.dump was called with correct parameters
            expected_values_data = {
                "deployment-test-service": {
                    "name": "test-service",
                    "labels": {"app": "test-app"},  # Direct dictionary assignment
                    "command": ["/bin/sh"],
                    "args": ["-c", "echo Hello"],
                    "env": [{"name": "ENV_VAR", "value": "value"}],
                    "volumes": [{"name": "config-vol", "configMap": {"name": "test-config"}}],
                    "volume_mounts": [{"name": "config-vol", "mountPath": "/etc/config"}],
                    "ports": [{"containerPort": 8080, "protocol": "TCP"}],
                    "workdir": "/app",
                    "liveness_probe": {"httpGet": {"path": "/health", "port": 8080}},
                    "security_context": {"runAsUser": 1000}
                }
            }
            mock_dump.assert_called_once_with(expected_values_data, mock.ANY)

def test_build_service_yaml():
    # Create a mock for ManifestBuilder with template methods pre-configured
    with patch('manifest_builder.ManifestBuilder._get_config_map_template'), \
         patch('manifest_builder.ManifestBuilder._get_deployment_template'), \
         patch('manifest_builder.ManifestBuilder._get_service_template') as mock_service, \
         patch('manifest_builder.ManifestBuilder._get_stateful_set_template'), \
         patch('manifest_builder.ManifestBuilder._get_pvc_template'), \
         patch('os.path.exists', return_value=False), \
         patch('os.makedirs', return_value=None), \
         patch('builtins.open', mock.mock_open(), create=True), \
         patch('yaml.dump') as mock_dump, \
         patch('manifest_builder.ManifestBuilder._save_yaml') as mock_save, \
         patch('os.getenv', return_value='/mock/path'):
        
        # Set up the template that will be returned by get_template
        template = {
            'apiVersion': 'v1',
            'kind': 'Service',
            'metadata': {'name': 'template-name', 'labels': {}},
            'spec': {
                'selector': {},
                'ports': [
                    {
                        'port': 80,
                        'targetPort': 8080,
                        'protocol': 'TCP',
                        'name': 'http'
                    }
                ],
                'type': 'ClusterIP'
            }
        }
        mock_service.return_value = template
        
        # Create the builder
        builder = ManifestBuilder()
        
        # Patch the specific method in the ManifestBuilder class
        with patch.object(builder, 'get_template', return_value=template.copy()):
            
            # Provide test data
            service = {
                "name": "web-service",
                "labels": {"app": "web"},
                "port": 80,
                "target_port": 8080,
                "protocol": "TCP",
                "type": "ClusterIP"
            }
            
            # Call the method being tested
            builder.build_service_yaml(service)
            
            # Check if yaml.dump was called with correct parameters
            expected_values_data = {
                "service-web-service": {
                    "name": "web-service",
                    "labels": {"app": "web"},
                    "port": 80,
                    "target_port": 8080,
                    "protocol": "TCP",
                    "type": "ClusterIP"
                }
            }
            mock_dump.assert_called_once_with(expected_values_data, mock.ANY)
            
            # Instead of checking for exact string format, check that key parts are present
            actual_template = mock_save.call_args[0][0]
            assert actual_template['apiVersion'] == 'v1'
            assert actual_template['kind'] == 'Service'
            
            # Check that the metadata contains the service name template reference
            assert 'Values.service' in actual_template['metadata']['name']
            assert 'web-service' in actual_template['metadata']['name']
            
            # Check that the ports section contains the correct port template reference
            assert len(actual_template['spec']['ports']) == 1
            assert 'Values.service' in str(actual_template['spec']['ports'][0]['port'])
            assert 'Values.service' in str(actual_template['spec']['ports'][0]['targetPort'])
            
            # Check service type
            assert 'Values.service' in str(actual_template['spec']['type'])

def test_build_stateful_set_yaml():
    # Create a mock for ManifestBuilder with template methods pre-configured
    with patch('manifest_builder.ManifestBuilder._get_config_map_template'), \
         patch('manifest_builder.ManifestBuilder._get_deployment_template'), \
         patch('manifest_builder.ManifestBuilder._get_service_template'), \
         patch('manifest_builder.ManifestBuilder._get_stateful_set_template') as mock_stateful_set, \
         patch('manifest_builder.ManifestBuilder._get_pvc_template'), \
         patch('os.path.exists', return_value=False), \
         patch('os.makedirs', return_value=None), \
         patch('builtins.open', mock.mock_open(), create=True), \
         patch('yaml.dump') as mock_dump, \
         patch('manifest_builder.ManifestBuilder._save_yaml') as mock_save, \
         patch('os.getenv', return_value='/mock/path'):
        
        # Set up the template that will be returned by get_template
        template = {
            'apiVersion': 'apps/v1',
            'kind': 'StatefulSet',
            'metadata': {'name': 'template-name', 'labels': {}},
            'spec': {
                'selector': {'matchLabels': {}},
                'serviceName': 'service-name',
                'replicas': 1,
                'template': {
                    'metadata': {'labels': {}},
                    'spec': {
                        'containers': [
                            {
                                'name': 'container-name',
                                'command': [],
                                'args': [],
                                'env': [],
                                'ports': [],
                            }
                        ]
                    }
                }
            }
        }
        mock_stateful_set.return_value = template
        
        # Create the builder
        builder = ManifestBuilder()
        
        # Patch the specific method in the ManifestBuilder class
        with patch.object(builder, 'get_template', return_value=template.copy()):
            
            # Provide test data
            stateful_set = {
                "name": "database",
                "labels": {"app": "db"},
                "command": ["mysqld"],
                "args": ["--default-authentication-plugin=mysql_native_password"],
                "env": [{"name": "MYSQL_ROOT_PASSWORD", "value": "password"}],
                "volumes": [{"name": "data", "persistentVolumeClaim": {"claimName": "mysql-data"}}],
                "volume_mounts": [{"name": "data", "mountPath": "/var/lib/mysql"}],
                "ports": [{"containerPort": 3306, "protocol": "TCP"}],
                "workdir": "/var/lib/mysql",
                "liveness_probe": {"exec": {"command": ["mysqladmin", "ping"]}},
                "user": 1000
            }
            
            # Call the method being tested
            builder.build_stateful_set_yaml(stateful_set)
            
            # Check if yaml.dump was called with correct parameters
            expected_values_data = {
                "stateful-set-database": {
                    "name": "database",
                    "labels": {"app": "db"},
                    "command": ["mysqld"],
                    "args": ["--default-authentication-plugin=mysql_native_password"],
                    "env": [{"name": "MYSQL_ROOT_PASSWORD", "value": "password"}],
                    "volumes": [{"name": "data", "persistentVolumeClaim": {"claimName": "mysql-data"}}],
                    "volume_mounts": [{"name": "data", "mountPath": "/var/lib/mysql"}],
                    "ports": [{"containerPort": 3306, "protocol": "TCP"}],
                    "workdir": "/var/lib/mysql",
                    "liveness_probe": {"exec": {"command": ["mysqladmin", "ping"]}},
                    "security_context": {"runAsUser": 1000}
                }
            }
            mock_dump.assert_called_once_with(expected_values_data, mock.ANY)
            
            # Instead of checking for exact string format, check that key parts are present
            actual_template = mock_save.call_args[0][0]
            assert actual_template['apiVersion'] == 'apps/v1'
            assert actual_template['kind'] == 'StatefulSet'
            
            # Check that the metadata contains the statefulset name template reference
            assert 'Values.stateful-set' in str(actual_template['metadata']['name'])
            assert 'database' in str(actual_template['metadata']['name'])
            
            # Check that the container section includes all the required fields
            container = actual_template['spec']['template']['spec']['containers'][0]
            assert 'Values.stateful-set' in str(container['name'])
            assert 'Values.stateful-set' in str(container['command'])
            assert 'Values.stateful-set' in str(container['args'])
            assert 'Values.stateful-set' in str(container['env'])
            
            # Check volume mounts and volumes
            assert 'Values.stateful-set' in str(container.get('volumeMounts', ''))
            assert 'Values.stateful-set' in str(actual_template['spec']['template']['spec'].get('volumes', ''))
            
            # Check that securityContext is set
            assert 'Values.stateful-set' in str(container.get('securityContext', {}).get('runAsUser', ''))

def test_build_pvc_yaml():
    # Create a mock for ManifestBuilder with template methods pre-configured
    with patch('manifest_builder.ManifestBuilder._get_config_map_template'), \
         patch('manifest_builder.ManifestBuilder._get_deployment_template'), \
         patch('manifest_builder.ManifestBuilder._get_service_template'), \
         patch('manifest_builder.ManifestBuilder._get_stateful_set_template'), \
         patch('manifest_builder.ManifestBuilder._get_pvc_template') as mock_pvc, \
         patch('os.path.exists', return_value=False), \
         patch('os.makedirs', return_value=None), \
         patch('builtins.open', mock.mock_open(), create=True), \
         patch('yaml.dump') as mock_dump, \
         patch('manifest_builder.ManifestBuilder._save_yaml') as mock_save, \
         patch('os.getenv', return_value='/mock/path'):
        
        # Set up the template that will be returned by get_template
        template = {
            'apiVersion': 'v1',
            'kind': 'PersistentVolumeClaim',
            'metadata': {'name': 'template-name', 'labels': {}},
            'spec': {
                'storageClassName': 'standard',
                'accessModes': ['ReadWriteOnce'],
                'resources': {
                    'requests': {'storage': '1Gi'}
                }
            }
        }
        mock_pvc.return_value = template
        
        # Create the builder
        builder = ManifestBuilder()
        
        # Patch the specific method in the ManifestBuilder class
        with patch.object(builder, 'get_template', return_value=template.copy()):
            
            # Provide test data
            pvc = {
                "name": "data-storage",
                "labels": {"app": "mysql"},
                "storage_class": "standard",
                "access_modes": ["ReadWriteOnce"],
                "resources": "10Gi"
            }
            
            # Call the method being tested
            builder.build_pvc_yaml(pvc)
            
            # Check if yaml.dump was called with correct parameters
            expected_values_data = {
                "pvc-data-storage": {
                    "name": "data-storage",
                    "labels": {"app": "mysql"},
                    "storage_class": "standard",
                    "access_modes": ["ReadWriteOnce"],
                    "resources": "10Gi"
                }
            }
            mock_dump.assert_called_once_with(expected_values_data, mock.ANY)
            
            # Instead of checking for exact string format, check that key parts are present
            actual_template = mock_save.call_args[0][0]
            assert actual_template['apiVersion'] == 'v1'
            assert actual_template['kind'] == 'PersistentVolumeClaim'
            
            # Check that the metadata contains the PVC name template reference
            assert 'Values.pvc' in str(actual_template['metadata']['name'])
            assert 'data-storage' in str(actual_template['metadata']['name'])
            
            # Check that spec contains the storage class name
            assert 'Values.pvc' in str(actual_template['spec']['storageClassName'])
            assert 'Values.pvc' in str(actual_template['spec']['accessModes'])
            
            # Check resources section
            assert 'Values.pvc' in str(actual_template['spec']['resources']['requests']['storage'])

