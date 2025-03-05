import time
import os
import json
from dotenv import load_dotenv
from mqtt_client import create_mqtt_client
import datetime

class SensorSimulator:
    """
    Simulates sensor behavior for temperature and pressure.
    """
    def __init__(self, initial_temp: float, initial_pressure: float):
        self.temperature = initial_temp
        self.pressure = initial_pressure

    def simulate(self):
        """Simulates gradual changes in temperature and pressure."""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        # Temperature oscillates between 25 and 35°C
        self.temperature += 0.2 if self.temperature < 35.0 else -0.2

        # Pressure oscillates between 250 and 280 Pa
        self.pressure += 1.5 if self.pressure < 280.0 else -1.5

        return round(self.temperature, 2), round(self.pressure, 2), timestamp

class DataManager:
    """
    Handles saving sensor data to a JSON file.
    """
    def __init__(self, file_path: str):
        self.file_path = file_path

    def save_to_json(self, data: dict):
        """Appends data to the JSON file."""
        print("[DATA MANAGER] Saving data to JSON file...")
        try:
            with open(self.file_path, 'r') as file:
                sensor_data = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            sensor_data = []

        sensor_data.append(data)

        with open(self.file_path, 'w') as file:
            json.dump(sensor_data, file, indent=4)

class SensorPublisher:
    """
    Publishes sensor data to MQTT topics and saves data to a JSON file.
    """
    def __init__(self, mqtt_client, simulator: SensorSimulator, data_manager: DataManager, 
                 temp_topic: str, pressure_topic: str, publish_interval: int):
        self.mqtt_client = mqtt_client
        self.simulator = simulator
        self.data_manager = data_manager
        self.temp_topic = temp_topic
        self.pressure_topic = pressure_topic
        self.publish_interval = publish_interval

    def publish(self):
        """Publishes simulated data at regular intervals."""
        self.mqtt_client.loop_start()



            # Publish to MQTT topics
            self.mqtt_client.publish(self.temp_topic, temp)
            self.mqtt_client.publish(self.pressure_topic, press)



def get_current_timestamp():
        """
        Returns the current timestamp in ISO 8601 format.
        """
        return datetime.datetime.now().isoformat()

def publish_sensor_data():
        """
        Publishes simulated sensor data to the MQTT topics at regular intervals.
        """
        mqtt_client = create_mqtt_client()
        mqtt_client.loop_start()  # Start background thread to handle networking

        while True:
            temp, press = simulate_sensor_behavior()
            timestamp = get_current_timestamp()

            # Publish to each topic
            mqtt_client.publish(TOPIC_TEMPERATURE, f"{timestamp} - {temp}")
            mqtt_client.publish(TOPIC_PRESSURE, f"{timestamp} - {press}")

            print(f"[PUBLISHER] Sent → Timestamp={timestamp}, Temp={temp}°C, Press={press}Pa")
            time.sleep(PUBLISH_INTERVAL)

if __name__ == "__main__":

