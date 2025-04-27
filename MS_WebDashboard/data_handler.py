import json
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from config import CONFIG

logger = logging.getLogger(__name__)

class DataHandler:
    """Handles data fetching and processing for the dashboard"""
    
    def __init__(self):
        self.resource_catalog_url = CONFIG["resource_catalog"]["url"]
        self.timeseries_db_url = CONFIG["timeseries_db"]["url"]
        self.analytics_url = CONFIG["analytics_service"]["url"]
        self.raspberry_pi_url = CONFIG["raspberry_pi_connector"]["url"]
        self.account_manager_url = CONFIG["account_manager"]["url"]
        self.auth_token = None
        
    def login(self, username, password):
        """Login to the account manager and get auth token"""
        try:
            payload = {
                "username": username,
                "password": password
            }
            
            response = requests.post(
                f"{self.account_manager_url}/login",
                json=payload
            )
            
            if response.status_code == 200:
                data = response.json()
                if data["status"] == "success" and "token" in data["data"]:
                    self.auth_token = data["data"]["token"]
                    return True, data["data"]["user"]
                else:
                    logger.error(f"Login failed: {data.get('message', 'Unknown error')}")
                    return False, data.get('message', 'Login failed')
            else:
                logger.error(f"Login failed: {response.status_code}")
                return False, f"Login failed with status code: {response.status_code}"
        except Exception as e:
            logger.error(f"Error during login: {str(e)}")
            return False, str(e)
            
    def register_user(self, username, email, password, role="user"):
        """Register a new user account"""
        try:
            # For registration, we need to be authenticated as admin
            if not self.auth_token:
                logger.error("Authentication required for user registration")
                return False, "Authentication required"
                
            payload = {
                "username": username,
                "email": email,
                "password": password,
                "role": role
            }
            
            headers = {
                "Authorization": f"Bearer {self.auth_token}"
            }
            
            response = requests.post(
                f"{self.account_manager_url}/register",
                json=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if data["status"] == "success":
                    return True, data["data"]
                else:
                    logger.error(f"Registration failed: {data.get('message', 'Unknown error')}")
                    return False, data.get('message', 'Registration failed')
            else:
                error_msg = f"Registration failed with status code: {response.status_code}"
                try:
                    error_data = response.json()
                    if "message" in error_data:
                        error_msg = error_data["message"]
                except:
                    pass
                    
                logger.error(error_msg)
                return False, error_msg
        except Exception as e:
            logger.error(f"Error during registration: {str(e)}")
            return False, str(e)
    
    def get_all_devices(self):
        """Get all registered devices from the resource catalog"""
        try:
            response = requests.get(f"{self.resource_catalog_url}/api/resources")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to fetch devices: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error fetching devices: {str(e)}")
            return []
            
    def get_sensor_data(self, device_id, sensor_type, hours=24):
        """Get sensor data for specific device and sensor type"""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            
            params = {
                "device_id": device_id,
                "sensor_type": sensor_type,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            }
            
            response = requests.get(
                f"{self.timeseries_db_url}/api/data/query", 
                params=params
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Convert to pandas DataFrame for easier manipulation
                if data and len(data) > 0:
                    df = pd.DataFrame(data)
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    return df
                return pd.DataFrame()
            else:
                logger.error(f"Failed to fetch sensor data: {response.status_code}")
                return pd.DataFrame()
        except Exception as e:
            logger.error(f"Error fetching sensor data: {str(e)}")
            return pd.DataFrame()
    
    def get_alerts(self, hours=24):
        """Get recent alerts from the analytics service"""
        try:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
            
            params = {
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            }
            
            response = requests.get(
                f"{self.analytics_url}/api/alerts", 
                params=params
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to fetch alerts: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error fetching alerts: {str(e)}")
            return []
            
    def get_system_status(self):
        """Get overall system status"""
        statuses = {}
        services = [
            {"name": "Resource Catalog", "url": f"{self.resource_catalog_url}/health"},
            {"name": "Timeseries DB", "url": f"{self.timeseries_db_url}/health"},
            {"name": "Analytics", "url": f"{self.analytics_url}/health"},
            {"name": "RaspberryPi Connector", "url": f"{self.raspberry_pi_url}/health"}
        ]
        
        for service in services:
            try:
                response = requests.get(service["url"], timeout=2)
                statuses[service["name"]] = response.status_code == 200
            except:
                statuses[service["name"]] = False
                
        return statuses
        
    def send_command(self, device_id, command, params=None):
        """Send command to a device via raspberry pi connector"""
        try:
            payload = {
                "device_id": device_id,
                "command": command
            }
            
            if params:
                payload["params"] = params
                
            response = requests.post(
                f"{self.raspberry_pi_url}/api/command",
                json=payload
            )
            
            return response.status_code == 200, response.json()
        except Exception as e:
            logger.error(f"Error sending command: {str(e)}")
            return False, {"error": str(e)}