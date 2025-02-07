import time
import random
import json
from mqtt.MYMQTT import MyMQTT
from config import *

# Define the publish interval in seconds
PUBLISH_INTERVAL = 5

class SensorSimulator:
    def __init__(self, device_id, broker, port):
        self.device_id = device_id
        # Use MyMQTT for publishing sensor data
        self.mqtt_client = MyMQTT(clientID=device_id, broker=broker, port=port, notifier=self)

    def start(self):
        """Start the MQTT client."""
        self.mqtt_client.start()
        print(f"{self.device_id} started publishing sensor data.")

    def stop(self):
        """Stop the MQTT client."""
        self.mqtt_client.stop()
        print(f"{self.device_id} stopped publishing sensor data.")

    def notify(self, topic, message):
        """Handle any messages received (if subscribing)."""
        print(f"Received message on topic {topic}: {message}")

    def simulate_sensors(self):
        """Simulate temperature and pressure sensors."""
        while True:
            # Generate random sensor data
            temperature = round(random.uniform(20.0, 100.0), 2)
            pressure = round(random.uniform(10.0, 300.0), 2)

            # Create a payload for publishing
            payload = {
                "device_id": self.device_id,
                "temperature": temperature,
                "pressure": pressure,
                "timestamp": time.time()
            }
            # Define MQTT topics
            MQTT_TOPIC_TEMPERATURE = "sensor/temperature"
            MQTT_TOPIC_PRESSURE = "sensor/pressure"
            # Publish to respective topics
            self.mqtt_client.myPublish(MQTT_TOPIC_TEMPERATURE, payload)
            self.mqtt_client.myPublish(MQTT_TOPIC_PRESSURE, payload)

            print(f"Published: {json.dumps(payload)}")
            time.sleep(PUBLISH_INTERVAL)
