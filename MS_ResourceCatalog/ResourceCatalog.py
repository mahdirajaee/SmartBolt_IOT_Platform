import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

import cherrypy
import json
import time
import threading
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ResourceCatalog')

class ResourceCatalog:
    def __init__(self):
        self.services = {}  # Store registered services
        self.devices = {}   # Store registered devices
        
        # Load data from file if it exists
        self.load_data()
        
        # Start background thread for service liveness check
        self.start_liveness_check()
        
        # Start background thread for periodic data saving
        self.start_data_saving()
    
    def load_data(self):
        try:
            if os.path.exists('services.json'):
                with open('services.json', 'r') as f:
                    self.services = json.load(f)
                logger.info("Loaded services data from file")
            
            if os.path.exists('devices.json'):
                with open('devices.json', 'r') as f:
                    self.devices = json.load(f)
                logger.info("Loaded devices data from file")
        except Exception as e:
            logger.error(f"Error loading data: {e}")
    
    def save_data(self):
        try:
            with open('services.json', 'w') as f:
                json.dump(self.services, f, indent=2)
            
            with open('devices.json', 'w') as f:
                json.dump(self.devices, f, indent=2)
            
            logger.info("Saved catalog data to file")
        except Exception as e:
            logger.error(f"Error saving data: {e}")
    
    def start_liveness_check(self):
        def check_liveness():
            while True:
                try:
                    current_time = time.time()
                    # If service hasn't been seen for 60 seconds, mark as inactive
                    for service_id, service in list(self.services.items()):
                        if current_time - service["last_seen"] > 60:
                            if service["status"] != "inactive":
                                service["status"] = "inactive"
                                logger.info(f"Service {service_id} marked as inactive")
                    time.sleep(10)  # Check every 10 seconds
                except Exception as e:
                    logger.error(f"Error in service liveness check: {e}")
        
        thread = threading.Thread(target=check_liveness, daemon=True)
        thread.start()
        logger.info("Started service liveness check thread")
    
    def start_data_saving(self):
        def save_periodically():
            while True:
                try:
                    self.save_data()
                    time.sleep(60)  # Save every 60 seconds
                except Exception as e:
                    logger.error(f"Error in periodic data saving: {e}")
        
        thread = threading.Thread(target=save_periodically, daemon=True)
        thread.start()
        logger.info("Started periodic data saving thread")

class ServiceAPI:
    exposed = True
    
    def __init__(self, catalog):
        self.catalog = catalog
    
    @cherrypy.tools.json_out()
    def GET(self, service_id=None):
        if service_id is None:
            # Get all services
            logger.info("Getting all services")
            return {"services": self.catalog.services, "status": "success"}
        
        if service_id not in self.catalog.services:
            logger.warning(f"Service {service_id} not found")
            raise cherrypy.HTTPError(404, f"Service {service_id} not found")
        
        # Get specific service
        logger.info(f"Getting service {service_id}")
        return {"service": self.catalog.services[service_id], "status": "success"}
    
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def POST(self):
        # Register a new service
        data = cherrypy.request.json
        required_fields = ["name", "endpoint", "port"]
        
        for field in required_fields:
            if field not in data:
                logger.warning(f"Missing required field: {field}")
                raise cherrypy.HTTPError(400, f"Missing required field: {field}")
        
        service_id = data.get("name")
        
        if service_id in self.catalog.services:
            # Service already exists, update instead
            logger.info(f"Updating existing service {service_id}")
            self.catalog.services[service_id].update({
                "endpoint": data.get("endpoint"),
                "port": data.get("port"),
                "last_seen": time.time(),
                "status": "active",
            })
            # Update any additional info if provided
            if "additional_info" in data:
                self.catalog.services[service_id]["additional_info"] = data.get("additional_info")
            
            return {"message": f"Service {service_id} updated successfully", "status": "success"}
        
        # New service registration
        logger.info(f"Registering new service {service_id}")
        self.catalog.services[service_id] = {
            "name": service_id,
            "endpoint": data.get("endpoint"),
            "port": data.get("port"),
            "last_seen": time.time(),
            "status": "active",
            "additional_info": data.get("additional_info", {})
        }
        
        return {"message": f"Service {service_id} registered successfully", "status": "success"}
    
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def PUT(self, service_id):
        # Update a service
        if service_id not in self.catalog.services:
            logger.warning(f"Service {service_id} not found")
            raise cherrypy.HTTPError(404, f"Service {service_id} not found")
        
        data = cherrypy.request.json
        logger.info(f"Updating service {service_id}")
        
        # Update fields
        for key, value in data.items():
            if key != "name":  # Don't update the name/ID
                self.catalog.services[service_id][key] = value
        
        self.catalog.services[service_id]["last_seen"] = time.time()
        
        return {"message": f"Service {service_id} updated successfully", "status": "success"}
    
    @cherrypy.tools.json_out()
    def DELETE(self, service_id):
        # Remove a service
        if service_id not in self.catalog.services:
            logger.warning(f"Service {service_id} not found")
            raise cherrypy.HTTPError(404, f"Service {service_id} not found")
        
        logger.info(f"Removing service {service_id}")
        del self.catalog.services[service_id]
        
        return {"message": f"Service {service_id} removed successfully", "status": "success"}

class DeviceAPI:
    exposed = True
    
    def __init__(self, catalog):
        self.catalog = catalog
    
    @cherrypy.tools.json_out()
    def GET(self, device_id=None):
        if device_id is None:
            # Get all devices
            logger.info("Getting all devices")
            return {"devices": self.catalog.devices, "status": "success"}
        
        if device_id not in self.catalog.devices:
            logger.warning(f"Device {device_id} not found")
            raise cherrypy.HTTPError(404, f"Device {device_id} not found")
        
        # Get specific device
        logger.info(f"Getting device {device_id}")
        return {"device": self.catalog.devices[device_id], "status": "success"}
    
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def POST(self):
        # Register a new device
        data = cherrypy.request.json
        required_fields = ["device_id", "sector_id", "type"]
        
        for field in required_fields:
            if field not in data:
                logger.warning(f"Missing required field: {field}")
                raise cherrypy.HTTPError(400, f"Missing required field: {field}")
        
        device_id = data.get("device_id")
        
        if device_id in self.catalog.devices:
            # Device already exists, update instead
            logger.info(f"Updating existing device {device_id}")
            self.catalog.devices[device_id].update({
                "sector_id": data.get("sector_id"),
                "type": data.get("type"),
                "last_seen": time.time(),
                "status": "active",
            })
            # Update any additional info if provided
            if "additional_info" in data:
                self.catalog.devices[device_id]["additional_info"] = data.get("additional_info")
            
            return {"message": f"Device {device_id} updated successfully", "status": "success"}
        
        # New device registration
        logger.info(f"Registering new device {device_id}")
        self.catalog.devices[device_id] = {
            "device_id": device_id,
            "sector_id": data.get("sector_id"),
            "type": data.get("type"),
            "status": "active",
            "last_seen": time.time(),
            "additional_info": data.get("additional_info", {})
        }
        
        return {"message": f"Device {device_id} registered successfully", "status": "success"}
    
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def PUT(self, device_id):
        # Update a device
        if device_id not in self.catalog.devices:
            logger.warning(f"Device {device_id} not found")
            raise cherrypy.HTTPError(404, f"Device {device_id} not found")
        
        data = cherrypy.request.json
        logger.info(f"Updating device {device_id}")
        
        # Update fields
        for key, value in data.items():
            if key != "device_id":  # Don't update the ID
                self.catalog.devices[device_id][key] = value
        
        self.catalog.devices[device_id]["last_seen"] = time.time()
        
        return {"message": f"Device {device_id} updated successfully", "status": "success"}
    
    @cherrypy.tools.json_out()
    def DELETE(self, device_id):
        # Remove a device
        if device_id not in self.catalog.devices:
            logger.warning(f"Device {device_id} not found")
            raise cherrypy.HTTPError(404, f"Device {device_id} not found")
        
        logger.info(f"Removing device {device_id}")
        del self.catalog.devices[device_id]
        
        return {"message": f"Device {device_id} removed successfully", "status": "success"}

class SectorAPI:
    exposed = True
    
    def __init__(self, catalog):
        self.catalog = catalog
    
    @cherrypy.tools.json_out()
    def GET(self, sector_id=None):
        if sector_id is None:
            # Return unique sectors
            sectors = set(device["sector_id"] for device in self.catalog.devices.values())
            logger.info("Getting all sectors")
            return {"sectors": list(sectors), "status": "success"}
        
        # Get devices for a specific sector
        logger.info(f"Getting devices for sector {sector_id}")
        sector_devices = {
            device_id: device for device_id, device in self.catalog.devices.items() 
            if device.get("sector_id") == sector_id
        }
        
        return {"devices": sector_devices, "status": "success"}

class RootAPI:
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self):
        logger.info("API root endpoint accessed")
        return {
            "message": "Resource Catalog API",
            "version": "1.0",
            "endpoints": [
                "/service - Service management",
                "/device - Device management",
                "/sector - Sector information"
            ],
            "timestamp": time.time()
        }

def validate_password(realm, username, password):
    valid_username = os.getenv("API_USERNAME", "admin")
    valid_password = os.getenv("API_PASSWORD", "password")
    
    return username == valid_username and password == valid_password

def main():
    # Get configuration from environment variables or use defaults
    port = int(os.getenv("RESOURCE_CATALOG_PORT", 8080))
    enable_auth = os.getenv("ENABLE_AUTH", "false").lower() == "true"
    
    # Create the catalog instance
    catalog = ResourceCatalog()
    
    # Configure CherryPy
    conf = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True,
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'application/json')],
        }
    }
    
    # Add basic authentication if enabled
    if enable_auth:
        conf['/']['tools.auth_basic.on'] = True
        conf['/']['tools.auth_basic.realm'] = 'Resource Catalog'
        conf['/']['tools.auth_basic.checkpassword'] = validate_password
        logger.info("Basic authentication enabled")
    
    # Mount the API endpoints
    root = RootAPI()
    root.service = ServiceAPI(catalog)
    root.device = DeviceAPI(catalog)
    root.sector = SectorAPI(catalog)
    
    # Configure CherryPy server
    cherrypy.config.update({
        'server.socket_host': os.getenv("RESOURCE_CATALOG_HOST", '0.0.0.0'),
        'server.socket_port': port,
        'engine.autoreload.on': False,
        'log.screen': True
    })
    
    # Start the server
    cherrypy.tree.mount(root, '/', conf)
    
    logger.info(f"Starting Resource Catalog API on port {port}")
    cherrypy.engine.start()
    cherrypy.engine.block()

if __name__ == "__main__":
    main()