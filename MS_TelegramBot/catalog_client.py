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
            # Get TimeSeries DB URL from config
            timeseries_url = "http://localhost:8084"
            
            # Use the device_id as primary sensor for now
            if sensor_type.lower() == "temperature":
                device_id = "temp_sensor_1"
                url = f"{timeseries_url}/sensor_data?device_id={device_id}&sensor_type=temperature&limit=1"
            elif sensor_type.lower() == "pressure":
                device_id = "pressure_sensor_1"
                url = f"{timeseries_url}/sensor_data?device_id={device_id}&sensor_type=pressure&limit=1"
            else:
                self.logger.error(f"Unknown sensor type: {sensor_type}")
                return None
            
            # Make REST API call to Time Series DB
            response = requests.get(url)
            
            if response.status_code == 200:
                data = response.json()
                if data and "data" in data and len(data["data"]) > 0:
                    # Use the latest reading
                    latest = data["data"][0]
                    result = {
                        "value": latest["value"],
                        "unit": latest["unit"] if "unit" in latest else self._get_default_unit(sensor_type),
                        "timestamp": latest["timestamp"] if "timestamp" in latest else time.time()
                    }
                    return result
                else:
                    # Fallback to mock data if no results returned
                    self.logger.warning(f"No data returned from TimeSeries DB for {sensor_type}, using mock data")
                    return self._get_mock_data(sensor_type)
            else:
                self.logger.error(f"Failed to get data from TimeSeries DB: {response.status_code} - {response.text}")
                # Fallback to mock data
                return self._get_mock_data(sensor_type)
                
        except Exception as e:
            self.logger.error(f"Error getting latest {sensor_type} data: {str(e)}")
            # Fallback to mock data on error
            return self._get_mock_data(sensor_type)
            
    def _get_default_unit(self, sensor_type):
        if sensor_type.lower() == "temperature":
            return "°C"
        elif sensor_type.lower() == "pressure":
            return "hPa"
        return ""
        
    def _get_mock_data(self, sensor_type):
        if sensor_type.lower() == "temperature":
            return {
                "value": 24.5,
                "unit": "°C",
                "timestamp": time.time()
            }
        elif sensor_type.lower() == "pressure":
            return {
                "value": 1013.2,
                "unit": "hPa",
                "timestamp": time.time()
            }
        return None