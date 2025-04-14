from enum import Enum
import json

class NodeType(Enum):
    """NodeType is an enumeration of the different nodes the repository can contain."""
    ROOT = "ROOT"
    MICROSERVICE = "MICROSERVICE"    
    ENV = "ENV"
    SECRET = "SECRET"
    VOLUME = "VOLUME"
    PVC = "PVC"
    LABEL = "LABEL"
    PORT = "PORT"
    ANNOTATION = "ANNOTATION"
    HEALTHCHECK = "HEALTHCHECK"
    STOPSIGNAL = "STOPSIGNAL"
    ENTRYPOINT = "ENTRYPOINT"
    CMD = "CMD"
    USER = "USER"
    WORKDIR = "WORKDIR"
    
    def __str__(self):
        return self.value
        
    def to_json(self):
        return self.value
        
    @classmethod
    def from_json(cls, value):
        return cls(value)