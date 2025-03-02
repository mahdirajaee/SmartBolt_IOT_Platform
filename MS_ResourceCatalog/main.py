import cherrypy
import json
import time
import os
import datetime

class ResourceCatalog:
    exposed = True
    
    def __init__(self):
        # Initialize with empty data structures
        self.devices = {}  # Dictionary to store device information
        self.services = {}  # Dictionary to store service information
        self.sectors = {}  # Dictionary to store sector information
        
        # Load configurations
        self.load_config()
        
        # Cleanup thread for stale entries
        self.start_cleanup_thread()
    
    def load_config(self):
        """Load configuration from file or environment variables"""
        try:
            # Configuration path from environment or default
            config_path = os.environ.get('CONFIG_PATH', 'config.json')
            
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            self.catalog_endpoint = config.get('catalog_endpoint', 'http://localhost:8080')
            self.expiration_time = config.get('expiration_time', 120)  # seconds
            self.cleanup_interval = config.get('cleanup_interval', 60)  # seconds
            
            # Initial services if any
            if 'initial_services' in config:
                self.services = config['initial_services']
            
            print("Configuration loaded successfully")
        except Exception as e:
            print(f"Error loading configuration: {e}")
            # Set defaults
            self.catalog_endpoint = 'http://localhost:8080'
            self.expiration_time = 120  # seconds
            self.cleanup_interval = 60  # seconds
    
    def start_cleanup_thread(self):
        """Start a CherryPy thread to clean up expired entries"""
        def cleanup():
            while True:
                self.cleanup_expired_entries()
                time.sleep(self.cleanup_interval)
        
        cherrypy.engine.subscribe('start', lambda: cherrypy.process.plugins.BackgroundTask(1, cleanup).start())
    
    def cleanup_expired_entries(self):
        """Remove expired devices and services"""
        current_time = time.time()
        
        # Clean devices
        expired_devices = []
        for device_id, device_info in self.devices.items():
            if current_time - device_info.get('last_update', 0) > self.expiration_time:
                expired_devices.append(device_id)
        
        for device_id in expired_devices:
            print(f"Removing expired device: {device_id}")
            self.devices.pop(device_id, None)
        
        # Clean services
        expired_services = []
        for service_id, service_info in self.services.items():
            if current_time - service_info.get('last_update', 0) > self.expiration_time:
                expired_services.append(service_id)
        
        for service_id in expired_services:
            print(f"Removing expired service: {service_id}")
            self.services.pop(service_id, None)
    
    @cherrypy.tools.json_out()
    def GET(self, *uri, **params):
        """Handle GET requests for retrieving information"""
        if len(uri) == 0:
            # Return full catalog info
            return {
                'devices': self.devices,
                'services': self.services,
                'sectors': self.sectors
            }
        
        resource_type = uri[0]
        
        if resource_type == 'devices':
            # Handle devices requests
            if len(uri) == 1:
                # Return all devices
                return {'devices': self.devices}
            elif len(uri) == 2:
                device_id = uri[1]
                if device_id in self.devices:
                    return {'device': self.devices[device_id]}
                else:
                    raise cherrypy.HTTPError(404, f"Device {device_id} not found")
        
        elif resource_type == 'services':
            # Handle services requests
            if len(uri) == 1:
                # Return all services
                return {'services': self.services}
            elif len(uri) == 2:
                service_id = uri[1]
                if service_id in self.services:
                    return {'service': self.services[service_id]}
                else:
                    raise cherrypy.HTTPError(404, f"Service {service_id} not found")
            elif len(uri) == 3 and uri[1] == 'type':
                # Filter services by type
                service_type = uri[2]
                filtered_services = {k: v for k, v in self.services.items() 
                                    if v.get('type') == service_type}
                return {'services': filtered_services}
        
        elif resource_type == 'sectors':
            # Handle sectors requests
            if len(uri) == 1:
                # Return all sectors
                return {'sectors': self.sectors}
            elif len(uri) == 2:
                sector_id = uri[1]
                if sector_id in self.sectors:
                    return {'sector': self.sectors[sector_id]}
                else:
                    raise cherrypy.HTTPError(404, f"Sector {sector_id} not found")
            elif len(uri) == 3 and uri[2] == 'devices':
                # Get all devices in a sector
                sector_id = uri[1]
                if sector_id in self.sectors:
                    sector_devices = {k: v for k, v in self.devices.items() 
                                     if v.get('sector_id') == sector_id}
                    return {'devices': sector_devices}
                else:
                    raise cherrypy.HTTPError(404, f"Sector {sector_id} not found")
        
        # If nothing matched, return 404
        raise cherrypy.HTTPError(404, "Resource not found")
    
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def POST(self, *uri, **params):
        """Handle POST requests for creating new entries"""
        if len(uri) == 0:
            raise cherrypy.HTTPError(400, "Invalid request: resource type not specified")
        
        resource_type = uri[0]
        request_data = cherrypy.request.json
        
        if resource_type == 'devices':
            # Register a new device
            if 'id' not in request_data:
                raise cherrypy.HTTPError(400, "Device ID is required")
            
            device_id = request_data['id']
            # Add timestamp for expiration check
            request_data['last_update'] = time.time()
            
            self.devices[device_id] = request_data
            return {'status': 'success', 'message': f"Device {device_id} registered successfully"}
        
        elif resource_type == 'services':
            # Register a new service
            if 'id' not in request_data:
                raise cherrypy.HTTPError(400, "Service ID is required")
            
            service_id = request_data['id']
            # Add timestamp for expiration check
            request_data['last_update'] = time.time()
            
            self.services[service_id] = request_data
            return {'status': 'success', 'message': f"Service {service_id} registered successfully"}
        
        elif resource_type == 'sectors':
            # Create a new sector
            if 'id' not in request_data:
                raise cherrypy.HTTPError(400, "Sector ID is required")
            
            sector_id = request_data['id']
            self.sectors[sector_id] = request_data
            return {'status': 'success', 'message': f"Sector {sector_id} created successfully"}
        
        # If nothing matched, return 400
        raise cherrypy.HTTPError(400, "Invalid resource type")
    
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def PUT(self, *uri, **params):
        """Handle PUT requests for updating existing entries"""
        if len(uri) < 2:
            raise cherrypy.HTTPError(400, "Invalid request: resource type and ID required")
        
        resource_type = uri[0]
        resource_id = uri[1]
        request_data = cherrypy.request.json
        
        if resource_type == 'devices':
            # Update an existing device
            if resource_id not in self.devices:
                raise cherrypy.HTTPError(404, f"Device {resource_id} not found")
            
            # Update timestamp
            request_data['last_update'] = time.time()
            
            # Update device information
            self.devices[resource_id].update(request_data)
            return {'status': 'success', 'message': f"Device {resource_id} updated successfully"}
        
        elif resource_type == 'services':
            # Update an existing service
            if resource_id not in self.services:
                raise cherrypy.HTTPError(404, f"Service {resource_id} not found")
            
            # Update timestamp
            request_data['last_update'] = time.time()
            
            # Update service information
            self.services[resource_id].update(request_data)
            return {'status': 'success', 'message': f"Service {resource_id} updated successfully"}
        
        elif resource_type == 'sectors':
            # Update an existing sector
            if resource_id not in self.sectors:
                raise cherrypy.HTTPError(404, f"Sector {resource_id} not found")
            
            # Update sector information
            self.sectors[resource_id].update(request_data)
            return {'status': 'success', 'message': f"Sector {resource_id} updated successfully"}
        
        # If nothing matched, return 400
        raise cherrypy.HTTPError(400, "Invalid resource type")
    
    @cherrypy.tools.json_out()
    def DELETE(self, *uri, **params):
        """Handle DELETE requests for removing entries"""
        if len(uri) < 2:
            raise cherrypy.HTTPError(400, "Invalid request: resource type and ID required")
        
        resource_type = uri[0]
        resource_id = uri[1]
        
        if resource_type == 'devices':
            # Delete a device
            if resource_id not in self.devices:
                raise cherrypy.HTTPError(404, f"Device {resource_id} not found")
            
            del self.devices[resource_id]
            return {'status': 'success', 'message': f"Device {resource_id} deleted successfully"}
        
        elif resource_type == 'services':
            # Delete a service
            if resource_id not in self.services:
                raise cherrypy.HTTPError(404, f"Service {resource_id} not found")
            
            del self.services[resource_id]
            return {'status': 'success', 'message': f"Service {resource_id} deleted successfully"}
        
        elif resource_type == 'sectors':
            # Delete a sector
            if resource_id not in self.sectors:
                raise cherrypy.HTTPError(404, f"Sector {resource_id} not found")
            
            del self.sectors[resource_id]
            return {'status': 'success', 'message': f"Sector {resource_id} deleted successfully"}
        
        # If nothing matched, return 400
        raise cherrypy.HTTPError(400, "Invalid resource type")

# Create a configuration file example
def create_config_file():
    """Create an example configuration file if not exists"""
    if not os.path.exists('config.json'):
        config = {
            'catalog_endpoint': 'http://localhost:8080',
            'expiration_time': 120,  # seconds
            'cleanup_interval': 60,  # seconds
            'initial_services': {
                'control_center': {
                    'id': 'control_center',
                    'type': 'control',
                    'endpoint': 'http://localhost:8081',
                    'last_update': time.time()
                }
            }
        }
        
        with open('config.json', 'w') as f:
            json.dump(config, f, indent=4)
        
        print("Created example configuration file: config.json")

if __name__ == '__main__':
    # Create example config file if not exists
    create_config_file()
    
    # Configure CherryPy server
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 8080
    })
    
    # Mount the application
    conf = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True,
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'application/json')],
        }
    }
    
    cherrypy.tree.mount(ResourceCatalog(), '/', conf)
    
    # Start the server
    try:
        cherrypy.engine.start()
        print(f"Resource/Service Catalog running on port 8080")
        cherrypy.engine.block()
    except KeyboardInterrupt:
        cherrypy.engine.stop()