"""
MS_ControlCenter for Smart IoT Bolt for Pipelines
"""
import sys
import os
import time
import json
import threading
import requests
import socket
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
        
        self.port = self.find_available_port(int(os.getenv('PORT', 8083)))
        
        # Initialize services and endpoints
        self.endpoints = {}
        self.mqtt_client = None
        self.mqtt_broker = None
        self.mqtt_port = None
        
        # Threshold values for control decisions
        self.temp_threshold = float(os.getenv('TEMP_THRESHOLD', '80.0'))  # Default 80°C
        self.pressure_threshold = float(os.getenv('PRESSURE_THRESHOLD', '10.0'))  # Default 10 bar
        
        # Record the start time
        self.start_time = time.time()
        
        # Register with catalog and get service information
        self.register_with_catalog()
        self.get_service_info()
        self.connect_mqtt()

    def find_available_port(self, preferred_port):
        max_port = preferred_port + 100
        current_port = preferred_port
        
        while current_port < max_port:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((self.host, current_port))
            sock.close()
            
            if result != 0:
                return current_port
            
            current_port += 1
        
        return preferred_port

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
            
            if not sector_id or not device_id:
                return {"status": "error", "message": "Missing sector_id or device_id"}
            
            # Get current device status from catalog
            try:
                response = requests.get(f"{self.catalog_url}/device/{device_id}")
                if response.status_code != 200:
                    return {"status": "error", "message": f"Failed to get device status: {response.status_code}"}
                
                device_info = response.json()
                current_status = device_info.get("status", {})
                
                # Get current temperature and pressure readings
                current_temp = current_status.get("temperature")
                current_pressure = current_status.get("pressure")
                current_valve_status = current_status.get("valve", "unknown")
                
                # Check if both temperature and pressure exceed thresholds
                temp_exceeded = current_temp is not None and current_temp > self.temp_threshold
                pressure_exceeded = current_pressure is not None and current_pressure > self.pressure_threshold
                
                # Log the anomaly
                print(f"Processing anomaly: {anomaly_type} in {sector_id}/{device_id}")
                print(f"Current readings: Temp={current_temp}, Pressure={current_pressure}, Valve={current_valve_status}")
                print(f"Thresholds: Temp={self.temp_threshold}, Pressure={self.pressure_threshold}")
                
                valve_action = None
                
                # Handle cascade problems with high severity
                if anomaly_type == "cascade" and severity == "high":
                    # For cascade problems, we always want to isolate the sector
                    valve_action = "close"
                    reason = "Cascade problem detected with high severity"
                
                # Both temperature and pressure exceeded - automatic valve control
                elif temp_exceeded and pressure_exceeded:
                    valve_action = "close"
                    reason = f"Both temperature ({current_temp}) and pressure ({current_pressure}) exceed thresholds"
                
                # Only temperature exceeded with high severity
                elif temp_exceeded and severity == "high":
                    valve_action = "close"
                    reason = f"Temperature ({current_temp}) exceeds threshold with high severity"
                
                # Only pressure exceeded with high severity
                elif pressure_exceeded and severity == "high":
                    valve_action = "close"
                    reason = f"Pressure ({current_pressure}) exceeds threshold with high severity"
                
                # Check if we need to control the valve
                if valve_action and current_valve_status != valve_action:
                    # Send command to valve
                    print(f"Sending {valve_action} command to valve {device_id} in sector {sector_id}")
                    self.send_valve_command(sector_id, device_id, valve_action)
                    
                    return {
                        "status": "success", 
                        "message": f"Valve {valve_action} command sent for {device_id}", 
                        "reason": reason
                    }
                elif valve_action and current_valve_status == valve_action:
                    return {
                        "status": "success", 
                        "message": f"Valve already in {valve_action} state", 
                        "reason": reason
                    }
                else:
                    return {
                        "status": "success", 
                        "message": "No valve action required at this time",
                        "temperature": current_temp,
                        "pressure": current_pressure,
                        "thresholds": {
                            "temperature": self.temp_threshold,
                            "pressure": self.pressure_threshold
                        }
                    }
            
            except requests.RequestException as e:
                return {"status": "error", "message": f"Failed to process anomaly: {str(e)}"}
                
        except Exception as e:
            return {"status": "error", "message": f"Error processing anomaly: {str(e)}"}

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
            result = self.process_anomaly(anomaly_data)
            return result
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

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def status(self):
        """Returns the current status of the control center"""
        return {
            "service": self.service_name,
            "uptime": time.time() - self.start_time if hasattr(self, 'start_time') else 0,
            "thresholds": {
                "temperature": self.temp_threshold,
                "pressure": self.pressure_threshold
            },
            "mqtt_connected": self.mqtt_client.is_connected() if self.mqtt_client else False,
            "sectors_monitored": len(self.get_all_sectors())
        }
    
    def get_all_sectors(self):
        """Get all sectors from the catalog"""
        try:
            response = requests.get(f"{self.catalog_url}/sector")
            if response.status_code == 200:
                return response.json().get("sectors", [])
            return []
        except Exception as e:
            print(f"Error getting sectors: {e}")
            return []


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