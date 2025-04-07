"""
MS_ControlCenter for Smart IoT Bolt for Pipelines
"""
import sys
import os
import time
import json
import threading
import requests
from dotenv import load_dotenv

# Apply CherryPy patch before importing it
from cherrypy_patch import patch_cherrypy
patch_cherrypy()

import cherrypy
import paho.mqtt.client as mqtt

# Load environment variables
load_dotenv()

class MS_ControlCenter:
    def __init__(self):
        self.service_id = "control_center"
        self.service_name = "Control Center Microservice"
        self.catalog_url = os.getenv('CATALOG_URL', 'http://localhost:8080')
        self.host = os.getenv('HOST', '0.0.0.0')
        self.port = int(os.getenv('PORT', 8083))
        
        # Initialize services and endpoints
        self.endpoints = {}
        self.mqtt_client = None
        self.mqtt_broker = None
        self.mqtt_port = None
        
        # Threshold values for control decisions
        self.temp_threshold = float(os.getenv('TEMP_THRESHOLD', '80.0'))  # Default 80°C
        self.pressure_threshold = float(os.getenv('PRESSURE_THRESHOLD', '10.0'))  # Default 10 bar
        
        # Register with catalog and get service information
        self.register_with_catalog()
        self.get_service_info()
        self.connect_mqtt()

    def register_with_catalog(self):
        """Register this service with the Resource Catalog"""
        registration_data = {
            "name": self.service_id,
            "endpoint": f"http://{self.host}:{self.port}",
            "port": self.port,
            "last_seen": time.time(),
            "additional_info": {
                "service_name": self.service_name
            }
        }
        
        try:
            response = requests.post(f"{self.catalog_url}/service", json=registration_data)
            if response.status_code == 200 or response.status_code == 201:
                print(f"Successfully registered with the catalog at {self.catalog_url}")
            else:
                print(f"Failed to register with catalog. Status code: {response.status_code}")
        except requests.RequestException as e:
            print(f"Error registering with catalog: {e}")

    def get_service_info(self):
        """Get information about required services from the catalog"""
        try:
            # Get Analytics service endpoint
            response = requests.get(f"{self.catalog_url}/service/analytics")
            if response.status_code == 200:
                analytics_info = response.json()
                self.endpoints["analytics"] = analytics_info.get("endpoint")
            else:
                print(f"Failed to get analytics service info. Status code: {response.status_code}")
            
            # Try different possible MQTT broker endpoint paths
            mqtt_endpoints = ["/mqtt", "/broker", "/service/mqtt_broker"]
            for endpoint in mqtt_endpoints:
                try:
                    response = requests.get(f"{self.catalog_url}{endpoint}")
                    if response.status_code == 200:
                        mqtt_info = response.json()
                        if "broker" in mqtt_info:
                            self.mqtt_broker = mqtt_info.get("broker")
                            self.mqtt_port = int(mqtt_info.get("port", 1883))
                            print(f"Found MQTT broker at {self.mqtt_broker}:{self.mqtt_port}")
                            break
                except requests.RequestException:
                    continue
            
            # Try different possible config endpoint paths
            config_endpoints = ["/config/thresholds", "/thresholds", "/service/config"]
            for endpoint in config_endpoints:
                try:
                    response = requests.get(f"{self.catalog_url}{endpoint}")
                    if response.status_code == 200:
                        config = response.json()
                        if "temperature" in config:
                            self.temp_threshold = float(config.get("temperature", self.temp_threshold))
                            self.pressure_threshold = float(config.get("pressure", self.pressure_threshold))
                            print(f"Found config values: temp={self.temp_threshold}, pressure={self.pressure_threshold}")
                            break
                except requests.RequestException:
                    continue
                
        except requests.RequestException as e:
            print(f"Error retrieving service information: {e}")

    def connect_mqtt(self):
        """Connect to the MQTT broker"""
        if not self.mqtt_broker:
            print("MQTT broker information not available")
            return
            
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message
        
        try:
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.mqtt_client.loop_start()
            print(f"Connected to MQTT broker at {self.mqtt_broker}:{self.mqtt_port}")
        except Exception as e:
            print(f"Failed to connect to MQTT broker: {e}")

    def on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        print(f"MQTT connected with result code {rc}")
        
    def on_mqtt_message(self, client, userdata, msg):
        """Callback when a message is received from MQTT"""
        try:
            print(f"Received message on topic {msg.topic}")
            # Process incoming MQTT messages if needed
        except Exception as e:
            print(f"Error processing MQTT message: {e}")

    def send_valve_command(self, sector_id, device_id, command):
        """Send a command to a valve via MQTT"""
        if not self.mqtt_client:
            print("MQTT client not initialized")
            return False
            
        topic = f"/actuator/valve/{sector_id}/{device_id}"
        payload = {
            "device_id": device_id,
            "sector_id": sector_id,
            "timestamp": time.time(),
            "command": command  # e.g., "open", "close"
        }
        
        try:
            result = self.mqtt_client.publish(topic, json.dumps(payload), qos=1)
            print(f"Published command to {topic}: {payload}")
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            print(f"Error publishing valve command: {e}")
            return False

    def get_devices_in_sector(self, sector_id):
        """Get a list of devices in a specific sector from the catalog"""
        try:
            response = requests.get(f"{self.catalog_url}/sector/{sector_id}/devices")
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to get devices for sector {sector_id}. Status code: {response.status_code}")
                return []
        except requests.RequestException as e:
            print(f"Error retrieving sector devices: {e}")
            return []

    def process_anomaly(self, anomaly_data):
        """Process an anomaly report from the Analytics service"""
        try:
            sector_id = anomaly_data.get("sector_id")
            device_id = anomaly_data.get("device_id")
            anomaly_type = anomaly_data.get("type")  # e.g., "temperature", "pressure", "cascade"
            severity = anomaly_data.get("severity", "medium")  # Default to medium if not specified
            
            print(f"Processing {severity} {anomaly_type} anomaly in sector {sector_id}, device {device_id}")
            
            if anomaly_type == "cascade":
                # For cascade problem, get all devices in the sector
                devices = self.get_devices_in_sector(sector_id)
                
                # Sort by device ID (assuming numeric ordering like dev010, dev020)
                sorted_devices = sorted(devices, key=lambda x: x.get("device_id"))
                
                # Find the index of the device with anomaly
                anomaly_index = next((i for i, d in enumerate(sorted_devices) if d.get("device_id") == device_id), -1)
                
                if anomaly_index > 0:
                    # Close valve of the device before the anomaly
                    prev_device = sorted_devices[anomaly_index - 1]
                    self.send_valve_command(sector_id, prev_device.get("device_id"), "close")
                    return True
            
            # For single device anomalies based on severity
            if severity == "high":
                # Close the valve of the affected device
                self.send_valve_command(sector_id, device_id, "close")
                return True
            elif severity == "medium":
                # Could implement more nuanced control strategies
                pass
            
            return False
            
        except Exception as e:
            print(f"Error processing anomaly: {e}")
            return False
            
    def health_check(self):
        """Health check endpoint to verify service is running"""
        return {
            "status": "ok",
            "service": self.service_name,
            "timestamp": time.time()
        }
    
    def update_thresholds(self, temp=None, pressure=None):
        """Update control thresholds"""
        if temp is not None:
            self.temp_threshold = float(temp)
        if pressure is not None:
            self.pressure_threshold = float(pressure)
        
        return {
            "status": "updated",
            "temperature_threshold": self.temp_threshold,
            "pressure_threshold": self.pressure_threshold
        }

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self):
        """Root endpoint with service information"""
        return {
            "service": self.service_name,
            "status": "running",
            "endpoints": {
                "/health": "Health check endpoint",
                "/anomaly": "Process anomaly reports (POST)",
                "/control": "Manually control valves (POST)",
                "/thresholds": "Get or update threshold values (GET/POST)"
            }
        }
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def health(self):
        """Health check endpoint"""
        return self.health_check()
    
    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def anomaly(self):
        """Endpoint to receive anomaly reports from Analytics"""
        if cherrypy.request.method == 'POST':
            anomaly_data = cherrypy.request.json
            success = self.process_anomaly(anomaly_data)
            return {"status": "processed" if success else "failed"}
        else:
            raise cherrypy.HTTPError(405, "Method not allowed")
    
    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def control(self):
        """Endpoint to manually control valves"""
        if cherrypy.request.method == 'POST':
            control_data = cherrypy.request.json
            sector_id = control_data.get("sector_id")
            device_id = control_data.get("device_id")
            command = control_data.get("command")
            
            if not all([sector_id, device_id, command]):
                raise cherrypy.HTTPError(400, "Missing required fields")
                
            success = self.send_valve_command(sector_id, device_id, command)
            return {"status": "sent" if success else "failed"}
        else:
            raise cherrypy.HTTPError(405, "Method not allowed")
    
    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def thresholds(self):
        """Endpoint to get or update threshold values"""
        if cherrypy.request.method == 'GET':
            return {
                "temperature": self.temp_threshold,
                "pressure": self.pressure_threshold
            }
        elif cherrypy.request.method == 'POST':
            data = cherrypy.request.json
            return self.update_thresholds(
                temp=data.get("temperature"),
                pressure=data.get("pressure")
            )
        else:
            raise cherrypy.HTTPError(405, "Method not allowed")


def periodic_tasks(control_center, interval=60):
    """Run periodic tasks like health check or re-registration"""
    while True:
        try:
            # Re-register with catalog to keep registration active
            control_center.register_with_catalog()
            # Check for updated service information
            control_center.get_service_info()
        except Exception as e:
            print(f"Error in periodic tasks: {e}")
        time.sleep(interval)


if __name__ == '__main__':
    # Create the Control Center instance
    control_center = MS_ControlCenter()
    
    # Start a background thread for periodic tasks
    task_thread = threading.Thread(
        target=periodic_tasks,
        args=(control_center,),
        daemon=True
    )
    task_thread.start()
    
    # Configure CherryPy server
    cherrypy.config.update({
        'server.socket_host': control_center.host,
        'server.socket_port': control_center.port,
    })
    
    # Start the web server
    cherrypy.quickstart(control_center)