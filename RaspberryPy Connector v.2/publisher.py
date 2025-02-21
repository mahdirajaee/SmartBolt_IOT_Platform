import time
import os
from dotenv import load_dotenv
from mqtt_client import create_mqtt_client

# Load environment variables
load_dotenv("config.env")

# Topics from config
TOPIC_TEMPERATURE = os.getenv("MQTT_TOPIC_SENSOR_TEMPERATURE", "/default/temperature")
TOPIC_PRESSURE = os.getenv("MQTT_TOPIC_SENSOR_PRESSURE", "/default/pressure")

PUBLISH_INTERVAL = int(os.getenv("PUBLISH_INTERVAL", "5"))
temperature = float(os.getenv("INITIAL_TEMPERATURE", "25.0"))
pressure = float(os.getenv("INITIAL_PRESSURE", "250.0"))

def simulate_sensor_behavior():
    """
    Simulates gradual changes in temperature and pressure.
    """
    global temperature, pressure

    # Example logic: temperature oscillates between 25 and 35
    if temperature < 35.0:
        temperature += 0.2
    else:
        temperature -= 0.2

    # Example logic: pressure oscillates between 250 and 280
    if pressure < 280.0:
        pressure += 1.5
    else:
        pressure -= 1.5

    return round(temperature, 2), round(pressure, 2)

def publish_sensor_data():
    """
    Publishes simulated sensor data to the MQTT topics at regular intervals.
    """
    mqtt_client = create_mqtt_client()
    mqtt_client.loop_start()  # Start background thread to handle networking

    while True:
        temp, press = simulate_sensor_behavior()

        # Publish to each topic
        mqtt_client.publish(TOPIC_TEMPERATURE, temp)
        mqtt_client.publish(TOPIC_PRESSURE, press)

        print(f"[PUBLISHER] Sent → Temp={temp}°C, Press={press}Pa")
        time.sleep(PUBLISH_INTERVAL)

if __name__ == "__main__":
    publish_sensor_data()
