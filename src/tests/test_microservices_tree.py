import pytest
from tree.microservices_tree import MicroservicesTree
from tree.node import Node
from tree.node_types import NodeType
from tree.docker_instruction_node import DockerInstruction
from unittest.mock import Mock, patch

@pytest.fixture
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

@pytest.fixture
def tree(mock_service_classifier):
    return MicroservicesTree(
        root_path="",
        embeddings_engine=Mock(),
        secret_classifier=Mock(),
        service_classifier=mock_service_classifier,
        label_classifier=Mock()
    )

def test_prepare_microservice_basic(tree):
    node = Node(name="test-service", type=NodeType.MICROSERVICE)
    result = tree.prepare_microservice(node)
    print(result)
    assert result["name"] == "test-service"
    assert result["labels"] == {"app": "test-service", "mock": "label"}

def test_prepare_microservice_with_labels(tree):
    node = Node(name="test-service", type=NodeType.MICROSERVICE)
    label_node = DockerInstruction(name="label", type=NodeType.LABEL, value="key=value")
    node.add_child(label_node)
    
    result = tree.prepare_microservice(node)
    assert result["labels"] == {"app": "test-service", "key": "value", "mock": "label"}

def test_prepare_microservice_with_ports(tree):
    node = Node(name="test-service", type=NodeType.MICROSERVICE)
    port_node = DockerInstruction(name="port", type=NodeType.PORT, value="8080")
    node.add_child(port_node)
    
    result = tree.prepare_microservice(node)
    assert result["ports"] == [8080]
    assert result["service-ports"] == [8080]
    assert result["type"] == "ClusterIP"
    assert result["protocol"] == "TCP"

def test_prepare_microservice_with_env_vars(tree):
    node = Node(name="test-service", type=NodeType.MICROSERVICE)
    env_node = DockerInstruction(name="DB_HOST", type=NodeType.ENV, value="localhost")
    node.add_child(env_node)
    
    result = tree.prepare_microservice(node)
    assert result["env"][0] == {
        "name": "DB_HOST",
        "key": "config",
        "value": "localhost"
    }

def test_prepare_microservice_with_volume(tree):
    node = Node(name="test-service", type=NodeType.MICROSERVICE)
    volume = DockerInstruction(name="volume", type=NodeType.VOLUME, value="/data")
    volume.is_persistent = True
    node.add_child(volume)
    
    result = tree.prepare_microservice(node)
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