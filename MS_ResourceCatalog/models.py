import time
from datetime import datetime

class Device:
    """Model for IoT devices/resources registered in the catalog"""
    def __init__(self, device_id, name, description, device_type, endpoints=None, 
                 sensors=None, actuators=None, last_update=None, status="offline"):
        self.device_id = device_id
        self.name = name
        self.description = description
        self.device_type = device_type  # e.g., "raspberry_pi", "arduino", etc.
        self.endpoints = endpoints or {}  # URLs, MQTT topics, etc.
        self.sensors = sensors or []  # List of available sensors
        self.actuators = actuators or []  # List of available actuators
        self.status = status  # "online", "offline", "error"
        self.last_update = last_update or time.time()
        self.registration_timestamp = time.time()
    
    def to_dict(self):
        """Convert device object to dictionary for storage/API responses"""
        return {
            "device_id": self.device_id,
            "name": self.name,
            "description": self.description,
            "device_type": self.device_type,
            "endpoints": self.endpoints,
            "sensors": self.sensors,
            "actuators": self.actuators,
            "status": self.status,
            "last_update": self.last_update,
            "last_update_formatted": datetime.fromtimestamp(self.last_update).strftime('%Y-%m-%d %H:%M:%S'),
            "registration_timestamp": self.registration_timestamp
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create a Device object from dictionary data"""
        return cls(
            device_id=data.get("device_id"),
            name=data.get("name"),
            description=data.get("description"),
            device_type=data.get("device_type"),
            endpoints=data.get("endpoints"),
            sensors=data.get("sensors"),
            actuators=data.get("actuators"),
            last_update=data.get("last_update"),
            status=data.get("status", "offline")
        )


class Service:
    """Model for services registered in the catalog"""
    def __init__(self, service_id, name, description, service_type, endpoints=None,
                 required_inputs=None, provided_outputs=None, last_update=None,
                 status="offline"):
        self.service_id = service_id
        self.name = name
        self.description = description
        self.service_type = service_type  # e.g., "data_storage", "analytics", "control"
        self.endpoints = endpoints or {}  # URLs, API endpoints
        self.required_inputs = required_inputs or {}  # Input specifications
        self.provided_outputs = provided_outputs or {}  # Output specifications
        self.status = status  # "online", "offline", "error"
        self.last_update = last_update or time.time()
        self.registration_timestamp = time.time()
    
    def to_dict(self):
        """Convert service object to dictionary for storage/API responses"""
        return {
            "service_id": self.service_id,
            "name": self.name,
            "description": self.description, 
            "service_type": self.service_type,
            "endpoints": self.endpoints,
            "required_inputs": self.required_inputs,
            "provided_outputs": self.provided_outputs,
            "status": self.status,
            "last_update": self.last_update,
            "last_update_formatted": datetime.fromtimestamp(self.last_update).strftime('%Y-%m-%d %H:%M:%S'),
            "registration_timestamp": self.registration_timestamp
        }
    
    @classmethod
    def from_dict(cls, data):
        """Create a Service object from dictionary data"""
        return cls(
            service_id=data.get("service_id"),
            name=data.get("name"),
            description=data.get("description"),
            service_type=data.get("service_type"),
            endpoints=data.get("endpoints"),
            required_inputs=data.get("required_inputs"),
            provided_outputs=data.get("provided_outputs"),
            last_update=data.get("last_update"),
            status=data.get("status", "offline")
        )