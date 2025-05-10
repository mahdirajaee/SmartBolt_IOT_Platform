import cherrypy
import json
import time
import threading
from models import Device, Service
from storage import StorageManager
from config import Config

class ResourceCatalogAPI:
    """CherryPy REST API for Resource Catalog"""
    
    def __init__(self, storage_manager=None, config=None):
        self.config = config or Config()
        self.storage = storage_manager or StorageManager(self.config.get("storage", "db_path"))
        
        # Start background thread for periodic cleanup
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_worker, 
            daemon=True
        )
        self.cleanup_thread.start()
    
    def _cleanup_worker(self):
        """Background worker for cleaning up stale device/service entries"""
        while True:
            try:
                timeout = self.config.get("timeout", "device_offline")
                num_cleaned = self.storage.cleanup_stale_entries(timeout)
                if num_cleaned > 0:
                    cherrypy.log(f"Marked {num_cleaned} stale entries as offline")
            except Exception as e:
                cherrypy.log.error(f"Error in cleanup worker: {e}")
            
            # Sleep for the configured interval
            time.sleep(self.config.get("timeout", "cleanup_interval"))
    
    # Utility methods for API responses
    def _success(self, data=None, message=None):
        return {
            "status": "success",
            "data": data,
            "message": message
        }
    
    def _error(self, message, status=400):
        cherrypy.response.status = status
        return {
            "status": "error",
            "message": message
        }
    
    # ROOT ENDPOINT
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self):
        """Root endpoint for health checks"""
        return self._success(message="Resource Catalog API is running")
    
    # DEVICE ENDPOINTS
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def devices(self):
        """Get all devices"""
        try:
            devices = self.storage.get_all_devices()
            return self._success([device.to_dict() for device in devices])
        except Exception as e:
            return self._error(f"Error retrieving devices: {e}")
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def device(self, device_id=None, **params):
        """Get a specific device by ID"""
        if not device_id:
            return self._error("Device ID is required", 400)
        
        try:
            device = self.storage.get_device(device_id)
            if device:
                return self._success(device.to_dict())
            else:
                return self._error(f"Device with ID {device_id} not found", 404)
        except Exception as e:
            return self._error(f"Error retrieving device: {e}")
    
    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def register_device(self):
        """Register a new device or update an existing one"""
        try:
            data = cherrypy.request.json
            
            # Validate required fields
            required_fields = ["device_id", "name", "description", "device_type"]
            for field in required_fields:
                if field not in data:
                    return self._error(f"Missing required field: {field}")
            
            # Create device object and store it
            device = Device(
                device_id=data["device_id"],
                name=data["name"],
                description=data["description"],
                device_type=data["device_type"],
                endpoints=data.get("endpoints", {}),
                sensors=data.get("sensors", []),
                actuators=data.get("actuators", []),
                status=data.get("status", "online"),
                last_update=time.time()
            )
            
            self.storage.add_device(device)
            return self._success(
                device.to_dict(), 
                f"Device {device.device_id} registered successfully"
            )
        except Exception as e:
            return self._error(f"Error registering device: {e}")
    
    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def update_device_status(self):
        """Update a device's status"""
        try:
            data = cherrypy.request.json
            
            if "device_id" not in data:
                return self._error("Missing required field: device_id")
            if "status" not in data:
                return self._error("Missing required field: status")
            
            success = self.storage.update_device_status(
                data["device_id"], 
                data["status"],
                time.time()
            )
            
            if success:
                return self._success(
                    None, 
                    f"Device {data['device_id']} status updated to {data['status']}"
                )
            else:
                return self._error(f"Device with ID {data['device_id']} not found", 404)
        except Exception as e:
            return self._error(f"Error updating device status: {e}")
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def devices_by_type(self, device_type=None):
        """Get devices by type"""
        if not device_type:
            return self._error("Device type is required", 400)
        
        try:
            devices = self.storage.get_devices_by_type(device_type)
            return self._success([device.to_dict() for device in devices])
        except Exception as e:
            return self._error(f"Error retrieving devices: {e}")
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def online_devices(self):
        """Get all online devices"""
        try:
            devices = self.storage.get_online_devices()
            return self._success([device.to_dict() for device in devices])
        except Exception as e:
            return self._error(f"Error retrieving online devices: {e}")
    
    # SERVICE ENDPOINTS
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def services(self):
        """Get all services"""
        try:
            services = self.storage.get_all_services()
            return self._success([service.to_dict() for service in services])
        except Exception as e:
            return self._error(f"Error retrieving services: {e}")
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def service(self, service_id=None, **params):
        """Get a specific service by ID"""
        if not service_id:
            return self._error("Service ID is required", 400)
        
        try:
            service = self.storage.get_service(service_id)
            if service:
                return self._success(service.to_dict())
            else:
                return self._error(f"Service with ID {service_id} not found", 404)
        except Exception as e:
            return self._error(f"Error retrieving service: {e}")
    
    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def register_service(self):
        """Register a new service or update an existing one"""
        try:
            data = cherrypy.request.json
            
            required_fields = ["service_id", "name", "description", "service_type"]
            for field in required_fields:
                if field not in data:
                    return self._error(f"Missing required field: {field}")
            
            service = Service(
                service_id=data["service_id"],
                name=data["name"],
                description=data["description"],
                service_type=data["service_type"],
                endpoints=data.get("endpoints", {}),
                required_inputs=data.get("required_inputs", {}),
                provided_outputs=data.get("provided_outputs", {}),
                status=data.get("status", "online"),
                last_update=time.time()
            )
            
            self.storage.add_service(service)
            return self._success(
                service.to_dict(), 
                f"Service {service.service_id} registered successfully"
            )
        except Exception as e:
            return self._error(f"Error registering service: {e}")
    
    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def update_service_status(self):
        """Update a service's status"""
        try:
            data = cherrypy.request.json
            
            if "service_id" not in data:
                return self._error("Missing required field: service_id")
            if "status" not in data:
                return self._error("Missing required field: status")
            
            success = self.storage.update_service_status(
                data["service_id"], 
                data["status"],
                time.time()
            )
            
            if success:
                return self._success(
                    None, 
                    f"Service {data['service_id']} status updated to {data['status']}"
                )
            else:
                return self._error(f"Service with ID {data['service_id']} not found", 404)
        except Exception as e:
            return self._error(f"Error updating service status: {e}")
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def services_by_type(self, service_type=None):
        """Get services by type"""
        if not service_type:
            return self._error("Service type is required", 400)
        
        try:
            services = self.storage.get_services_by_type(service_type)
            return self._success([service.to_dict() for service in services])
        except Exception as e:
            return self._error(f"Error retrieving services: {e}")
    

    # sensors data endpoint for telegram bot 
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def temperature_latest(self):
        data = {
            "value": 24.5,
            "unit": "°C",
            "timestamp": time.time()
        }
        return self._success(data)
        
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def pressure_latest(self):
        data = {
            "value": 1013.2,
            "unit": "hPa",
            "timestamp": time.time()
        }
        return self._success(data)