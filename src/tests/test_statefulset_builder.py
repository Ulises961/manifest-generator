import os
import pytest
from unittest.mock import patch, MagicMock
from manifests_generation.statefulset_builder import StatefulSetBuilder



@pytest.fixture
def mock_remove_none_values():
    with patch("utils.file_utils.remove_none_values") as mock_remove:
        yield mock_remove


@pytest.fixture
def stateful_set_data():
    return {
        "name": "test-statefulset",
        "labels": {"app": "test-app"},
        "command": ["/bin/sh", "-c"],
        "args": ["echo", "Hello World"],
        "volumes": [{"name": "test-volume", "emptyDir": {}}],
        "volume_mounts": [{"name": "test-volume", "mountPath": "/data"}],
        "ports": [{"containerPort": 8080}],
        "workdir": "/app",
        "liveness_probe": {"httpGet": {"path": "/", "port": 8080}},
        "user": 1000,
        "env": [
            {"name": "ENV_VAR_1", "key": "env_var_1"},
            {"name": "PASSWORD", "key": "password"},
        ],
    }

@pytest.fixture
def statefulset_template():
    return{
        "apiVersion": "apps/v1",
        "kind": "StatefulSet",
        "metadata": {"name": "", "labels": {}},
        "spec": {
            "selector": {"matchLabels": {}},
            "serviceName": "",
            "replicas": 1,
            "template": {
                "metadata": {"labels": {}},
                "spec": {
                    "containers": [
                        {
                            "name": "",
                            "image": "",
                            "command": [],
                            "args": [],
                            "securityContext": {},
                            "env": [],
                            "volumeMounts": [],
                            "ports": [],
                            "lifecycle": {},
                            "workingDir": "",
                            "resources": {},
                            "livenessProbe": {},
                            "readinessProbe": {},
                        }
                    ],
                    "volumes": [],
                    "affinity": {},
                    "nodeSelector": {},
                    "tolerations": [],
                },
            },
            "volumeClaimTemplates": [],
        },
    }


@patch("manifests_generation.pvc_builder.load_file")
def test_build_template(mock_load_file, mock_remove_none_values, stateful_set_data):
    mock_load_file.return_value = statefulset_template
    mock_remove_none_values.side_effect = lambda x: x

    builder = StatefulSetBuilder()
    result = builder.build_template(stateful_set_data)

    assert result["metadata"]["name"] == "test-statefulset"
    assert result["metadata"]["labels"] == {"app": "test-app"}
    assert (
        result["spec"]["template"]["spec"]["containers"][0]["name"]
        == "test-statefulset"
    )
    assert (
        result["spec"]["template"]["spec"]["containers"][0]["image"]
        == "test-statefulset"
    )
    assert result["spec"]["template"]["spec"]["containers"][0]["command"] == [
        "/bin/sh",
        "-c",
    ]
    assert result["spec"]["template"]["spec"]["containers"][0]["args"] == [
        "echo",
        "Hello World",
    ]
    assert result["spec"]["template"]["spec"]["containers"][0]["ports"] == [
        {"containerPort": 8080}
    ]
    assert result["spec"]["template"]["spec"]["containers"][0]["workingDir"] == "/app"
    assert result["spec"]["template"]["spec"]["containers"][0]["livenessProbe"] == {
        "httpGet": {"path": "/", "port": 8080}
    }
    assert result["spec"]["template"]["spec"]["containers"][0]["securityContext"] == {
        "runAsUser": 1000
    }
    assert result["spec"]["template"]["spec"]["volumes"] == [
        {"name": "test-volume", "emptyDir": {}}
    ]
    assert result["spec"]["template"]["spec"]["containers"][0]["volumeMounts"] == [
        {"name": "test-volume", "mountPath": "/data"}
    ]
    assert result["spec"]["template"]["spec"]["containers"][0]["env"] == [
        {
            "name": "ENV_VAR_1",
            "valueFrom": {"configMapKeyRef": {"name": "config", "key": "ENV_VAR_1"}},
        },
        {
            "name": "PASSWORD",
            "valueFrom": {"secretKeyRef": {"name": "config", "key": "PASSWORD"}},
        },
    ]

@patch("manifests_generation.statefulset_builder.load_file")
def test_get_stateful_set_template(mock_load_file, statefulset_template):
    mock_load_file.return_value = statefulset_template
    builder = StatefulSetBuilder()
    result = builder._get_stateful_set_template()
    assert result == statefulset_template
    mock_load_file.assert_called_once_with(
        os.path.join(
            os.path.dirname(os.path.abspath("src/manifests_generation/statefulset_builder.py")),
            "..",
            "resources/k8s_templates/statefulset.json",
        )
    )
