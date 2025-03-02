import paho.mqtt.client as mqtt
import time
import importlib
import json
import threading
import datetime
import os
import sys

# Add the parent directory to the Python path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Load Configuration from config.json
config_path = os.path.join(os.path.dirname(__file__), "config_sen.json")
try:
    with open(config_path, "r") as config_file:
        config = json.load(config_file)
except FileNotFoundError:
    print(f"Error: {config_path} not found.")
    exit(1)

# MQTT Broker Configuration
BROKER_ADDRESS = config["broker_address"]
BROKER_PORT = config["broker_port"]

# Topics
TEMPERATURE_TOPIC = config["temperature_topic"]
PRESSURE_TOPIC = config["pressure_topic"]
ACTUATOR_COMMAND_TOPIC = config["actuator_command_topic"]
INFLUXDB_TOPIC = config["influxdb_topic"]

# MQTT Client Setup
def on_connect(client, userdata, flags, rc):
    print("Connected with result code " + str(rc))
    client.subscribe(ACTUATOR_COMMAND_TOPIC)

def on_message(client, userdata, msg):
    if msg.topic == ACTUATOR_COMMAND_TOPIC:
        command = msg.payload.decode()
        actuator_module.set_actuator(command)

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message

client.connect(BROKER_ADDRESS, BROKER_PORT, 60)
client.loop_start()

# Import Sensor and Actuator Modules
temperature_module = importlib.import_module("raspberry_connector.temperature.temperature_sensor")
pressure_module = importlib.import_module("raspberry_connector.pressure.pressure_sensor")
actuator_module = importlib.import_module("raspberry_connector.actuator_valve.actuator")

# Function to get user input and send commands
def send_user_commands():
    while True:
        command = input("Enter actuator command (or 'exit'): ")
        if command.lower() == 'exit':
            break
        client.publish(ACTUATOR_COMMAND_TOPIC, command)

# Start command input thread
command_thread = threading.Thread(target=send_user_commands)
command_thread.daemon = True
command_thread.start()

# Main Loop
try:
    while True:
        temperature = temperature_module.get_temperature()
        pressure = pressure_module.get_pressure()
        #get time like this
        #time = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

        client.publish(TEMPERATURE_TOPIC, str(temperature))
        client.publish(PRESSURE_TOPIC, str(pressure))

        data = {
            "temperature": temperature,
            "pressure": pressure,

        }
        client.publish(INFLUXDB_TOPIC, json.dumps(data))

        print(f"Published: Temperature={temperature}, Pressure={pressure}")

        time.sleep(2)

except KeyboardInterrupt:
    print("Exiting...")
    client.loop_stop()
    client.disconnect()