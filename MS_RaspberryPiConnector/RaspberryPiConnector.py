import os
import time
import json
import uuid
import random
import threading
import numpy as np
import socket
import sys
if sys.version_info >= (3, 13):
    import cgi_patch

import cherrypy
import requests
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

load_dotenv()

class RaspberryPiConnector:
    def __init__(self):
        self.device_id = os.getenv("DEVICE_ID")
        self.sector_id = os.getenv("SECTOR_ID")
        self.catalog_url = os.getenv("CATALOG_URL")
        
        self.connector_id = f"raspberry_pi_{self.sector_id}_{self.device_id}_{str(uuid.uuid4())[:8]}"
        self.port = self.get_port_from_env()
        self.base_url = f"http://{os.getenv('HOST')}:{self.port}"
        
        self.temperature_mean = float(os.getenv("TEMP_MEAN"))
        self.temperature_std = float(os.getenv("TEMP_STD"))
        self.pressure_mean = float(os.getenv("PRESSURE_MEAN"))
        self.pressure_std = float(os.getenv("PRESSURE_STD"))
        
        self.sensor_interval = int(os.getenv("SENSOR_INTERVAL"))
        self.catalog_update_interval = int(os.getenv("CATALOG_UPDATE_INTERVAL"))
        
        self.mqtt_broker = os.getenv("MQTT_BROKER")
        self.mqtt_port = int(os.getenv("MQTT_PORT"))
        self.mqtt_client = None
        
        self.valve_status = "closed"
        self.last_temperature = None
        self.last_pressure = None
        
        self.running = True
    
    def get_port_from_env(self):
        try:
            preferred_port = int(os.getenv("PORT"))
            return self.find_available_port(preferred_port)
        except (ValueError, TypeError):
            print(f"Invalid PORT in .env, using default port 8000")
            return self.find_available_port(8000)
        
    def start(self):
        try:
            self.retrieve_config_from_catalog()
        except Exception as e:
            print(f"Could not connect to catalog, using default MQTT settings: {e}")
        
        try:
            self.setup_mqtt()
        except Exception as e:
            print(f"Failed to set up MQTT client: {e}")
            print("Continuing without MQTT capabilities")
            
        try:
            self.register_with_catalog()
        except Exception as e:
            print(f"Failed to register with catalog: {e}")

        sensor_thread = threading.Thread(target=self.sensor_loop)
        catalog_thread = threading.Thread(target=self.catalog_update_loop)
        
        sensor_thread.daemon = True
        catalog_thread.daemon = True
        
        sensor_thread.start()
        catalog_thread.start()
        
        cherrypy.config.update({'server.socket_host': '0.0.0.0',
                               'server.socket_port': self.port})
        
        cherrypy.quickstart(self)
    
    def retrieve_config_from_catalog(self):
        try:
            response = requests.get(f"{self.catalog_url}/broker")
            if response.status_code == 200:
                broker_info = response.json()
                self.mqtt_broker = broker_info.get("address")
                self.mqtt_port = broker_info.get("port", 1883)
                print(f"Retrieved broker configuration: {self.mqtt_broker}:{self.mqtt_port}")
        except Exception as e:
            print(f"Error retrieving configuration: {e}")
    
    def setup_mqtt(self):
        try:
            major_version = int(mqtt.__version__.split('.')[0])
            
            if major_version >= 2:
                self.mqtt_client = mqtt.Client(
                    client_id=self.connector_id,
                    callback_api_version=mqtt.CallbackAPIVersion.VERSION2
                )
            else:
                self.mqtt_client = mqtt.Client(client_id=self.connector_id)
        except AttributeError:
            print("Could not determine MQTT version, using default client initialization")
            self.mqtt_client = mqtt.Client(client_id=self.connector_id)
        
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        
        try:
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.mqtt_client.loop_start()
            print(f"Connected to MQTT broker at {self.mqtt_broker}:{self.mqtt_port}")
        except Exception as e:
            print(f"Failed to connect to MQTT broker: {e}")
            raise
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        print(f"Connected to MQTT broker with result code {rc}")
        valve_topic = f"/actuator/valve/{self.sector_id}/{self.device_id}"
        client.subscribe(valve_topic)
        print(f"Subscribed to topic: {valve_topic}")
    
    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            topic = msg.topic
            
            print(f"Received message on topic {topic}: {payload}")
            
            if topic.startswith("/actuator/valve"):
                self.handle_valve_command(payload)
        except Exception as e:
            print(f"Error processing message: {e}")
    
    def handle_valve_command(self, payload):
        if "command" in payload:
            command = payload["command"]
            if command in ["open", "close"]:
                self.valve_status = "open" if command == "open" else "closed"
                print(f"Valve {self.device_id} is now {self.valve_status}")
                self.update_catalog_status()
            else:
                print(f"Unknown valve command: {command}")
    
    def read_temperature(self):
        temperature = random.gauss(self.temperature_mean, self.temperature_std)
        return round(temperature, 2)
    
    def read_pressure(self):
        pressure = random.gauss(self.pressure_mean, self.pressure_std)
        return round(pressure, 2)
    
    def publish_sensor_data(self):
        try:
            temperature = self.read_temperature()
            pressure = self.read_pressure()
            
            self.last_temperature = temperature
            self.last_pressure = pressure
            
            timestamp = int(time.time())
            
            temp_payload = {
                "device_id": self.device_id,
                "sector_id": self.sector_id,
                "timestamp": timestamp,
                "value": temperature,
                "unit": "celsius"
            }
            
            pressure_payload = {
                "device_id": self.device_id,
                "sector_id": self.sector_id,
                "timestamp": timestamp,
                "value": pressure,
                "unit": "kPa"
            }
            
            temp_topic = f"/sensor/temperature/{self.sector_id}/{self.device_id}"
            pressure_topic = f"/sensor/pressure/{self.sector_id}/{self.device_id}"
            
            if self.mqtt_client:
                self.mqtt_client.publish(temp_topic, json.dumps(temp_payload))
                self.mqtt_client.publish(pressure_topic, json.dumps(pressure_payload))
                print(f"Published: Temperature: {temperature}°C, Pressure: {pressure} kPa")
            else:
                print(f"MQTT client not available. Sensor readings: Temperature: {temperature}°C, Pressure: {pressure} kPa")
            
        except Exception as e:
            print(f"Error publishing sensor data: {e}")
    
    def sensor_loop(self):
        while self.running:
            try:
                self.publish_sensor_data()
            except Exception as e:
                print(f"Error in sensor loop: {e}")
            time.sleep(self.sensor_interval)
    
    def register_with_catalog(self):
        registration_data = {
            "id": self.connector_id,
            "device_id": self.device_id,
            "sector_id": self.sector_id,
            "type": "raspberry_pi_connector",
            "endpoints": {
                "rest": self.base_url
            },
            "status": {
                "online": True,
                "temperature": self.last_temperature,
                "pressure": self.last_pressure,
                "valve": self.valve_status
            }
        }
        
        try:
            response = requests.post(
                f"{self.catalog_url}/device",
                json=registration_data
            )
            
            if response.status_code in [200, 201]:
                print(f"Successfully registered with Resource Catalog: {response.text}")
            else:
                print(f"Failed to register with Resource Catalog: {response.status_code} - {response.text}")
        
        except Exception as e:
            print(f"Error registering with Resource Catalog: {e}")
            raise
            
    def update_catalog_status(self):
        status_data = {
            "online": True,
            "temperature": self.last_temperature,
            "pressure": self.last_pressure,
            "valve": self.valve_status
        }
        
        try:
            response = requests.put(
                f"{self.catalog_url}/device/{self.device_id}",
                json={"status": status_data}
            )
            
            if response.status_code == 200:
                print("Successfully updated status in Resource Catalog")
            else:
                print(f"Failed to update status: {response.status_code} - {response.text}")
        
        except Exception as e:
            print(f"Error updating status in Resource Catalog: {e}")
    
    def catalog_update_loop(self):
        while self.running:
            try:
                self.update_catalog_status()
            except Exception as e:
                print(f"Error in catalog update loop: {e}")
            time.sleep(self.catalog_update_interval)
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def status(self):
        return {
            "device_id": self.device_id,
            "sector_id": self.sector_id,
            "temperature": self.last_temperature,
            "pressure": self.last_pressure,
            "valve_status": self.valve_status,
            "uptime": time.time()
        }
    
    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def valve(self):
        if cherrypy.request.method == 'PUT':
            data = cherrypy.request.json
            if "command" in data and data["command"] in ["open", "close"]:
                self.valve_status = "open" if data["command"] == "open" else "closed"
                self.update_catalog_status()
                
                if self.mqtt_client:
                    valve_topic = f"/actuator/valve/{self.sector_id}/{self.device_id}"
                    self.mqtt_client.publish(valve_topic, json.dumps({"command": data["command"]}))
                
                return {"status": "success", "valve": self.valve_status}
            return {"status": "error", "message": "Invalid command"}
        
        return {"status": "error", "message": "Method not allowed"}

    def find_available_port(self, preferred_port, max_attempts=10):
        port = preferred_port
        for attempt in range(max_attempts):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    s.bind(('0.0.0.0', port))
                    print(f"Found available port: {port}")
                    return port
            except OSError:
                print(f"Port {port} is already in use, trying {port + 1}")
                port += 1

        raise RuntimeError(f"Could not find an available port after {max_attempts} attempts starting from {preferred_port}")
    
    def is_port_in_use(self, port, host='0.0.0.0'):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex((host, port)) == 0

if __name__ == "__main__":
    connector = RaspberryPiConnector()
    connector.start()