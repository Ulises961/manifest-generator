from enum import Enum
import json

class NodeType(str, Enum):
    """NodeType is an enumeration of the different nodes the repository can contain."""
    ROOT = "ROOT"
    MICROSERVICE = "MICROSERVICE"    
    ENV = "ENV"
    SECRET = "SECRET"
    VOLUME = "VOLUME"
    LABEL = "LABEL"
    PORT = "PORT"
    ANNOTATION = "ANNOTATION"
    HEALTHCHECK = "HEALTHCHECK"
    ENTRYPOINT = "ENTRYPOINT"
    CMD = "CMD"
    USER = "USER"
    WORKDIR = "WORKDIR"
    
    def __str__(self):
        return self.value
        
    def __repr__(self):
        return self.value
    
    def to_dict(self):
        """Convert the NodeType to a dictionary."""
        return {
            "type": self.value
        }