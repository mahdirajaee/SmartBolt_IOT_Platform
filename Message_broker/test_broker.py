#!/usr/bin/env python3
"""
Test script for the Smart IoT Bolt Message Broker.

This script simulates:
1. A Raspberry Pi Connector publishing temperature and pressure readings
2. A Control Center sending valve commands
3. A Time Series DB Connector subscribing to sensor readings
"""

import json
import random
import time
from typing import Dict, Any

import paho.mqtt.client as mqtt

# Configuration
CONFIG = {
    "broker": {
        "host": "localhost",
        "port": 1883
    },
    "topics": {
        "temperature": "/sensor/temperature",
        "pressure": "/sensor/pressure",
        "valve": "/actuator/valve"
    },
    "device_ids": [
        "dev010",  # Pipeline 1, position 0
        "dev020",  # Pipeline 1, position 1
        "dev030",  # Pipeline 1, position 2
        "dev110",  # Pipeline 2, position 0
        "dev120"   # Pipeline 2, position 1
    ]
}

# Callback functions
def on_connect(client, userdata, flags, rc):
    """Callback for when client connects to the broker."""
    if rc == 0:
        print(f"Connected to MQTT broker with result code {rc}")
        # Subscribe to topics based on client role
        if userdata.get("role") == "time_series_db":
            client.subscribe(CONFIG["topics"]["temperature"])
            client.subscribe(CONFIG["topics"]["pressure"])
            print("Time Series DB: Subscribed to sensor topics")
        elif userdata.get("role") == "control_center":
            client.subscribe(CONFIG["topics"]["temperature"])
            client.subscribe(CONFIG["topics"]["pressure"])
            print("Control Center: Subscribed to sensor topics")
        elif userdata.get("role") == "raspberry_pi":
            client.subscribe(CONFIG["topics"]["valve"])
            print("Raspberry Pi: Subscribed to valve topic")
    else:
        print(f"Failed to connect to MQTT broker with result code {rc}")

def on_message(client, userdata, msg):
    """Callback for when a message is received from the broker."""
    try:
        payload = json.loads(msg.payload.decode())
        print(f"{userdata.get('role', 'unknown')} received on {msg.topic}: {payload}")
        
        # Simulate Control Center logic
        if userdata.get("role") == "control_center" and msg.topic == CONFIG["topics"]["temperature"]:
            # If temperature is too high, send command to open valve
            if payload.get("value", 0) > 80:
                device_id = payload.get("device_id")
                if device_id:
                    send_valve_command(client, device_id, "open")
                    print(f"Control Center: Sending OPEN command to {device_id} due to high temperature")
    except json.JSONDecodeError:
        print(f"Received malformed JSON on {msg.topic}")
    except Exception as e:
        print(f"Error processing message: {str(e)}")

# Helper functions
def create_sensor_message(device_id: str, sensor_type: str, value: float) -> Dict[str, Any]:
    """Create a standardized sensor message."""
    return {
        "device_id": device_id,
        "sensor_type": sensor_type,
        "value": value,
        "timestamp": time.time(),
        "metadata": {
            "pipeline_id": device_id[3], 
            "position": int(device_id[4:])
        }
    }

def send_sensor_data(client, device_id: str):
    """Simulate sending sensor data from a Raspberry Pi."""
    # Simulate temperature (normal range 60-75°C)
    temperature = round(random.uniform(60, 75), 1)
    # Randomly simulate an abnormal reading occasionally
    if random.random() < 0.1:  # 10% chance of abnormal reading
        temperature += random.uniform(10, 20)  # Abnormal spike
    
    temp_message = create_sensor_message(device_id, "temperature", temperature)
    client.publish(
        CONFIG["topics"]["temperature"],
        json.dumps(temp_message)
    )
    
    # Simulate pressure (normal range 400-600 kPa)
    pressure = round(random.uniform(400, 600), 1)
    # Randomly simulate an abnormal reading occasionally
    if random.random() < 0.1:  # 10% chance of abnormal reading
        pressure += random.uniform(100, 200)  # Abnormal spike
    
    pressure_message = create_sensor_message(device_id, "pressure", pressure)
    client.publish(
        CONFIG["topics"]["pressure"],
        json.dumps(pressure_message)
    )
    
    print(f"Raspberry Pi {device_id}: Sent temperature {temperature}°C and pressure {pressure} kPa")

def send_valve_command(client, device_id: str, command: str):
    """Simulate sending a valve command from the Control Center."""
    message = {
        "device_id": device_id,
        "actuator_type": "valve",
        "command": command,
        "timestamp": time.time()
    }
    client.publish(
        CONFIG["topics"]["valve"],
        json.dumps(message)
    )

def main():
    """Test the message broker with simulated clients."""
    # Create Time Series DB client
    ts_db_client = mqtt.Client()
    ts_db_client.user_data_set({"role": "time_series_db"})
    ts_db_client.on_connect = on_connect
    ts_db_client.on_message = on_message
    
    # Create Control Center client
    control_client = mqtt.Client()
    control_client.user_data_set({"role": "control_center"})
    control_client.on_connect = on_connect
    control_client.on_message = on_message
    
    # Create Raspberry Pi clients (one per device)
    pi_clients = {}
    for device_id in CONFIG["device_ids"]:
        client = mqtt.Client()
        client.user_data_set({"role": "raspberry_pi", "device_id": device_id})
        client.on_connect = on_connect
        client.on_message = on_message
        pi_clients[device_id] = client
    
    try:
        # Connect all clients
        ts_db_client.connect(CONFIG["broker"]["host"], CONFIG["broker"]["port"])
        ts_db_client.loop_start()
        
        control_client.connect(CONFIG["broker"]["host"], CONFIG["broker"]["port"])
        control_client.loop_start()
        
        for device_id, client in pi_clients.items():
            client.connect(CONFIG["broker"]["host"], CONFIG["broker"]["port"])
            client.loop_start()
        
        print("All clients connected and started. Press Ctrl+C to stop.")
        
        # Simulation loop
        while True:
            # Each Raspberry Pi publishes sensor data
            for device_id, client in pi_clients.items():
                send_sensor_data(client, device_id)
            
            # Wait between iterations
            time.sleep(5)
    
    except KeyboardInterrupt:
        print("Test stopped by user")
    except Exception as e:
        print(f"Error during test: {str(e)}")
    finally:
        # Disconnect all clients
        ts_db_client.loop_stop()
        ts_db_client.disconnect()
        
        control_client.loop_stop()
        control_client.disconnect()
        
        for client in pi_clients.values():
            client.loop_stop()
            client.disconnect()
        
        print("All clients disconnected")

if __name__ == "__main__":
    main()