import time
import random
import sys
import os

# Ensure the 'MQTT' module is accessible
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from MQTT.MYMQTT import MYMQTT  # Corrected import

class SensorSimulator:
    def __init__(self, device_id, broker, port, topic):
        self.device_id = device_id
        self.client = MYMQTT("SensorSimulator")
        self.client.start(broker, port)
        self.topic = topic  # This must be initialized

    def stop(self):
        print(f"{self.device_id} stopped publishing sensor data.")
        self.client.stop()

    def notify(self, topic, message):
        """Handle messages received if subscribing."""
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

            # Publish data to MQTT broker
            self.client.myPublish(self.topic, payload)
            time.sleep(2)  # Simulate data sending every 2 seconds
