import os
import paho.mqtt.client as mqtt
from dotenv import load_dotenv

# Load environment variables from config.env
load_dotenv("config.env")

# Read configuration with safe defaults
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "guest")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "guest")

def on_connect(client, userdata, flags, rc):
    """
    Called when the client connects to the MQTT broker.
    rc == 0 means success.
    """
    if rc == 0:
        print(f"[MQTT] Connected to {MQTT_BROKER}:{MQTT_PORT}")
    else:
        print(f"[MQTT] Connection failed with code {rc}")

def create_mqtt_client():
    """
    Creates and returns an MQTT client configured with broker credentials.
    """
    client = mqtt.Client()
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    return client
