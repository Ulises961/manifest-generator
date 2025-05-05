import os
from unittest import mock
from unittest.mock import Mock, patch
import numpy as np
import pytest
import yaml
from embeddings.embeddings_engine import EmbeddingsEngine
from manifest_builder import ManifestBuilder
from utils.file_utils import load_environment


@pytest.fixture(autouse=True)
def load_env():
    load_environment()


@pytest.fixture
def mock_embeddings_engine():
    """Create a mock embeddings engine for testing."""
    engine = Mock()
    engine.encode = Mock(return_value=np.array([0.1, 0.2, 0.3]))
    engine.encode = Mock(return_value=np.array([0.1, 0.2, 0.3]))
    engine.compute_similarity = Mock(return_value=0.85)
    return engine


@pytest.fixture
def manifest_builder(mock_embeddings_engine):
    return ManifestBuilder(mock_embeddings_engine)


def test_get_template_valid_names(manifest_builder):

    assert (
        manifest_builder.get_template("config_map")
        == manifest_builder._config_map_template
    )
    assert (
        manifest_builder.get_template("deployment")
        == manifest_builder.deployment_template
    )
    assert (
        manifest_builder.get_template("service") == manifest_builder._service_template
    )
    assert (
        manifest_builder.get_template("stateful_set")
        == manifest_builder._stateful_set_template
    )
    assert manifest_builder.get_template("pvc") == manifest_builder._pvc_template


def test_get_template_invalid_name(manifest_builder):
    with pytest.raises(AssertionError):
        manifest_builder.get_template("invalid_name")


def test_get_template_empty_name(manifest_builder):
    with pytest.raises(AssertionError):
        manifest_builder.get_template("")


def test_get_template_none_name(manifest_builder):
    with pytest.raises(AssertionError):
        manifest_builder.get_template(None)


def test_build_secrets_yaml(manifest_builder):
    # Create a mock for ManifestBuilder with template methods pre-configured
    with patch(
        "manifest_builder.ManifestBuilder._get_config_map_template"
    ) as mock_config_map, patch(
        "manifest_builder.ManifestBuilder._get_deployment_template"
    ), patch(
        "manifest_builder.ManifestBuilder._get_service_template"
    ), patch(
        "manifest_builder.ManifestBuilder._get_stateful_set_template"
    ), patch(
        "manifest_builder.ManifestBuilder._get_pvc_template"
    ), patch(
        "os.path.exists", return_value=False
    ), patch(
        "os.makedirs", return_value=None
    ), patch(
        "builtins.open", mock.mock_open(), create=True
    ), patch(
        "manifest_builder.ManifestBuilder._save_yaml"
    ) as mock_save:

        # Remove the yaml.dump mock since we're not directly calling it
        # patch('yaml.dump') as mock_dump, <-- Remove this line

        # Set up the template that will be returned by get_template
        template = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "template-name"},
            "data": {},
        }
        mock_config_map.return_value = template

        # Provide test data
        secret = {"name": "secret1", "value": "value1"}

        # Call the method being tested
        manifest_builder.build_secrets_yaml(secret)

        # Check if _save_yaml was called with values.yaml data first
        expected_values_data = {
            "secrets": {"secret1": {"name": "secret1", "password": "value1"}}
        }
        # First call should be for values.yaml
        assert mock_save.call_count >= 1
        assert mock_save.call_args_list[0][0][0] == expected_values_data

        # Second call should be for the template
        expected_template = {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {"name": "{{ .Values.secrets.secret1.name }}"},
            "data": {"secret1": "{{ .Values.secrets.secret1.password }}"},
            "type": "Opaque",
        }
        assert mock_save.call_count >= 2
        second_call_template = mock_save.call_args_list[1][0][0]
        assert second_call_template["kind"] == "Secret"
        assert "{{ .Values.secrets.secret1.name }}" in str(
            second_call_template["metadata"]["name"]
        )
        assert "secret1" in second_call_template["data"]


def test_build_config_map_yaml(manifest_builder):
    # Create a mock for ManifestBuilder with template methods pre-configured
    with patch(
        "manifest_builder.ManifestBuilder._get_config_map_template"
    ) as mock_config_map, patch(
        "manifest_builder.ManifestBuilder._get_deployment_template"
    ), patch(
        "manifest_builder.ManifestBuilder._get_service_template"
    ), patch(
        "manifest_builder.ManifestBuilder._get_stateful_set_template"
    ), patch(
        "manifest_builder.ManifestBuilder._get_pvc_template"
    ), patch(
        "os.path.exists", return_value=False
    ), patch(
        "os.makedirs", return_value=None
    ), patch(
        "builtins.open", mock.mock_open(), create=True
    ), patch(
        "yaml.dump"
    ) as mock_dump, patch(
        "manifest_builder.ManifestBuilder._save_yaml"
    ) as mock_save, patch(
        "os.getenv", return_value="/mock/path"
    ):

        # Set up the template that will be returned by get_template
        template = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "template-name"},
            "data": {},
        }
        mock_config_map.return_value = template

        # Provide test data
        config_map = {"name": "my-config", "value": "sample-config-content"}

        # Call the method being tested
        manifest_builder.build_config_map_yaml(config_map)

        # Check if yaml.dump was called with correct parameters
        expected_values_data = {
            "config": {
                "my_config": {"name": "my_config", "value": "sample-config-content"}
            }
        }
        # First call should be for values.yaml
        assert mock_save.call_count >= 1
        assert mock_save.call_args_list[0][0][0] == expected_values_data

        # Check if _save_yaml was called with the correct template
        expected_template = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "my_config"},
            "data": {"my-config": "{{ .Values.config.my_config.value }}"},
        }

        assert mock_save.call_count >= 2
        second_call_template = mock_save.call_args_list[1][0][0]
        assert second_call_template == expected_template

def test_build_deployment_yaml(manifest_builder):
    # Create a mock for ManifestBuilder with template methods pre-configured
    with patch("manifest_builder.ManifestBuilder._get_config_map_template"), patch(
        "manifest_builder.ManifestBuilder._get_deployment_template"
    ) as mock_deployment, patch(
        "manifest_builder.ManifestBuilder._get_service_template"
    ), patch(
        "manifest_builder.ManifestBuilder._get_stateful_set_template"
    ), patch(
        "manifest_builder.ManifestBuilder._get_pvc_template"
    ), patch(
        "os.path.exists", return_value=False
    ), patch(
        "os.makedirs", return_value=None
    ), patch(
        "builtins.open", mock.mock_open(), create=True
    ), patch(
        "manifest_builder.ManifestBuilder._save_yaml"
    ) as mock_save, patch(
        "os.getenv", return_value="/mock/path"
    ), patch(
        "manifest_builder.ManifestBuilder.get_template",
        return_value=mock_deployment.return_value,
    ):

        # Set up the template that will be returned by get_template
        template = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "template-name", "labels": {}},
            "spec": {
                "selector": {"matchLabels": {}},
                "template": {
                    "metadata": {"labels": {}},
                    "spec": {
                        "containers": [
                            {
                                "name": "container-name",
                                "command": [],
                                "args": [],
                                "env": [],
                                "ports": [],
                            }
                        ]
                    },
                },
            },
        }
        mock_deployment.return_value = template

        # Patch the specific method in the ManifestBuilder class
        with patch.object(
            manifest_builder, "get_template", return_value=template.copy()
        ):

            # Provide test data
            deployment = {
                "name": "test-app",
                "labels": {"app": "test-app"},
                "command": ["/bin/sh"],
                "args": ["-c", "echo Hello"],
                "env": [{"name": "ENV_VAR", "value": "value"}],
                "volumes": [
                    {"name": "config-vol", "configMap": {"name": "test-config"}}
                ],
                "volume_mounts": [{"name": "config-vol", "mountPath": "/etc/config"}],
                "ports": [8080],
                "workdir": "/app",
                "liveness_probe": {"httpGet": {"path": "/health", "port": 8080}},
                "user": 1000,
            }

            # Call the method being tested
            manifest_builder.build_deployment_yaml(deployment)

            # Check if yaml.dump was called with correct parameters
            expected_values_data = {
                "deployment": {
                    "test_app": {
                        "name": "test-app",
                        "labels": {"app": "test-app"},
                        "command": ["/bin/sh"],
                        "args": ["-c", "echo Hello"],
                        "volumes": [
                            {"name": "config-vol", "configMap": {"name": "test-config"}}
                        ],
                        "volume_mounts": [
                            {"name": "config-vol", "mountPath": "/etc/config"}
                        ],
                        "ports": {"containerPort": 8080},
                        "workdir": "/app",
                        "liveness_probe": {
                            "httpGet": {"path": "/health", "port": 8080}
                        },
                        "user": 1000,
                    }
                }
            }

            # First call should be for values.yaml
            assert mock_save.call_count >= 1
            assert mock_save.call_args_list[0][0][0] == expected_values_data

            expected_template = {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {
                    "name": "{{ .Values.deployment.test_app.name }}",
                    "labels": "{{ .Values.deployment.test_app.labels }}",
                },
                "spec": {
                    "selector": {
                        "matchLabels": "{{ .Values.deployment.test_app.labels }}"
                    },
                    "template": {
                        "metadata": {
                            "labels": "{{ .Values.deployment.test_app.labels }}"
                        },
                        "spec": {
                            "containers": [
                                {
                                    "name": "{{ .Values.deployment.test_app.name }}",
                                    "command": "{{ .Values.deployment.test_app.command }}",
                                    "args": "{{ .Values.deployment.test_app.args }}",
                                    "env": [
                                        {
                                            "name": "ENV_VAR",
                                            "valueFrom": {
                                                "configMapKeyRef": {
                                                    "name": "env_var",
                                                    "key": "ENV_VAR",
                                                }
                                            },
                                        }
                                    ],
                                    "ports": "{{ .Values.deployment.test_app.ports }}",
                                    "securityContext": {
                                        "runAsUser": "{{ .Values.deployment.test_app.user }}"
                                    },
                                    "volumeMounts": "{{ .Values.deployment.test_app.volume_mounts }}",
                                    "workingDir": "{{ .Values.deployment.test_app.workdir }}",
                                    "livenessProbe": "{{ .Values.deployment.test_app.liveness_probe }}",
                                }
                            ],
                            "volumes": "{{ .Values.deployment.test_app.volumes }}",
                        },
                    },
                },
            }
            assert mock_save.call_count >= 2
            assert mock_save.call_args_list[1][0][0] == expected_template


def test_build_stateful_set_yaml_extended(manifest_builder):
    # Create a mock for ManifestBuilder with template methods pre-configured
    with patch("manifest_builder.ManifestBuilder._get_config_map_template"), patch(
        "manifest_builder.ManifestBuilder._get_deployment_template"
    ), patch("manifest_builder.ManifestBuilder._get_service_template"), patch(
        "manifest_builder.ManifestBuilder._get_stateful_set_template"
    ) as mock_stateful_set, patch(
        "manifest_builder.ManifestBuilder._get_pvc_template"
    ), patch(
        "os.path.exists", return_value=False
    ), patch(
        "os.makedirs", return_value=None
    ), patch(
        "builtins.open", mock.mock_open(), create=True
    ), patch(
        "manifest_builder.ManifestBuilder._save_yaml"
    ) as mock_save, patch(
        "os.getenv", return_value="/mock/path"
    ), patch(
        "manifest_builder.ManifestBuilder.get_template",
        return_value=mock_stateful_set.return_value,
    ):

        # Set up the template that will be returned by get_template
        template = {
            "apiVersion": "apps/v1",
            "kind": "StatefulSet",
            "metadata": {"name": "template-name", "labels": {}},
            "spec": {
                "selector": {"matchLabels": {}},
                "template": {
                    "metadata": {"labels": {}},
                    "spec": {
                        "containers": [
                            {
                                "name": "container-name",
                                "command": [],
                                "args": [],
                                "env": [],
                                "ports": [],
                            }
                        ]
                    },
                },
            },
        }
        mock_stateful_set.return_value = template

        # Patch the specific method in the ManifestBuilder class
        with patch.object(
            manifest_builder, "get_template", return_value=template.copy()
        ):

            # Provide test data
            stateful_set = {
                "name": "db-stateful",
                "labels": {"app": "database"},
                "command": ["mysqld"],
                "args": ["--default-authentication-plugin=mysql_native_password"],
                "env": [{"name": "MYSQL_ROOT_PASSWORD", "value": "secretpassword"}],
                "volumes": [
                    {
                        "name": "data-vol",
                        "persistentVolumeClaim": {"claimName": "mysql-data"},
                    }
                ],
                "volume_mounts": [{"name": "data-vol", "mountPath": "/var/lib/mysql"}],
                "ports": [3306],
                "workdir": "/var/lib/mysql",
                "liveness_probe": {"exec": {"command": ["mysqladmin", "ping"]}},
                "user": 999,
            }

            # Call the method being tested
            manifest_builder.build_stateful_set_yaml(stateful_set)

            # Check if yaml.dump was called with correct parameters
            expected_values_data = {
                "stateful-set": {
                    "db_stateful": {
                        "name": "db-stateful",
                        "labels": {"app": "database"},
                        "command": ["mysqld"],
                        "args": [
                            "--default-authentication-plugin=mysql_native_password"
                        ],
                        "volumes": [
                            {
                                "name": "data-vol",
                                "persistentVolumeClaim": {"claimName": "mysql-data"},
                            }
                        ],
                        "volume_mounts": [
                            {"name": "data-vol", "mountPath": "/var/lib/mysql"}
                        ],
                        "ports": [3306],
                        "workdir": "/var/lib/mysql",
                        "liveness_probe": {"exec": {"command": ["mysqladmin", "ping"]}},
                        "user": 999,
                    }
                }
            }

            # First call should be for values.yaml
            assert mock_save.call_count >= 1
            assert mock_save.call_args_list[0][0][0] == expected_values_data

            expected_template = {
                "apiVersion": "apps/v1",
                "kind": "StatefulSet",
                "metadata": {
                    "name": "{{ .Values.stateful-set.db_stateful.name }}",
                    "labels": "{{ .Values.stateful-set.db_stateful.labels }}",
                },
                "spec": {
                    "selector": {
                        "matchLabels": "{{ .Values.stateful-set.db_stateful.labels }}"
                    },
                    "template": {
                        "metadata": {
                            "labels": "{{ .Values.stateful-set.db_stateful.labels }}"
                        },
                        "spec": {
                            "containers": [
                                {
                                    "name": "{{ .Values.stateful-set.db_stateful.name }}",
                                    "command": "{{ .Values.stateful-set.db_stateful.command }}",
                                    "args": "{{ .Values.stateful-set.db_stateful.args }}",
                                    "env": [
                                        {
                                            "name": "MYSQL_ROOT_PASSWORD",
                                            "valueFrom": {
                                                "configMapKeyRef": {
                                                    "name": "mysql_root_password",
                                                    "key": "MYSQL_ROOT_PASSWORD",
                                                }
                                            },
                                        }
                                    ],
                                    "ports": "{{ .Values.stateful-set.db_stateful.ports }}",
                                    "securityContext": {
                                        "runAsUser": "{{ .Values.stateful-set.db_stateful.user }}"
                                    },
                                    "volumeMounts": "{{ .Values.stateful-set.db_stateful.volume_mounts }}",
                                    "workingDir": "{{ .Values.stateful-set.db_stateful.workdir }}",
                                    "livenessProbe": "{{ .Values.stateful-set.db_stateful.liveness_probe }}",
                                }
                            ],
                            "volumes": "{{ .Values.stateful-set.db_stateful.volumes }}",
                        },
                    },
                },
            }

            assert mock_save.call_count >= 2
            assert mock_save.call_args_list[1][0][0] == expected_template


def test_build_service_yaml(manifest_builder):
    # Create a mock for ManifestBuilder with template methods pre-configured
    with patch("manifest_builder.ManifestBuilder._get_config_map_template"), patch(
        "manifest_builder.ManifestBuilder._get_deployment_template"
    ), patch(
        "manifest_builder.ManifestBuilder._get_service_template"
    ) as mock_service, patch(
        "manifest_builder.ManifestBuilder._get_stateful_set_template"
    ), patch(
        "manifest_builder.ManifestBuilder._get_pvc_template"
    ), patch(
        "os.path.exists", return_value=False
    ), patch(
        "os.makedirs", return_value=None
    ), patch(
        "builtins.open", mock.mock_open(), create=True
    ), patch(
        "manifest_builder.ManifestBuilder._save_yaml"
    ) as mock_save, patch(
        "os.getenv", return_value="/mock/path"
    ):

        # Set up the template that will be returned by get_template
        template = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {"name": "template-name", "labels": {}},
            "spec": {
                "selector": {},
                "ports": [
                    {"port": 80, "targetPort": 8080, "protocol": "TCP", "name": "http"}
                ],
                "type": "ClusterIP",
            },
        }
        mock_service.return_value = template

        # Patch the specific method in the ManifestBuilder class
        with patch.object(
            manifest_builder, "get_template", return_value=template.copy()
        ):

            # Provide test data
            service = {
                "name": "web-service",
                "labels": {"app": "web"},
                "ports": [8080],
                "service-ports": [80, 443],
                "protocol": "TCP",
                "type": "ClusterIP",
            }

            # Call the method being tested
            manifest_builder.build_service_yaml(service)

            # Check if yaml.dump was called with correct parameters
            expected_values_data = {
                "service": {
                    "web_service": {
                        "name": "web-service",
                        "labels": {"app": "web"},
                        "ports": [
                            {
                                "port": 80,
                                "targetPort": 8080,
                                "name": "http",
                                "protocol": "TCP",
                            },
                            {
                                "port": 443,
                                "targetPort": 8080,
                                "name": "https",
                                "protocol": "TCP",
                            },
                        ],
                        "type": "ClusterIP",
                    }
                }
            }

            # First call should be for values.yaml
            assert mock_save.call_count >= 1
            assert mock_save.call_args_list[0][0][0] == expected_values_data

            expected_template = {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {
                    "name": "{{ .Values.service.web_service.name }}",
                    "labels": "{{ .Values.service.web_service.labels }}",
                },
                "spec": {
                    "selector": "{{ .Values.service.web_service.labels }}",
                    "ports": "{{ .Values.service.web_service.ports }}",
                    "type": "{{ .Values.service.web_service.type }}",
                },
            }

            assert mock_save.call_count >= 2
            assert expected_template == mock_save.call_args_list[1][0][0]


def test_build_pvc_yaml(manifest_builder):
    # Create a mock for ManifestBuilder with template methods pre-configured
    with patch("manifest_builder.ManifestBuilder._get_config_map_template"), patch(
        "manifest_builder.ManifestBuilder._get_deployment_template"
    ), patch("manifest_builder.ManifestBuilder._get_service_template"), patch(
        "manifest_builder.ManifestBuilder._get_stateful_set_template"
    ), patch(
        "manifest_builder.ManifestBuilder._get_pvc_template"
    ) as mock_pvc, patch(
        "os.path.exists", return_value=False
    ), patch(
        "os.makedirs", return_value=None
    ), patch(
        "builtins.open", mock.mock_open(), create=True
    ), patch(
        "manifest_builder.ManifestBuilder._save_yaml"
    ) as mock_save, patch(
        "os.getenv", return_value="/mock/path"
    ):

        # Set up the template that will be returned by get_template
        template = {
            "apiVersion": "v1",
            "kind": "PersistentVolumeClaim",
            "metadata": {"name": "template-name", "labels": {}},
            "spec": {
                "storageClassName": "standard",
                "accessModes": ["ReadWriteOnce"],
                "resources": {"requests": {"storage": "1Gi"}},
            },
        }
        mock_pvc.return_value = template

        # Patch the specific method in the ManifestBuilder class
        with patch.object(
            manifest_builder, "get_template", return_value=template.copy()
        ):

            # Provide test data
            pvc = {
                "name": "data-storage",
                "labels": {"app": "mysql"},
                "storage_class": "standard",
                "access_modes": ["ReadWriteOnce"],
                "resources": "10Gi",
            }

            # Call the method being tested
            manifest_builder.build_pvc_yaml(pvc)

            # Check if yaml.dump was called with correct parameters
            expected_values_data = {
                "pvc": {
                    "data_storage": {
                        "name": "data-storage",
                        "labels": {"app": "mysql"},
                        "storage_class": "standard",
                        "access_modes": ["ReadWriteOnce"],
                        "resources": "10Gi",
                    }
                }
            }

            # First call should be for values.yaml
            assert mock_save.call_count >= 1
            assert mock_save.call_args_list[0][0][0] == expected_values_data

            expected_template = {
                "apiVersion": "v1",
                "kind": "PersistentVolumeClaim",
                "metadata": {
                    "name": "{{ .Values.pvc.data_storage.name }}",
                    "labels": "{{ .Values.pvc.data_storage.labels }}",
                },
                "spec": {
                    "storageClassName": "{{ .Values.pvc.data_storage.storage_class }}",
                    "accessModes": "{{ .Values.pvc.data_storage.access_modes }}",
                    "resources": {
                        "requests": {
                            "storage": "{{ .Values.pvc.data_storage.resources }}"
                        }
                    },
                },
            }

            assert mock_save.call_count >= 2
            assert expected_template == mock_save.call_args_list[1][0][0]

def test_build_secrets_yaml_existing_values(manifest_builder):
    """Test build_secrets_yaml when values.yaml already exists."""
    with patch(
        "manifest_builder.ManifestBuilder._get_config_map_template"
    ) as mock_config_map, patch(
        "manifest_builder.ManifestBuilder._get_deployment_template"
    ), patch(
        "manifest_builder.ManifestBuilder._get_service_template"
    ), patch(
        "manifest_builder.ManifestBuilder._get_stateful_set_template"
    ), patch(
        "manifest_builder.ManifestBuilder._get_pvc_template"
    ), patch(
        "os.path.exists", return_value=True
    ), patch(
        "os.makedirs"
    ), patch(
        "builtins.open",
        mock.mock_open(read_data='secrets:\n  existing_secret:\n    name: "existing"\n    password: "old_value"'),
    ) as mock_file, patch(
        "manifest_builder.ManifestBuilder._save_yaml"
    ) as mock_save:

        # Set up the template that will be returned by get_template 
        template = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "template-name"},
            "data": {},
        }
        mock_config_map.return_value = template

        # Provide test data for a new secret
        new_secret = {"name": "new_secret", "value": "new_value"}

        # Call the method being tested
        manifest_builder.build_secrets_yaml(new_secret)

        # Expected values data should contain both existing and new secrets
        expected_values_data = {
            "secrets": {
                "existing_secret": {"name": "existing", "password": "old_value"},
                "new_secret": {"name": "new_secret", "password": "new_value"} 
            }
        }

        # Check if _save_yaml was called with expected values
        assert mock_save.call_count >= 1
        first_save_call = mock_save.call_args_list[0][0][0]
        assert "secrets" in first_save_call
        assert "existing_secret" in first_save_call["secrets"]
        assert "new_secret" in first_save_call["secrets"]

        # Check template generation
        expected_template = {
            "apiVersion": "v1", 
            "kind": "Secret",
            "metadata": {"name": "{{ .Values.secrets.new_secret.name }}"},
            "data": {"new_secret": "{{ .Values.secrets.new_secret.password }}"},
            "type": "Opaque"
        }

        # Check second _save_yaml call for template
        assert mock_save.call_count >= 2 
        assert mock_save.call_args_list[1][0][0] == expected_template
        
def test_generate_manifests_statefulset(manifest_builder):
    """Test generating manifests for a statefulset workload"""
    with patch.object(manifest_builder, 'build_stateful_set_yaml') as mock_build_stateful, \
            patch.object(manifest_builder, 'build_service_yaml') as mock_build_service, \
            patch.object(manifest_builder, 'build_pvc_yaml') as mock_build_pvc, \
            patch.object(manifest_builder, 'build_secrets_yaml') as mock_build_secrets, \
            patch.object(manifest_builder, 'build_config_map_yaml') as mock_build_config:

        microservice = {
            "name": "db",
            "workload": "StatefulSet",
            "ports": [3306],
            "persistent_volumes": [{"name": "data"}],
            "secrets": [{"name": "password", "value": "secret"}],
            "env": [{"name": "DB_NAME", "value": "mydb"}]
        }

        manifest_builder.generate_manifests(microservice)

        mock_build_stateful.assert_called_once_with(microservice)
        mock_build_service.assert_called_once_with(microservice)  
        mock_build_pvc.assert_called_once_with({"name": "data"})
        mock_build_secrets.assert_called_once_with({"name": "password", "value": "secret"})
        mock_build_config.assert_called_once_with({"name": "DB_NAME", "value": "mydb"})

def test_generate_manifests_deployment(manifest_builder):
    """Test generating manifests for a deployment workload"""
    with patch.object(manifest_builder, 'build_deployment_yaml') as mock_build_deployment, \
            patch.object(manifest_builder, 'build_service_yaml') as mock_build_service, \
            patch.object(manifest_builder, 'build_pvc_yaml') as mock_build_pvc, \
            patch.object(manifest_builder, 'build_secrets_yaml') as mock_build_secrets, \
            patch.object(manifest_builder, 'build_config_map_yaml') as mock_build_config:

        microservice = {
            "name": "app",
            "workload": "Deployment", 
            "ports": [8080],
            "persistent_volumes": [{"name": "storage"}],
            "secrets": [{"name": "api-key", "value": "xyz123"}],
            "env": [{"name": "PORT", "value": "8080"}]
        }

        manifest_builder.generate_manifests(microservice)

        mock_build_deployment.assert_called_once_with(microservice)
        mock_build_service.assert_called_once_with(microservice)
        mock_build_pvc.assert_called_once_with({"name": "storage"})
        mock_build_secrets.assert_called_once_with({"name": "api-key", "value": "xyz123"})
        mock_build_config.assert_called_once_with({"name": "PORT", "value": "8080"})

def test_generate_manifests_no_workload_defaults_to_deployment(manifest_builder):
    """Test generating manifests with no workload specified defaults to deployment"""
    with patch.object(manifest_builder, 'build_deployment_yaml') as mock_build_deployment:

        microservice = {
            "name": "app",
            "ports": [8080],
            "labels": []
        }

        manifest_builder.generate_manifests(microservice)

        mock_build_deployment.assert_called_once_with(microservice)

def test_generate_manifests_no_ports_skips_service(manifest_builder):
    """Test generating manifests with no ports skips service creation"""
    with patch.object(manifest_builder, 'build_deployment_yaml') as mock_build_deployment, \
            patch.object(manifest_builder, 'build_service_yaml') as mock_build_service:
            
        microservice = {
            "name": "app",
            "workload": "Deployment"
        }

        manifest_builder.generate_manifests(microservice)

        mock_build_deployment.assert_called_once_with(microservice)
        mock_build_service.assert_not_called()
        
def test_build_config_map_yaml_existing_values(manifest_builder):
    # Create a mock for ManifestBuilder with template methods pre-configured
    with patch(
        "manifest_builder.ManifestBuilder._get_config_map_template"
    ) as mock_config_map, patch(
        "manifest_builder.ManifestBuilder._get_deployment_template"
    ), patch(
        "manifest_builder.ManifestBuilder._get_service_template"
    ), patch(
        "manifest_builder.ManifestBuilder._get_stateful_set_template"
    ), patch(
        "manifest_builder.ManifestBuilder._get_pvc_template"
    ), patch(
        "os.path.exists", return_value=True
    ), patch(
        "os.makedirs", return_value=None
    ), patch(
        "builtins.open", mock.mock_open(read_data=yaml.dump({"existing": "data"})), create=True
    ), patch(
        "yaml.dump"
    ) as mock_dump, patch(
        "manifest_builder.ManifestBuilder._save_yaml"
    ) as mock_save, patch(
        "os.getenv", return_value="/mock/path"
    ):

        # Set up the template that will be returned by get_template
        template = {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {"name": "template-name"},
            "data": {},
        }
        mock_config_map.return_value = template

        # Provide test data
        config_map = {"name": "test-config", "value": "test-value"}

        # Call the method being tested
        manifest_builder.build_config_map_yaml(config_map)

        # Check if yaml.dump was called with correct parameters
        expected_values_data = {
            "existing": "data",
            "config": {
                "test_config": {"name": "test_config", "value": "test-value"}
            }
        }

        # First call should be for values.yaml
        assert mock_save.call_count >= 1
        assert mock_save.call_args_list[0][0][0] == expected_values_data

def test_build_deployment_yaml_with_existing_values(manifest_builder):
    # Create a mock for ManifestBuilder with template methods pre-configured
    with patch("manifest_builder.ManifestBuilder._get_config_map_template"), patch(
        "manifest_builder.ManifestBuilder._get_deployment_template"
    ) as mock_deployment, patch(
        "manifest_builder.ManifestBuilder._get_service_template"
    ), patch(
        "manifest_builder.ManifestBuilder._get_stateful_set_template"
    ), patch(
        "manifest_builder.ManifestBuilder._get_pvc_template"
    ), patch(
        "os.path.exists", return_value=False
    ), patch(
        "os.makedirs", return_value=None
    ), patch(
        "builtins.open", mock.mock_open(), create=True
    ), patch(
        "manifest_builder.ManifestBuilder._save_yaml"
    ) as mock_save, patch(
        "os.getenv", return_value="/mock/path"
    ), patch(
        "manifest_builder.ManifestBuilder.get_template",
        return_value=mock_deployment.return_value,
    ):

        # Set up the template that will be returned by get_template
        template = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {"name": "template-name", "labels": {}},
            "spec": {
                "selector": {"matchLabels": {}},
                "template": {
                    "metadata": {"labels": {}},
                    "spec": {
                        "containers": [
                            {
                                "name": "container-name",
                                "command": [],
                                "args": [],
                                "env": [],
                                "ports": [],
                            }
                        ]
                    },
                },
            },
        }
        mock_deployment.return_value = template

        # Patch the specific method in the ManifestBuilder class
        with patch.object(
            manifest_builder, "get_template", return_value=template.copy()
        ):


            # Provide test data for else branch of workload type test
            deployments = {
                "name": "test-app-2", 
                "labels": {"app": "test-app-2"},
                "command": ["/bin/bash"],
                "args": ["-c", "sleep infinity"],
                "env": [
                    {"name": "ENV_VAR1", "value": "test1"},
                    {"name": "ENV_VAR2", "key": "password", "value": "test2"}
                ],
                "ports": [8080, 9090],
                "workdir": "/app",
                "liveness_probe": {"httpGet": {"path": "/health", "port": 8080}},
                "user": 1000,
            }

            # Call the method being tested
            manifest_builder.build_deployment_yaml(deployments)

            # Check values.yaml data
            expected_values_data = {
                "deployment": {
                    "test_app_2": {
                        "name": "test-app-2",
                        "labels": {"app": "test-app-2"},
                        "command": ["/bin/bash"],
                        "args": ["-c", "sleep infinity"],
                        "ports": {"containerPort": 8080, "containerPort": 9090},
                        "workdir": "/app",
                        "liveness_probe": {"httpGet": {"path": "/health", "port": 8080}},
                        "user": 1000,
                    }
                }
            }

            # First call should be for values.yaml
            assert mock_save.call_count >= 1
            assert mock_save.call_args_list[0][0][0] == expected_values_data

def test_build_stateful_set_yaml_with_existing_values(manifest_builder):
    # Create a mock for ManifestBuilder with template methods pre-configured
    with patch("manifest_builder.ManifestBuilder._get_config_map_template"), patch(
        "manifest_builder.ManifestBuilder._get_deployment_template"
    ) as mock_deployment, patch(
        "manifest_builder.ManifestBuilder._get_service_template"
    ), patch(
        "manifest_builder.ManifestBuilder._get_stateful_set_template"
    ), patch(
        "manifest_builder.ManifestBuilder._get_pvc_template"
    ), patch(
        "os.path.exists", return_value=True
    ), patch(
        "os.makedirs", return_value=None
    ), patch(
        "builtins.open", mock.mock_open(), create=True
    ), patch(
        "manifest_builder.ManifestBuilder._save_yaml"
    ) as mock_save, patch(
        "os.getenv", return_value="/mock/path"
    ), patch(
        "manifest_builder.ManifestBuilder.get_template",
        return_value=mock_deployment.return_value,
    ):

        # Provide test data with an existing values.yaml file
        stateful_set = {
            "name": "db-stateful",
            "labels": {"app": "database"},
            "command": ["mysqld"],
            "args": ["--default-authentication-plugin=mysql_native_password"],
            "env": [{"name": "MYSQL_ROOT_PASSWORD", "value": "secretpassword"}],
            "volumes": [
                {
                    "name": "data-vol",
                    "persistentVolumeClaim": {"claimName": "mysql-data"},
                }
            ],
            "volume_mounts": [{"name": "data-vol", "mountPath": "/var/lib/mysql"}],
            "ports": [3306],
            "workdir": "/var/lib/mysql",
            "liveness_probe": {"exec": {"command": ["mysqladmin", "ping"]}},
            "user": 999,
        }

        # Mock the existing values.yaml file content
        mock_existing_values = {
            "some-existing": {"key": "value"},
            "stateful-set": {
                "existing-stateful": {"name": "existing", "command": ["cmd"]}
            },
        }

        # Mock open to return the existing values.yaml content
        mock_open = mock.mock_open(read_data=yaml.dump(mock_existing_values))
        with patch("builtins.open", mock_open):

            # Call the method being tested
            manifest_builder.build_stateful_set_yaml(stateful_set)

            # Check if _save_yaml was called with correct parameters
            expected_values_data = mock_existing_values.copy()
            expected_values_data["stateful-set"]["db_stateful"] = {
                "name": "db-stateful",
                "labels": {"app": "database"},
                "command": ["mysqld"],
                "args": ["--default-authentication-plugin=mysql_native_password"],
                "volumes": [
                    {
                        "name": "data-vol",
                        "persistentVolumeClaim": {"claimName": "mysql-data"},
                    }
                ],
                "volume_mounts": [
                    {"name": "data-vol", "mountPath": "/var/lib/mysql"}
                ],
                "ports": [3306],
                "workdir": "/var/lib/mysql",
                "liveness_probe": {"exec": {"command": ["mysqladmin", "ping"]}},
                "user": 999,
            }

            # First call should be for values.yaml
            assert mock_save.call_count >= 1
            print(mock_save.call_args_list[0][0][0])
            print(expected_values_data)
            assert mock_save.call_args_list[0][0][0] == expected_values_data
