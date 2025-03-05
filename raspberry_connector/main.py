import paho.mqtt.client as mqtt
import time
import json
import threading
import datetime
import os
import sys
import requests
import numpy as np
import random

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Import sensor modules
from temperature.temperature_sensor import get_temperature
from pressure.pressure_sensor import get_pressure
from actuator_valve.actuator import Actuator

# Configuration
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config_sen.json")

try:
    with open(CONFIG_PATH, "r") as config_file:
        config = json.load(config_file)
except FileNotFoundError:
    print(f"Error: {CONFIG_PATH} not found. Creating default configuration.")
    

# MQTT Broker Configuration
BROKER_ADDRESS = config["broker_address"]
BROKER_PORT = config["broker_port"]

# Topics
TEMPERATURE_TOPIC = f"{config['temperature_topic']}/{config['pipeline_id']}/{config['device_id']}"
PRESSURE_TOPIC = f"{config['pressure_topic']}/{config['pipeline_id']}/{config['device_id']}"
ACTUATOR_COMMAND_TOPIC = f"{config['actuator_command_topic']}/{config['pipeline_id']}/{config['device_id']}"
ACTUATOR_STATUS_TOPIC = f"{config['actuator_command_topic']}/status/{config['pipeline_id']}/{config['device_id']}"

# Initialize actuator
actuator = Actuator(config['pipeline_id'], config['device_id'])

# Service information for catalog registration
service_info = {
    "service_id": f"raspberry_pi_{config['pipeline_id']}_{config['device_id']}",
    "service_type": "smart_bolt",
    "pipeline_id": config['pipeline_id'],
    "device_id": config['device_id'],
    "location": config.get("device_location", {"latitude": 0, "longitude": 0}),
    "endpoints": {
        "mqtt": {
            "broker": BROKER_ADDRESS,
            "port": BROKER_PORT,
            "subscribe": [ACTUATOR_COMMAND_TOPIC],
            "publish": [TEMPERATURE_TOPIC, PRESSURE_TOPIC, ACTUATOR_STATUS_TOPIC]
        }
    },
    "last_update": datetime.datetime.now().isoformat()
}

# Function to register with catalog
def register_with_catalog():
    try:
        response = requests.post(
            config["catalog_url"],
            headers={"Content-Type": "application/json"},
            json=service_info
        )
        if response.status_code == 200:
            print(f"Successfully registered with catalog: {response.json()}")
        else:
            print(f"Failed to register with catalog: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"Error registering with catalog: {e}")

# Function to update status with catalog
def update_status_with_catalog():
    update_url = f"{config['catalog_url']}/{service_info['service_id']}"
    try:
        service_info["last_update"] = datetime.datetime.now().isoformat()
        response = requests.put(
            update_url,
            headers={"Content-Type": "application/json"},
            json=service_info
        )
        if response.status_code == 200:
            print("Updated status with catalog")
        else:
            print(f"Failed to update status: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"Error updating status: {e}")

# MQTT Client Setup
def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker with result code {rc}")
    client.subscribe(ACTUATOR_COMMAND_TOPIC)

def on_message(client, userdata, msg):
    if msg.topic == ACTUATOR_COMMAND_TOPIC:
        command = msg.payload.decode()
        actuator.set_actuator(command)
        # Publish updated status
        client.publish(ACTUATOR_STATUS_TOPIC, actuator.get_status())

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

try:
    client.connect(BROKER_ADDRESS, BROKER_PORT, 60)
    client.loop_start()
    print(f"Connected to MQTT broker at {BROKER_ADDRESS}:{BROKER_PORT}")
except Exception as e:
    print(f"Failed to connect to MQTT broker: {e}")
    sys.exit(1)

# Register with catalog at startup
register_with_catalog()

# Start a thread to periodically update status with catalog
def status_update_thread():
    while True:
        update_status_with_catalog()
        time.sleep(60)  # Update every minute

status_thread = threading.Thread(target=status_update_thread)
status_thread.daemon = True
status_thread.start()

# Main Loop
try:
    while True:
        
        # Get sensor readings
        temperature = get_temperature(config['pipeline_id'], config['device_id'])
        pressure = get_pressure(config['pipeline_id'], config['device_id'])
        actuator_status = actuator.get_status()
        
        # Prepare data payloads
        temp_data = {
            "pipeline_id": config['pipeline_id'],
            "device_id": config['device_id'],
            "value": temperature,
            "unit": "celsius"
        }
        
        pressure_data = {
            "pipeline_id": config['pipeline_id'],
            "device_id": config['device_id'],
            "value": pressure,
            "unit": "bar"
        }
        
        status_data = {
            "pipeline_id": config['pipeline_id'],
            "device_id": config['device_id'],
            "status": actuator_status
        }
        
        # Publish to respective topics
        client.publish(TEMPERATURE_TOPIC, json.dumps(temp_data))
        client.publish(PRESSURE_TOPIC, json.dumps(pressure_data))
        client.publish(ACTUATOR_STATUS_TOPIC, json.dumps(status_data))
        
        print(f"Published: Temperature={temperature}°C, Pressure={pressure} bar, Valve={actuator_status}")
        
        # Wait for next update
        time.sleep(config.get("update_interval", 2))
        
except KeyboardInterrupt:
    print("Exiting...")
    client.loop_stop()
    client.disconnect()
    sys.exit(0)