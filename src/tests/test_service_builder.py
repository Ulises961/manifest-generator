import os
import pytest
from unittest.mock import patch, MagicMock
from manifests_generation.service_builder import ServiceBuilder

@pytest.fixture
def service_builder():
    return ServiceBuilder()

@pytest.fixture
def service_template():
    return {
        "apiVersion": "v1",
        "kind": "Service",
        "metadata": {
            "name": "",
            "labels": {}
        },
        "spec": {
            "selector": {},
            "ports": [
                {
                    "name": "",
                    "port": 0,
                    "targetPort": 0,
                    "protocol": "TCP"
                }
            ],
            "type": "{{ dynamic_service_type }}"
        }
    }

# Remove the conflicting mock_load_file fixture and use only the decorator
@patch("manifests_generation.service_builder.load_file")
def test_get_service_template(mock_load_file, service_builder, service_template):
    mock_load_file.return_value = service_template
    result = service_builder._get_service_template()
    assert result == service_template
    mock_load_file.assert_called_once()

@patch("manifests_generation.service_builder.load_file")
@patch("manifests_generation.service_builder.remove_none_values")
def test_build_template(mock_remove_none_values, mock_load_file, service_builder):
    mock_template = {
        "metadata": {"name": "", "labels": {}},
        "spec": {"selector": {}, "ports": [], "type": ""},
    }
    mock_load_file.return_value = mock_template
    mock_remove_none_values.side_effect = lambda x: x  # Return input as-is

    service = {
        "name": "test-service",
        "labels": {"app": "test"},
        "ports": [8080],
        "service-ports": [80],
        "protocol": "TCP",
        "type": "ClusterIP",
    }

    result = service_builder.build_template(service)

    assert result["metadata"]["name"] == "test-service"
    assert result["metadata"]["labels"] == {"app": "test"}
    assert result["spec"]["selector"] == {"app": "test"}
    assert result["spec"]["ports"] == [
        {"port": 80, "targetPort": 8080, "name": "http", "protocol": "TCP"}
    ]
    assert result["spec"]["type"] == "ClusterIP"


def test_get_port_mappings_1_to_1(service_builder):
    service_info = {
        "ports": [8080],
        "service-ports": [80],
        "protocol": "TCP",
    }
    result = service_builder._get_port_mappings(service_info)
    assert result == [
        {"port": 80, "targetPort": 8080, "name": "http", "protocol": "TCP"}
    ]


def test_get_port_mappings_subset(service_builder):
    service_info = {
        "ports": [8080, 3000],
        "service-ports": [8080],
        "protocol": "TCP",
    }
    result = service_builder._get_port_mappings(service_info)
    assert result == [
        {"port": 8080, "targetPort": 8080, "name": "port-8080", "protocol": "TCP"}
    ]


def test_get_port_mappings_convention(service_builder):
    service_info = {
        "ports": [8080, 3000],
        "service-ports": [80],
        "protocol": "TCP",
    }
    result = service_builder._get_port_mappings(service_info)
    assert result == [
        {"port": 80, "targetPort": 8080, "name": "http", "protocol": "TCP"}
    ]


def test_get_port_mappings_no_match(service_builder):
    service_info = {
        "ports": [5001],
        "service-ports": [80],
        "protocol": "TCP",
    }
    result = service_builder._get_port_mappings(service_info)
    assert result == [
        {"port": 80, "targetPort": 5001, "name": "http", "protocol": "TCP"}
    ]