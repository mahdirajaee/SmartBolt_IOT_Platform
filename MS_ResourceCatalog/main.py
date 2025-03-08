import cherrypy
import json
import time
import os
import datetime
import logging
import uuid

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("catalog.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ResourceCatalog")

class ResourceCatalog:
    exposed = True
    
    def __init__(self):
        self.devices = {}
        self.services = {}
        self.sectors = {}
        self.load_config()
        self.start_cleanup_thread()
        logger.info("Resource/Service Catalog initialized")
    
    def load_config(self):
        try:
            config_path = os.environ.get('CONFIG_PATH', 'config.json')
            
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                
                self.catalog_endpoint = config.get('catalog_endpoint', 'http://localhost:8080')
                self.expiration_time = config.get('expiration_time', 120)
                self.cleanup_interval = config.get('cleanup_interval', 60)
                
                if 'initial_services' in config:
                    self.services = config['initial_services']
                
                logger.info("Configuration loaded successfully")
            else:
                logger.warning(f"Configuration file {config_path} not found, using defaults")
                self.catalog_endpoint = 'http://localhost:8080'
                self.expiration_time = 120
                self.cleanup_interval = 60
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            self.catalog_endpoint = 'http://localhost:8080'
            self.expiration_time = 120
            self.cleanup_interval = 60
    
    def start_cleanup_thread(self):
        def cleanup():
            while True:
                self.cleanup_expired_entries()
                time.sleep(self.cleanup_interval)
        
        cherrypy.engine.subscribe('start', lambda: cherrypy.process.plugins.BackgroundTask(1, cleanup).start())
        logger.info("Started cleanup thread")
    
    def cleanup_expired_entries(self):
        current_time = time.time()
        
        expired_devices = []
        for device_id, device_info in self.devices.items():
            if current_time - device_info.get('last_update', 0) > self.expiration_time:
                expired_devices.append(device_id)
        
        for device_id in expired_devices:
            logger.info(f"Removing expired device: {device_id}")
            self.devices.pop(device_id, None)
        
        expired_services = []
        for service_id, service_info in self.services.items():
            if current_time - service_info.get('last_update', 0) > self.expiration_time:
                expired_services.append(service_id)
        
        for service_id in expired_services:
            logger.info(f"Removing expired service: {service_id}")
            self.services.pop(service_id, None)
    
    @cherrypy.tools.json_out()
    def GET(self, *uri, **params):
        if len(uri) == 0:
            return {
                'devices': self.devices,
                'services': self.services,
                'sectors': self.sectors
            }
        
        resource_type = uri[0]
        
        if resource_type == 'devices':
            if len(uri) == 1:
                return {'devices': self.devices}
            elif len(uri) == 2:
                device_id = uri[1]
                if device_id in self.devices:
                    return {'device': self.devices[device_id]}
                else:
                    raise cherrypy.HTTPError(404, f"Device {device_id} not found")
        
        elif resource_type == 'services':
            if len(uri) == 1:
                return {'services': self.services}
            elif len(uri) == 2:
                service_id = uri[1]
                if service_id in self.services:
                    return {'service': self.services[service_id]}
                else:
                    raise cherrypy.HTTPError(404, f"Service {service_id} not found")
            elif len(uri) == 3 and uri[1] == 'type':
                service_type = uri[2]
                filtered_services = {k: v for k, v in self.services.items() 
                                    if v.get('type') == service_type}
                return {'services': filtered_services}
        
        elif resource_type == 'sectors':
            if len(uri) == 1:
                return {'sectors': self.sectors}
            elif len(uri) == 2:
                sector_id = uri[1]
                if sector_id in self.sectors:
                    return {'sector': self.sectors[sector_id]}
                else:
                    raise cherrypy.HTTPError(404, f"Sector {sector_id} not found")
            elif len(uri) == 3 and uri[2] == 'devices':
                sector_id = uri[1]
                if sector_id in self.sectors:
                    sector_devices = {k: v for k, v in self.devices.items() 
                                     if v.get('sector_id') == sector_id}
                    return {'devices': sector_devices}
                else:
                    raise cherrypy.HTTPError(404, f"Sector {sector_id} not found")
        
        elif resource_type == 'info':
            return {
                'name': 'Smart IoT Bolt Resource/Service Catalog',
                'version': '1.0',
                'uptime': time.time() - self._start_time if hasattr(self, '_start_time') else 0,
                'endpoints': {
                    'devices': f"{self.catalog_endpoint}/devices",
                    'services': f"{self.catalog_endpoint}/services",
                    'sectors': f"{self.catalog_endpoint}/sectors"
                }
            }
            
        elif resource_type == 'broker':
            broker_services = {k: v for k, v in self.services.items() 
                              if v.get('type') == 'messageBroker'}
            if broker_services:
                return list(broker_services.values())[0]
            else:
                return {
                    'address': 'localhost',
                    'port': 1883
                }
        
        raise cherrypy.HTTPError(404, "Resource not found")
    
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def POST(self, *uri, **params):
        if len(uri) == 0:
            raise cherrypy.HTTPError(400, "Invalid request: resource type not specified")
        
        resource_type = uri[0]
        request_data = cherrypy.request.json
        
        if resource_type == 'devices':
            if 'id' not in request_data:
                request_data['id'] = f"device_{uuid.uuid4().hex[:8]}"
            
            device_id = request_data['id']
            request_data['last_update'] = time.time()
            
            self.devices[device_id] = request_data
            logger.info(f"Device {device_id} registered")
            return {'status': 'success', 'id': device_id, 'message': f"Device {device_id} registered successfully"}
        
        elif resource_type == 'services':
            if 'id' not in request_data:
                request_data['id'] = f"service_{uuid.uuid4().hex[:8]}"
            
            service_id = request_data['id']
            request_data['last_update'] = time.time()
            
            self.services[service_id] = request_data
            logger.info(f"Service {service_id} registered")
            return {'status': 'success', 'id': service_id, 'message': f"Service {service_id} registered successfully"}
        
        elif resource_type == 'sectors':
            if 'id' not in request_data:
                request_data['id'] = f"sector_{uuid.uuid4().hex[:8]}"
            
            sector_id = request_data['id']
            self.sectors[sector_id] = request_data
            logger.info(f"Sector {sector_id} created")
            return {'status': 'success', 'id': sector_id, 'message': f"Sector {sector_id} created successfully"}
        
        raise cherrypy.HTTPError(400, "Invalid resource type")
    
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def PUT(self, *uri, **params):
        if len(uri) < 2:
            raise cherrypy.HTTPError(400, "Invalid request: resource type and ID required")
        
        resource_type = uri[0]
        resource_id = uri[1]
        request_data = cherrypy.request.json
        
        if resource_type == 'devices':
            if resource_id not in self.devices:
                raise cherrypy.HTTPError(404, f"Device {resource_id} not found")
            
            request_data['last_update'] = time.time()
            self.devices[resource_id].update(request_data)
            logger.info(f"Device {resource_id} updated")
            return {'status': 'success', 'message': f"Device {resource_id} updated successfully"}
        
        elif resource_type == 'services':
            if resource_id not in self.services:
                raise cherrypy.HTTPError(404, f"Service {resource_id} not found")
            
            request_data['last_update'] = time.time()
            self.services[resource_id].update(request_data)
            logger.info(f"Service {resource_id} updated")
            return {'status': 'success', 'message': f"Service {resource_id} updated successfully"}
        
        elif resource_type == 'sectors':
            if resource_id not in self.sectors:
                raise cherrypy.HTTPError(404, f"Sector {resource_id} not found")
            
            self.sectors[resource_id].update(request_data)
            logger.info(f"Sector {resource_id} updated")
            return {'status': 'success', 'message': f"Sector {resource_id} updated successfully"}
        
        raise cherrypy.HTTPError(400, "Invalid resource type")
    
    @cherrypy.tools.json_out()
    def DELETE(self, *uri, **params):
        if len(uri) < 2:
            raise cherrypy.HTTPError(400, "Invalid request: resource type and ID required")
        
        resource_type = uri[0]
        resource_id = uri[1]
        
        if resource_type == 'devices':
            if resource_id not in self.devices:
                raise cherrypy.HTTPError(404, f"Device {resource_id} not found")
            
            del self.devices[resource_id]
            logger.info(f"Device {resource_id} deleted")
            return {'status': 'success', 'message': f"Device {resource_id} deleted successfully"}
        
        elif resource_type == 'services':
            if resource_id not in self.services:
                raise cherrypy.HTTPError(404, f"Service {resource_id} not found")
            
            del self.services[resource_id]
            logger.info(f"Service {resource_id} deleted")
            return {'status': 'success', 'message': f"Service {resource_id} deleted successfully"}
        
        elif resource_type == 'sectors':
            if resource_id not in self.sectors:
                raise cherrypy.HTTPError(404, f"Sector {resource_id} not found")
            
            del self.sectors[resource_id]
            logger.info(f"Sector {resource_id} deleted")
            return {'status': 'success', 'message': f"Sector {resource_id} deleted successfully"}
        
        raise cherrypy.HTTPError(400, "Invalid resource type")

def main():
    os.makedirs('config', exist_ok=True)
    
    config_path = os.environ.get('CONFIG_PATH', 'config.json')
    if not os.path.exists(config_path):
        default_config = {
            'catalog_endpoint': 'http://localhost:8080',
            'expiration_time': 120,
            'cleanup_interval': 60,
            'initial_services': {
                'message_broker': {
                    'id': 'message_broker',
                    'type': 'messageBroker',
                    'name': 'MQTT Message Broker',
                    'address': 'localhost',
                    'port': 1883,
                    'last_update': time.time()
                }
            }
        }
        
        with open(config_path, 'w') as f:
            json.dump(default_config, f, indent=4)
        
        logger.info(f"Created default configuration file: {config_path}")
    
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': int(os.environ.get('PORT', '8080')),
        'log.access_file': 'access.log',
        'log.error_file': 'error.log'
    })
    
    catalog = ResourceCatalog()
    catalog._start_time = time.time()
    
    conf = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True,
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'application/json')],
        }
    }
    
    cherrypy.tree.mount(catalog, '/', conf)
    
    try:
        cherrypy.engine.start()
        logger.info(f"Resource/Service Catalog running on port {cherrypy.server.socket_port}")
        cherrypy.engine.block()
    except KeyboardInterrupt:
        cherrypy.engine.stop()
        logger.info("Resource/Service Catalog stopped")

if __name__ == '__main__':
    main()