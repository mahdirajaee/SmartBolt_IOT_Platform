import json
import logging
import requests
import time

class CatalogClient:
    def __init__(self, config_path="config.json"):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.catalog_url = self.config["resource_catalog"]["url"]
        self.service_info = self.config["service"]
        self.logger = logging.getLogger("catalog_client")
    
    def register_service(self):
        try:
            service_data = {
                "service_id": self.service_info["id"],
                "name": self.service_info["name"],
                "description": self.service_info["description"],
                "service_type": self.service_info["type"],
                "endpoints": {
                    "api": f"http://localhost:{self.service_info['port']}"
                },
                "status": "online"
            }
            
            response = requests.post(
                f"{self.catalog_url}/register_service",
                json=service_data
            )
            
            if response.status_code == 200 or response.status_code == 201:
                self.logger.info(f"Service registered successfully with ID: {self.service_info['id']}")
                return True
            else:
                self.logger.error(f"Failed to register service: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error registering service: {str(e)}")
            return False
    
    def update_service_status(self):
        try:
            update_data = {
                "service_id": self.service_info["id"],
                "status": "active"
            }
            
            response = requests.post(
                f"{self.catalog_url}/update_service_status",
                json=update_data
            )
            
            if response.status_code == 200:
                self.logger.debug("Service status updated successfully")
                return True
            else:
                self.logger.error(f"Failed to update service status: {response.text}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error updating service status: {str(e)}")
            return False
    
    def discover_service(self, service_id):
        try:
            response = requests.get(f"{self.catalog_url}/services/{service_id}")
            
            if response.status_code == 200:
                service_data = response.json()
                return service_data
            else:
                self.logger.error(f"Failed to discover service {service_id}: {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error discovering service {service_id}: {str(e)}")
            return None

    def get_latest_sensor_data(self, sensor_type):
        try:
            response = requests.get(f"{self.catalog_url}/sensors/data/{sensor_type}/latest")
            
            if response.status_code == 200:
                sensor_data = response.json()
                return sensor_data
            else:
                self.logger.error(f"Failed to get latest {sensor_type} data: {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting latest {sensor_type} data: {str(e)}")
            return None 