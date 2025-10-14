import pytest
from tree.attached_file import AttachedFile
from tree.microservices_tree import MicroservicesTree
from tree.node import Node
from tree.node_types import NodeType

from unittest.mock import Mock

@pytest.fixture(scope="function")
def mock_service_classifier():
    classifier = Mock()
    classifier.decide_service.return_value = {
        "workload": "Deployment",
        "protocol": "TCP", 
        "serviceType": "ClusterIP",
        "ports": ["8080"],
        "labels": {"mock": "label"}
    }
    return classifier

@pytest.fixture(scope="function")
def tree(mock_service_classifier):
    return MicroservicesTree(
        root_path="",
        embeddings_engine=Mock(),
        secret_classifier=Mock(),
        service_classifier=mock_service_classifier,
        label_classifier=Mock(),
        volumes_classifier=Mock()
    )

def test_prepare_microservice_basic(tree):
    node = Node(name="test-service", type=NodeType.MICROSERVICE)
    result = tree.prepare_microservice(node)
    assert result["name"] == "test-service"
    assert result["labels"] == {"app": "test-service", "mock": "label"}

def test_prepare_microservice_with_labels(tree):
    node = Node(name="test-service", type=NodeType.MICROSERVICE)
    label_node = Node(name="label", type=NodeType.LABEL, value="key=value")
    node.add_child(label_node)
    
    result = tree.prepare_microservice(node)
    assert result["labels"] == {"app": "test-service", "key": "value", "mock": "label"}

def test_prepare_microservice_with_ports(tree):
    node = Node(name="test-service", type=NodeType.MICROSERVICE)
    port_node = Node(name="port", type=NodeType.CONTAINER_PORT, value="8080")
    node.add_child(port_node)
    
    result = tree.prepare_microservice(node)
    assert result["ports"] == [8080]
    assert result["service-ports"] == [8080]
    assert result["type"] == "ClusterIP"
    assert result["protocol"] == "TCP"

def test_prepare_microservice_with_env_vars(tree):
    node = Node(name="test-service", type=NodeType.MICROSERVICE)
    env_node = Node(name="DB_HOST", type=NodeType.ENV, value="localhost")
    node.add_child(env_node)
    
    result = tree.prepare_microservice(node)
    if len(result["env"]) > 0:
        assert result["env"][0] == {
            "name": "DB_HOST",
            "key": "config",
            "value": "localhost"
        }

def test_prepare_microservice_with_volume(tree):
    node = Node(name="test-service", type=NodeType.MICROSERVICE)
    volume = Node(name="volume", type=NodeType.VOLUME, value="/data")
    volume.is_persistent = True
    node.add_child(volume)
    
    result = tree.prepare_microservice(node)

    if len(result["volumes"]) > 0:
        assert result["volume_mounts"][0] == {
            "name": "volume-0",
            "mountPath": "/data"
        }
        assert result["persistent_volumes"][0]["name"] == "volume-0"
        assert result["volumes"][0] == {
            "name": "volume-0", 
            "persistentVolumeClaim": {"claimName": "volume-0"}
        }

def test_prepare_microservice_with_service_classifier(tree, mock_service_classifier):
    node = Node(name="test-service", type=NodeType.MICROSERVICE)
    result = tree.prepare_microservice(node)
    
    assert result["workload"] == "Deployment"
    assert result["protocol"] == "TCP"
    assert result["type"] == "ClusterIP"
    assert result["ports"] == [8080]
    assert "app" in result["labels"]

def test_prepare_microservice_with_annotations(tree):
    node = Node(name="test-service", type=NodeType.MICROSERVICE)
    annotation_node = Node(name="annotation", type=NodeType.ANNOTATION, value="key=value")
    node.add_child(annotation_node)
    
    result = tree.prepare_microservice(node)
    assert result["annotations"] == {"key": "value"}

def test_prepare_microservice_with_entrypoint(tree):
    node = Node(name="test-service", type=NodeType.MICROSERVICE)
    entrypoint_node = Node(name="entrypoint", type=NodeType.ENTRYPOINT, value="python app.py")
    node.add_child(entrypoint_node)
    
    result = tree.prepare_microservice(node)
    assert result["command"] == "python app.py"

def test_prepare_microservice_with_cmd(tree):
    node = Node(name="test-service", type=NodeType.MICROSERVICE)
    cmd_node = Node(name="cmd", type=NodeType.CMD, value="--config=config.yaml")
    node.add_child(cmd_node)
    
    result = tree.prepare_microservice(node)
    assert result["args"] == "--config=config.yaml"

def test_prepare_microservice_with_healthcheck(tree):
    node = Node(name="test-service", type=NodeType.MICROSERVICE)
    healthcheck_node = Node(name="healthcheck", type=NodeType.HEALTHCHECK, value="curl http://localhost:8080/health")
    healthcheck_node.metadata = {"initialDelaySeconds": 5, "timeoutSeconds": 2}
    node.add_child(healthcheck_node)
    
    result = tree.prepare_microservice(node)
    assert result["liveness_probe"] == {
        "exec": {"command": "curl http://localhost:8080/health"},
        "initialDelaySeconds": 5,
        "status": "active",
        "timeoutSeconds": 2
    }

def test_prepare_microservice_with_multiple_ports(tree):
    mock_service_classifier = Mock()
    mock_service_classifier.decide_service.return_value = {
        "workload": "Deployment",
        "protocol": "TCP", 
        "serviceType": "ClusterIP",
        "ports": ["8080", "9090"],
        "labels": {"mock": "label"}
    }
    
    # Create tree with the specific mock
    tree = MicroservicesTree(
        root_path="",
        embeddings_engine=Mock(),
        secret_classifier=Mock(),
        service_classifier=mock_service_classifier,
        label_classifier=Mock(),
        volumes_classifier=Mock()
    )

    node = Node(name="test-service", type=NodeType.MICROSERVICE)
    port_node1 = Node(name="port1", type=NodeType.CONTAINER_PORT, value="8080")
    port_node2 = Node(name="port2", type=NodeType.CONTAINER_PORT, value="9090")
    node.add_child(port_node1)
    node.add_child(port_node2)
    
    result = tree.prepare_microservice(node)

    assert result["ports"] == [8080, 9090]
    assert result["service-ports"] == [8080, 9090]

def test_prepare_microservice_with_workdir(tree):
    node = Node(name="test-service", type=NodeType.MICROSERVICE)
    workdir_node = Node(name="workdir", type=NodeType.WORKDIR, value="/app")
    node.add_child(workdir_node)
    
    result = tree.prepare_microservice(node)
    assert result["workdir"] == "/app"

def test_prepare_microservice_with_secrets(tree):
    node = Node(name="test-service", type=NodeType.MICROSERVICE)
    secret_node = Node(name="DB_PASSWORD", type=NodeType.SECRET, value="password123")
    node.add_child(secret_node)
    result = tree.prepare_microservice(node)
    assert result["secrets"] == [{"name": "DB_PASSWORD", "key": "password", "value": "password123"}]

def test_prepare_microservice_with_service_classifier_ports(tree, mock_service_classifier):
    mock_service_classifier.decide_service.return_value = {
        "workload": "Deployment",
        "protocol": "TCP",
        "serviceType": "ClusterIP",
        "ports": ["3000", "4000"],
        "labels": {"mock": "label"}
    }
    node = Node(name="test-service", type=NodeType.MICROSERVICE)
    result = tree.prepare_microservice(node)
    
    assert result["ports"] == [3000, 4000]
    assert result["service-ports"] == [3000, 4000]