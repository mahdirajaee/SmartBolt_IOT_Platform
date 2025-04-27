import os
import cherrypy
import logging
from api import ResourceCatalogAPI
from storage import StorageManager
from config import Config

def setup_logging(config):
    """Configure logging based on application config"""
    log_level = getattr(logging, config.get("logging", "level").upper(), logging.INFO)
    log_file = config.get("logging", "file")
    
    # Configure cherrypy logging
    cherrypy.config.update({
        'log.screen': True,
        'log.access_file': '',
        'log.error_file': log_file
    })
    
    # Configure application logging
    logger = logging.getLogger('resource_catalog')
    logger.setLevel(log_level)
    
    # Create file handler
    file_handler = logging.FileHandler(log_file, 'a')
    file_handler.setLevel(log_level)
    
    # Create formatter and add it to the handler
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    
    # Add handler to the logger
    logger.addHandler(file_handler)
    
    return logger

def main():
    # Load configuration
    config = Config()
    
    # Setup logging
    logger = setup_logging(config)
    logger.info("Starting Resource Catalog service")
    
    # Initialize storage
    storage = StorageManager(config.get("storage", "db_path"))
    
    # Initialize API
    api = ResourceCatalogAPI(storage, config)
    
    # Configure CherryPy
    cherrypy.config.update({
        'server.socket_host': config.get("server", "host"),
        'server.socket_port': config.get("server", "port"),
        'engine.autoreload.on': False,
        'tools.sessions.on': False,
    })
    
    # API endpoint configuration
    conf = {
        '/': {
            'tools.sessions.on': False,
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'application/json')],
            'tools.gzip.on': True,
            'tools.encode.on': True,
            'tools.encode.encoding': 'utf-8',
        },
    }
    
    # Mount API endpoints
    cherrypy.tree.mount(api, '/', conf)
    
    # # Print startup message
    # logger.info(f"Resource Catalog started on {config.get('server', 'host')}:{config.get('server', 'port')}")
    # print(f"Resource Catalog started on {config.get('server', 'host')}:{config.get('server', 'port')}")
    # print(f"Available endpoints:")
    # print(f"  - GET    /devices             - List all devices")
    # print(f"  - GET    /device?device_id=X  - Get device by ID")
    # print(f"  - POST   /register_device     - Register a new device")
    # print(f"  - POST   /update_device_status - Update device status")
    # print(f"  - GET    /devices_by_type?device_type=X - Get devices by type")
    # print(f"  - GET    /online_devices      - Get all online devices")
    # print(f"  - GET    /services            - List all services")
    # print(f"  - GET    /service?service_id=X - Get service by ID")
    # print(f"  - POST   /register_service    - Register a new service")
    # print(f"  - POST   /update_service_status - Update service status")
    # print(f"  - GET    /services_by_type?service_type=X - Get services by type")
    
    # Start the server
    try:
        cherrypy.engine.start()
        cherrypy.engine.block()
    except KeyboardInterrupt:
        cherrypy.engine.stop()
        logger.info("Resource Catalog service stopped")

if __name__ == "__main__":
    main()