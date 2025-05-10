#!/usr/bin/env python3

import os
import sys
import signal
import logging
import json
import time
import threading
import random
import string
from datetime import datetime
import paho.mqtt.client as mqtt
import config

logging.basicConfig(
    filename=config.LOG_FILE,
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('message_broker')

console = logging.StreamHandler()
console.setLevel(getattr(logging, config.LOG_LEVEL))
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)

class MessageBroker:
    
    def __init__(self):
        # Use a unique client ID to avoid conflicts
        unique_id = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"{config.MQTT_CLIENT_ID}_{unique_id}", clean_session=True)
        self.running = False
        
        # Set up callbacks
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        
        # Set a will message to notify when client disconnects unexpectedly
        self.client.will_set(
            config.SYSTEM_EVENTS_TOPIC + "/disconnect", 
            payload=json.dumps({"client_id": config.MQTT_CLIENT_ID, "event": "unexpected_disconnect"}),
            qos=1, 
            retain=False
        )
        
        if config.MQTT_USERNAME and config.MQTT_PASSWORD:
            self.client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)
        
        self.handlers = {
            config.VALVE_CONTROL_TOPIC: self.handle_valve_control,
            config.VALVE_STATUS_TOPIC: self.handle_valve_status,
            config.SENSOR_DATA_TOPIC: self.handle_sensor_data,
            config.SYSTEM_EVENTS_TOPIC: self.handle_system_event
        }
        
        if config.TLS_ENABLED:
            if os.path.exists(config.TLS_CERT_FILE) and os.path.exists(config.TLS_KEY_FILE):
                self.client.tls_set(
                    certfile=config.TLS_CERT_FILE,
                    keyfile=config.TLS_KEY_FILE
                )
            else:
                logger.warning("TLS enabled but certificate/key files not found. Running without TLS.")
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info("Connected to MQTT broker")
            self.client.subscribe("#")
        else:
            logger.error(f"Failed to connect to MQTT broker with code: {rc}")
    
    def on_disconnect(self, client, userdata, rc, *args, **kwargs):
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker with code: {rc}")
            if self.running:
                threading.Timer(5.0, self.connect).start()
        else:
            logger.info("Disconnected from MQTT broker")
    
    def on_message(self, client, userdata, msg, *args, **kwargs):
        try:
            logger.debug(f"Received message on topic {msg.topic}")
            
            for topic_pattern, handler in self.handlers.items():
                if msg.topic == topic_pattern or (
                    topic_pattern.endswith("/#") and 
                    msg.topic.startswith(topic_pattern[:-2])
                ):
                    handler(msg)
                    break
                    
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def handle_valve_control(self, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            sector_id = payload.get('sector_id')
            action = payload.get('action')
            
            if not sector_id or not action:
                logger.error("Invalid valve control message: missing sector_id or action")
                return
                
            logger.info(f"Valve control message received: Sector {sector_id}, Action {action}")
            
        except json.JSONDecodeError:
            logger.error(f"Invalid valve control format: {msg.payload}")
        except Exception as e:
            logger.error(f"Error handling valve control: {e}")
    
    def handle_valve_status(self, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            sector_id = payload.get('sector_id')
            state = payload.get('state')
            
            if not sector_id or not state:
                logger.error("Invalid valve status message: missing sector_id or state")
                return
                
            logger.info(f"Valve status update: Sector {sector_id}, State {state}")
            
        except json.JSONDecodeError:
            logger.error(f"Invalid valve status format: {msg.payload}")
        except Exception as e:
            logger.error(f"Error handling valve status: {e}")
    
    def handle_sensor_data(self, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            
            device_id = payload.get('device_id')
            timestamp = payload.get('timestamp')
            readings = payload.get('readings', {})
            
            if not device_id or not readings:
                logger.error("Invalid sensor data: missing device_id or readings")
                return
                
            temperature = readings.get('temperature', {}).get('value')
            pressure = readings.get('pressure', {}).get('value')
            
            logger.info(f"Sensor data received: Device {device_id}, Temperature {temperature}°C, Pressure {pressure}hPa")
            
            sector_id = payload.get('sector_id')
            if sector_id and temperature and temperature > config.TEMPERATURE_THRESHOLD:
                logger.warning(f"High temperature detected in Sector {sector_id}: {temperature}°C")
                
                valve_state = "closed"
                timestamp = datetime.now().isoformat()
                
                valve_status = {
                    "timestamp": timestamp,
                    "sector_id": sector_id,
                    "state": valve_state
                }
                self.client.publish(
                    config.VALVE_STATUS_TOPIC,
                    json.dumps(valve_status),
                    qos=1
                )
                
        except json.JSONDecodeError:
            logger.error(f"Invalid sensor data format: {msg.payload}")
        except Exception as e:
            logger.error(f"Error handling sensor data: {e}")
    
    def handle_system_event(self, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            logger.info(f"System event received: {payload}")
            
        except json.JSONDecodeError:
            logger.error(f"Invalid system event format: {msg.payload}")
        except Exception as e:
            logger.error(f"Error handling system event: {e}")
    
    def connect(self):
        try:
            # Set the connection retry parameters
            self.client.reconnect_delay_set(min_delay=1, max_delay=10)
            self.client.connect_async(config.MQTT_HOST, config.MQTT_PORT, keepalive=30)
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False
    
    def start(self):
        if self.running:
            logger.warning("Control Center client already running")
            return False
        
        self.running = True
        
        if not self.connect():
            self.running = False
            return False
        
        self.client.loop_start()
        
        logger.info("Control Center MQTT client started")
        
        startup_message = {
            "event": "control_center_start",
            "timestamp": datetime.now().isoformat(),
            "client_id": config.MQTT_CLIENT_ID
        }
        self.client.publish(
            config.SYSTEM_EVENTS_TOPIC,
            json.dumps(startup_message),
            qos=1
        )
        
        return True
    
    def stop(self):
        if not self.running:
            return False
        
        self.running = False
        
        shutdown_message = {
            "event": "broker_stop",
            "timestamp": datetime.now().isoformat(),
            "broker_id": config.MQTT_CLIENT_ID
        }
        
        self.client.publish(
            config.SYSTEM_EVENTS_TOPIC,
            json.dumps(shutdown_message),
            qos=1
        )
        
        time.sleep(1)
        
        self.client.disconnect()
        self.client.loop_stop()
        
        logger.info("Message broker stopped")
        return True
    
    def publish_message(self, topic, payload, qos=0, retain=False):
        if not self.running:
            logger.warning("Cannot publish message: broker not running")
            return False
        
        try:
            if isinstance(payload, (dict, list)):
                payload = json.dumps(payload)
            
            result = self.client.publish(topic, payload, qos=qos, retain=retain)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"Message published to {topic}")
                return True
            else:
                logger.error(f"Failed to publish message to {topic}: {result.rc}")
                return False
        except Exception as e:
            logger.error(f"Error publishing message: {e}")
            return False


def main():
    mqtt_client = MessageBroker()
    
    def signal_handler(sig, frame):
        logger.info("Shutdown signal received")
        mqtt_client.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if mqtt_client.start():
        print(f"Control Center connected to MQTT broker at {config.MQTT_HOST}:{config.MQTT_PORT}")
        print("Press Ctrl+C to stop")
        
        try:
            while mqtt_client.running:
                time.sleep(0.1)  # More frequent checks to maintain connection
                # Send a ping every 30 seconds to keep connection alive
                if mqtt_client.running and time.time() % 30 < 0.1:
                    mqtt_client.client.publish(config.SYSTEM_EVENTS_TOPIC + "/ping", "", qos=0, retain=False)
        except KeyboardInterrupt:
            mqtt_client.stop()
    else:
        print("Failed to start Control Center")


if __name__ == "__main__":
    main()
