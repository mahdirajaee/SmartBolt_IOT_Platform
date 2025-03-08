import paho.mqtt.client as mqtt
import time
import json
import threading
import datetime
import os
import sys
import requests
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("raspberry_pi.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("RaspberryPiConnector")

# Import sensor modules
from temperature_sensor import TemperatureSensor
from pressure_sensor import PressureSensor
from actuator import Actuator

class RaspberryPiConnector:
    def __init__(self, config=None):
        # Load configuration
        self.config = config if config else self.load_config()
        
        # Initialize sensors and actuator
        self.temperature_sensor = TemperatureSensor()
        self.pressure_sensor = PressureSensor()
        self.actuator = Actuator(self.config['pipeline_id'], self.config['device_id'])
        
        # MQTT client setup
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.on_disconnect = self.on_disconnect
        
        # Topics
        self.temperature_topic = f"{self.config['temperature_topic']}/{self.config['pipeline_id']}/{self.config['device_id']}"
        self.pressure_topic = f"{self.config['pressure_topic']}/{self.config['pipeline_id']}/{self.config['device_id']}"
        self.actuator_command_topic = f"{self.config['actuator_command_topic']}/{self.config['pipeline_id']}/{self.config['device_id']}"
        self.actuator_status_topic = f"{self.config['actuator_status_topic']}/{self.config['pipeline_id']}/{self.config['device_id']}"
        
        # Service information
        self.service_info = {
            "id": f"raspberry_pi_{self.config['pipeline_id']}_{self.config['device_id']}",
            "name": "Raspberry Pi Connector",
            "type": "smart_bolt",
            "pipeline_id": self.config['pipeline_id'],
            "device_id": self.config['device_id'],
            "location": self.config.get("location", {"latitude": 0, "longitude": 0}),
            "sensors": ["temperature", "pressure"],
            "actuators": ["valve"],
            "endpoints": {
                "mqtt": {
                    "broker": self.config["broker_address"],
                    "port": self.config["broker_port"],
                    "subscribe": [self.actuator_command_topic],
                    "publish": [self.temperature_topic, self.pressure_topic, self.actuator_status_topic]
                }
            },
            "last_update": int(time.time())
        }
        
        # Connect to broker and register with catalog
        self.connected = False
        logger.info("Raspberry Pi Connector initialized")
    
    def load_config(self):
        """Load configuration from file or environment variables"""
        try:
            # Try to load from file
            config_path = os.environ.get("CONFIG_PATH", "config_sen.json")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config = json.load(f)
                    logger.info(f"Loaded configuration from {config_path}")
            else:
                # Use environment variables
                config = {
                    "broker_address": os.environ.get("MQTT_BROKER", "localhost"),
                    "broker_port": int(os.environ.get("MQTT_PORT", 1883)),
                    "pipeline_id": os.environ.get("PIPELINE_ID", "pipeline001"),
                    "device_id": os.environ.get("DEVICE_ID", "dev010"),
                    "catalog_url": os.environ.get("CATALOG_URL", "http://localhost:8080"),
                    "temperature_topic": os.environ.get("TEMPERATURE_TOPIC", "sensor/temperature"),
                    "pressure_topic": os.environ.get("PRESSURE_TOPIC", "sensor/pressure"),
                    "actuator_command_topic": os.environ.get("ACTUATOR_COMMAND_TOPIC", "actuator/valve"),
                    "actuator_status_topic": os.environ.get("ACTUATOR_STATUS_TOPIC", "actuator/valve/status"),
                    "update_interval": int(os.environ.get("UPDATE_INTERVAL", 2))
                }
                logger.info("Using configuration from environment variables")
            
            return config
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            # Return default configuration
            return {
                "broker_address": "localhost",
                "broker_port": 1883,
                "pipeline_id": "pipeline001",
                "device_id": "dev010",
                "catalog_url": "http://localhost:8080",
                "temperature_topic": "sensor/temperature",
                "pressure_topic": "sensor/pressure",
                "actuator_command_topic": "actuator/valve",
                "actuator_status_topic": "actuator/valve/status",
                "update_interval": 2
            }
    
    def connect_mqtt(self):
        """Connect to MQTT broker"""
        try:
            # Try to get broker info from catalog first
            broker_info = self.get_broker_info_from_catalog()
            if broker_info:
                broker_address = broker_info.get("address", self.config["broker_address"])
                broker_port = broker_info.get("port", self.config["broker_port"])
            else:
                broker_address = self.config["broker_address"]
                broker_port = self.config["broker_port"]
            
            self.mqtt_client.connect(broker_address, broker_port, 60)
            self.mqtt_client.loop_start()
            logger.info(f"Connected to MQTT broker at {broker_address}:{broker_port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False
    
    def get_broker_info_from_catalog(self):
        """Get broker information from the catalog"""
        try:
            response = requests.get(f"{self.config['catalog_url']}/broker")
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Error getting broker info from catalog: {e}")
            return None
    
    def on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            logger.info("Connected to MQTT broker")
            self.connected = True
            # Subscribe to command topic
            client.subscribe(self.actuator_command_topic)
            logger.info(f"Subscribed to topic: {self.actuator_command_topic}")
        else:
            logger.error(f"Failed to connect to MQTT broker with code {rc}")
            self.connected = False
    
    def on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        logger.warning(f"Disconnected from MQTT broker with code {rc}")
        self.connected = False
        # Try to reconnect
        if rc != 0:
            threading.Timer(5.0, self.connect_mqtt).start()
    
    def on_message(self, client, userdata, msg):
        """Callback when a message is received from MQTT broker"""
        try:
            logger.info(f"Received message on topic {msg.topic}")
            
            if msg.topic == self.actuator_command_topic:
                command = msg.payload.decode()
                logger.info(f"Received command: {command}")
                self.actuator.set_actuator(command)
                
                # Publish updated status
                self.publish_actuator_status()
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def register_with_catalog(self):
        """Register this device with the Resource/Service Catalog"""
        try:
            response = requests.post(
                f"{self.config['catalog_url']}/devices",
                json=self.service_info
            )
            if response.status_code in (200, 201):
                logger.info("Successfully registered with catalog")
                return True
            else:
                logger.error(f"Failed to register with catalog: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error registering with catalog: {e}")
            return False
    
    def update_status_with_catalog(self):
        """Update the device status in the catalog"""
        self.service_info["last_update"] = int(time.time())
        self.service_info["status"] = "online" if self.connected else "offline"
        
        try:
            response = requests.put(
                f"{self.config['catalog_url']}/devices/{self.service_info['id']}",
                json=self.service_info
            )
            if response.status_code == 200:
                logger.info("Successfully updated status with catalog")
                return True
            else:
                logger.error(f"Failed to update status with catalog: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error updating status with catalog: {e}")
            return False
    
    def start_update_thread(self):
        """Start a thread to periodically update the catalog"""
        def update_loop():
            while True:
                self.update_status_with_catalog()
                time.sleep(60)  # Update every minute
                
        thread = threading.Thread(target=update_loop)
        thread.daemon = True
        thread.start()
        logger.info("Started catalog update thread")
    
    def publish_sensor_data(self):
        """Publish sensor data to MQTT broker"""
        # Get sensor readings
        temperature = self.temperature_sensor.get_temperature(
            self.config['pipeline_id'], 
            self.config['device_id']
        )
        pressure = self.pressure_sensor.get_pressure(
            self.config['pipeline_id'], 
            self.config['device_id']
        )
        
        # Prepare data payloads
        temp_data = {
            "pipeline_id": self.config['pipeline_id'],
            "device_id": self.config['device_id'],
            "value": temperature,
            "unit": "celsius",
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        pressure_data = {
            "pipeline_id": self.config['pipeline_id'],
            "device_id": self.config['device_id'],
            "value": pressure,
            "unit": "bar",
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        # Publish to respective topics
        self.mqtt_client.publish(self.temperature_topic, json.dumps(temp_data))
        self.mqtt_client.publish(self.pressure_topic, json.dumps(pressure_data))
        
        logger.info(f"Published: Temperature={temperature}°C, Pressure={pressure} bar")
    
    def publish_actuator_status(self):
        """Publish actuator status to MQTT broker"""
        status_data = {
            "pipeline_id": self.config['pipeline_id'],
            "device_id": self.config['device_id'],
            "status": self.actuator.get_status(),
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        self.mqtt_client.publish(self.actuator_status_topic, json.dumps(status_data))
        logger.info(f"Published actuator status: {self.actuator.get_status()}")
    
    def start(self):
        """Start the Raspberry Pi connector"""
        # Connect to MQTT broker
        if not self.connect_mqtt():
            logger.error("Failed to connect to MQTT broker, exiting")
            return False
        
        # Register with catalog
        self.register_with_catalog()
        
        # Start catalog update thread
        self.start_update_thread()
        
        # Start main loop
        try:
            while True:
                if self.connected:
                    # Publish sensor data
                    self.publish_sensor_data()
                    # Publish actuator status
                    self.publish_actuator_status()
                
                # Wait for next update
                time.sleep(self.config.get("update_interval", 2))
        except KeyboardInterrupt:
            logger.info("Shutting down...")
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        
        return True

# Main entry point
if __name__ == "__main__":
    # Create and start the Raspberry Pi connector
    connector = RaspberryPiConnector()
    connector.start()