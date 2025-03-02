import paho.mqtt.client as mqtt
import os
import json
import time
import requests
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MessageBroker")

# Load environment variables
load_dotenv()

class MessageBroker:
    def __init__(self):
        # Get configuration from environment variables or use defaults
        self.mqtt_host = os.getenv("MQTT_HOST", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", 1883))
        self.mqtt_keepalive = int(os.getenv("MQTT_KEEPALIVE", 60))
        self.catalog_url = os.getenv("CATALOG_URL", "http://localhost:8080")
        
        # Topic structure
        self.sensor_temperature_topic = "/sensor/temperature"
        self.sensor_pressure_topic = "/sensor/pressure"
        self.actuator_valve_topic = "/actuator/valve"
        
        # Setup MQTT client
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        
        # Connection status
        self.connected = False
        
        # Service details for catalog registration
        self.service_id = "message_broker"
        self.service_name = "MQTT Message Broker"
        self.endpoints = {
            "mqtt": f"mqtt://{self.mqtt_host}:{self.mqtt_port}"
        }
        self.topics = {
            "temperature": self.sensor_temperature_topic,
            "pressure": self.sensor_pressure_topic,
            "valve": self.actuator_valve_topic
        }
        
    def on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            logger.info(f"Connected to MQTT Broker at {self.mqtt_host}:{self.mqtt_port}")
            self.connected = True
            
            # Subscribe to all relevant topics
            client.subscribe(self.sensor_temperature_topic + "/#")
            client.subscribe(self.sensor_pressure_topic + "/#")
            client.subscribe(self.actuator_valve_topic + "/#")
            logger.info("Subscribed to sensor and actuator topics")
        else:
            logger.error(f"Failed to connect to MQTT broker with code {rc}")
            self.connected = False
    
    def on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        logger.warning(f"Disconnected from MQTT broker with code {rc}")
        self.connected = False
    
    def on_message(self, client, userdata, msg):
        """Callback when a message is received"""
        try:
            logger.info(f"Message received on topic {msg.topic}: {msg.payload.decode()}")
            
            # Message forwarding logic can be implemented here if needed
            # This is a basic broker, so messages are automatically forwarded
            # by the MQTT broker itself based on topic subscriptions
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def register_with_catalog(self):
        """Register the message broker service with the catalog"""
        try:
            service_data = {
                "id": self.service_id,
                "name": self.service_name,
                "endpoints": self.endpoints,
                "topics": self.topics,
                "status": "active",
                "last_updated": time.time()
            }
            
            response = requests.post(
                f"{self.catalog_url}/services",
                json=service_data
            )
            
            if response.status_code == 200 or response.status_code == 201:
                logger.info("Successfully registered with the catalog")
                return True
            else:
                logger.error(f"Failed to register with catalog: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error registering with catalog: {e}")
            return False
    
    def update_status_with_catalog(self):
        """Update the service status with the catalog"""
        try:
            status_data = {
                "status": "active" if self.connected else "disconnected",
                "last_updated": time.time()
            }
            
            response = requests.put(
                f"{self.catalog_url}/services/{self.service_id}",
                json=status_data
            )
            
            if response.status_code == 200:
                logger.info("Successfully updated status with the catalog")
                return True
            else:
                logger.error(f"Failed to update status with catalog: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error updating status with catalog: {e}")
            return False
        
    def start(self):
        """Start the message broker"""
        try:
            # Connect to MQTT broker
            logger.info(f"Connecting to MQTT broker at {self.mqtt_host}:{self.mqtt_port}")
            self.client.connect(self.mqtt_host, self.mqtt_port, self.mqtt_keepalive)
            
            # Register with catalog
            self.register_with_catalog()
            
            # Start the MQTT client loop
            self.client.loop_start()
            
            # Start the heartbeat loop for catalog updates
            while True:
                if self.connected:
                    self.update_status_with_catalog()
                time.sleep(60)  # Update status every minute
                
        except KeyboardInterrupt:
            logger.info("Shutting down message broker...")
            self.client.loop_stop()
            self.client.disconnect()
        except Exception as e:
            logger.error(f"Error in message broker: {e}")
            self.client.loop_stop()
            self.client.disconnect()

# Entry point
if __name__ == "__main__":
    broker = MessageBroker()
    broker.start()