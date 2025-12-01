from enum import Enum

class NodeType(str, Enum):
    """NodeType is an enumeration of the different nodes the repository can contain."""
    ROOT = "ROOT"
    MICROSERVICE = "MICROSERVICE"    
    ENV = "ENV"
    SECRET = "SECRET"
    VOLUME = "VOLUME"
    VOLUME_MOUNT = "VOLUME_MOUNT"
    VOLUME_CLAIM = "VOLUME_CLAIM"
    LABEL = "LABEL"
    CONTAINER_PORT = "CONTAINER_PORT"
    SERVICE_PORT_MAPPING = "SERVICE_PORT_MAPPING"
    ANNOTATION = "ANNOTATION"
    HEALTHCHECK = "HEALTHCHECK"
    ENTRYPOINT = "ENTRYPOINT"
    CMD = "CMD"
    USER = "USER"
    WORKDIR = "WORKDIR"
    NETWORK = "NETWORK"
    DEPENDENCY = "DEPENDENCY"
    IMAGE = "IMAGE"
    RESTART = "RESTART"
    CONDITION = "CONDITION"

    def __str__(self):
        return self.value
        
    def __repr__(self):
        return self.value
    
    def to_dict(self):
        """Convert the NodeType to a dictionary."""
        return {
            "type": self.value
        }