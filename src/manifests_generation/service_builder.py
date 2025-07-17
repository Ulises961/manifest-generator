from copy import deepcopy
import logging
import os
from typing import Any, List, cast, Dict

from utils.file_utils import load_file, remove_none_values


class ServiceBuilder:
    def _get_service_template(self) -> Dict[str, Any]:
        """Get the service template."""
        template = load_file(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                os.getenv(
                    "SERVICES_TEMPLATE_PATH", "resources/k8s_templates/services.json"
                ),
            )
        )
        return cast(Dict[str, Any], deepcopy(template))
    
    def build_template(self, service: dict) -> Dict[str, Any]:
        """Build a YAML file from the template and data."""

        port_mappings = self._get_port_mappings(service)

        # Prepare the service entry
        service_entry = {
            "name": service["name"],
            "labels": service["labels"],
            "ports": port_mappings,
            "type": service.get("type", "ClusterIP"),
        }

        template = self._get_service_template()
        template["metadata"]["name"] = service_entry["name"]
        template["metadata"]["labels"] = service_entry["labels"]

        template["spec"]["selector"] = service_entry["labels"]

        template["spec"]["ports"] = service_entry["ports"]

        template["spec"]["type"] = service_entry["type"]
        # Remove all None values from the template
        template = remove_none_values(template)

        return cast(Dict[str, Any],template) 

    def _get_port_mappings(self, service_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate port mappings between service ports and container ports.

        Args:
            service_info: Service information from ontology
            container_ports: Container ports detected from Dockerfile (optional)

        Returns:
            List of port mapping dictionaries
        """

        container_ports = service_info.get("ports", [])
        service_ports = service_info.get("service-ports", [])
        protocol = service_info.get("protocol", "TCP")

        # If we have different numbers of ports, we need to be careful
        if len(service_ports) != len(container_ports):
            # Special case: Service ports are a subset of container ports
            if all(port in container_ports for port in service_ports):
                return [
                    {
                        "port": sport,
                        "targetPort": sport,
                        "name": f"port-{sport}",
                        "protocol": protocol,
                    }
                    for sport in service_ports
                ]
            # For mismatched ports, use common port conventions
            return self._map_ports_by_convention(
                service_ports, container_ports, protocol
            )

        # Simple 1:1 mapping when port counts match
        return [
            {
                "port": sport,
                "targetPort": cport,
                "name": self._get_port_name(sport),
                "protocol": protocol,
            }
            for sport, cport in zip(service_ports, container_ports)
        ]

    def _map_ports_by_convention(
        self, service_ports: List[int], container_ports: List[int], protocol: str
    ) -> List[Dict[str, Any]]:
        """Map ports using common conventions."""
        mappings = []

        # Common port conventions
        conventions = {
            80: [8080, 3000, 4200, 5000, 8000],
            443: [8443, 8080, 3000],
        }

        # Try to map each service port
        for sport in service_ports:
            # Direct match
            if sport in container_ports:
                mappings.append(
                    {
                        "port": sport,
                        "targetPort": sport,
                        "name": self._get_port_name(sport),
                        "protocol": protocol,
                    }
                )
                continue

            # Look for conventional mappings
            mapped = False
            for standard, alternatives in conventions.items():
                if sport == standard and any(
                    alternative in container_ports for alternative in alternatives
                ):
                    # Find the first matching alternative
                    for alternative in alternatives:
                        if alternative in container_ports:
                            mappings.append(
                                {
                                    "port": sport,
                                    "targetPort": alternative,
                                    "name": self._get_port_name(sport),
                                    "protocol": protocol,
                                }
                            )
                            mapped = True
                            break
                    if mapped:
                        break

            # No mapping found, use the service port directly
            if not mapped:
                mappings.append(
                    {
                        "port": sport,
                        "targetPort": sport,
                        "name": f"port-{sport}",
                        "protocol": protocol,
                    }
                )

        return mappings

    def _get_port_name(self, port):
        """Get a canonical name for well-known ports."""
        port_names = {80: "http", 443: "https"}
        return port_names.get(port, f"port-{port}")
