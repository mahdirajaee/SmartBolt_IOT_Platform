#!/usr/bin/env python3
"""
Test subscriber for Smart Bolt Message Broker
This script subscribes to key topics and prints received messages to verify proper pub/sub functionality
"""

import json
import time
from datetime import datetime
from client import MQTTClient
import config

# Topics to monitor
TOPICS = [
    config.SENSOR_DATA_TOPIC,      # For temperature and pressure data
    config.VALVE_STATUS_TOPIC,     # For valve status updates
    config.SYSTEM_EVENTS_TOPIC     # For system events
]

def message_callback(topic, payload, qos):
    """Callback for received messages"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"\n[{timestamp}] Message on topic: {topic}")
    
    try:
        # Try to parse as JSON
        data = json.loads(payload)
        
        if topic == config.SENSOR_DATA_TOPIC:
            # Process sensor data
            device_id = data.get("device_id", "unknown")
            readings = data.get("readings", {})
            
            if "temperature" in readings:
                temp = readings["temperature"].get("value")
                temp_unit = readings["temperature"].get("unit", "celsius")
                print(f"  Temperature: {temp} {temp_unit}")
            
            if "pressure" in readings:
                pressure = readings["pressure"].get("value")
                pressure_unit = readings["pressure"].get("unit", "hPa")
                print(f"  Pressure: {pressure} {pressure_unit}")
                
            # Check for valve info
            sector_info = data.get("sector_info", {})
            if "valve_state" in sector_info:
                print(f"  Valve State: {sector_info['valve_state']}")
                
        elif topic == config.VALVE_STATUS_TOPIC:
            # Process valve status
            sector_id = data.get("sector_id", "unknown")
            state = data.get("state", "unknown")
            print(f"  Valve in sector {sector_id}: {state}")
            
        elif topic == config.SYSTEM_EVENTS_TOPIC:
            # Process system events
            event = data.get("event", "unknown")
            print(f"  System Event: {event}")
            
        else:
            # Generic JSON message
            print(f"  Data: {json.dumps(data, indent=2)}")
            
    except json.JSONDecodeError:
        # Not JSON, print as string
        print(f"  Data: {payload.decode('utf-8')}")

def main():
    """Main function to start the test subscriber"""
    print("\n=== Smart Bolt Message Broker Test Subscriber ===")
    print(f"Will subscribe to the following topics:")
    for topic in TOPICS:
        print(f" - {topic}")
    print("\nPress Ctrl+C to exit\n")
    
    # Create MQTT client
    client = MQTTClient(client_id="smart_bolt_test_subscriber")
    
    try:
        # Connect to broker
        print(f"Connecting to broker at {config.MQTT_HOST}:{config.MQTT_PORT}...")
        if client.connect():
            print("Connected to broker successfully!")
            client.start()
            
            # Wait a moment to ensure the client is fully connected
            time.sleep(2)
            
            # Subscribe to topics only after confirming we're connected
            if client.connected:
                for topic in TOPICS:
                    success = client.subscribe(topic, qos=1, callback=message_callback)
                    print(f"Subscribed to {topic}: {'Success' if success else 'Failed'}")
                    
                print("Subscribed to all topics. Waiting for messages...")
            else:
                print("Failed to connect to broker! Client reports not connected.")
                return
                
            # Keep the script running
            while True:
                time.sleep(1)
                
        else:
            print("Failed to connect to broker!")
            
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        client.stop()
        
if __name__ == "__main__":
    main()