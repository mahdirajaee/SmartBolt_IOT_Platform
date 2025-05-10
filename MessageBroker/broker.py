#!/usr/bin/env python3

import os
import sys
import signal
import logging
import json
import time
import threading
import socket
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
        self.running = False
        self.broker = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.broker.on_connect = self.on_connect
        self.broker.on_message = self.on_message
        self.broker.on_disconnect = self.on_disconnect
        
        if config.MQTT_USERNAME and config.MQTT_PASSWORD:
            self.broker.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info(f"MQTT broker connected with result code {rc}")
            self.broker.subscribe("#")
        else:
            logger.error(f"Failed to connect to MQTT broker with code: {rc}")
    
    def on_message(self, client, userdata, msg, *args, **kwargs):
        try:
            logger.debug(f"Received message on topic {msg.topic}")
            payload = msg.payload.decode('utf-8')
            logger.debug(f"Message content: {payload}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def on_disconnect(self, client, userdata, rc, *args, **kwargs):
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker with code: {rc}")
        else:
            logger.info("Disconnected from MQTT broker")
    
    def publish_message(self, topic, payload, qos=0, retain=False):
        if not self.running:
            logger.warning("Cannot publish message: broker not running")
            return False
        
        try:
            if isinstance(payload, (dict, list)):
                payload = json.dumps(payload)
            
            result = self.broker.publish(topic, payload, qos=qos, retain=retain)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.debug(f"Message published to {topic}")
                return True
            else:
                logger.error(f"Failed to publish message to {topic}: {result.rc}")
                return False
        except Exception as e:
            logger.error(f"Error publishing message: {e}")
            return False
    

    

    
    def start(self):
        if self.running:
            logger.warning("Message broker already running")
            return False
        
        try:
            self.broker.connect(config.MQTT_HOST, config.MQTT_PORT, config.MQTT_KEEPALIVE)
            self.broker.loop_start()
            self.running = True
            
            startup_message = {
                "event": "broker_start",
                "timestamp": datetime.now().isoformat(),
                "broker_id": config.MQTT_CLIENT_ID
            }
            self.broker.publish(config.SYSTEM_EVENTS_TOPIC, json.dumps(startup_message), qos=1)
            
            logger.info(f"Message broker started on {config.MQTT_HOST}:{config.MQTT_PORT}")
            return True
        except Exception as e:
            logger.error(f"Failed to start MQTT broker: {e}")
            return False
    
    def stop(self):
        if not self.running:
            return False
        
        self.running = False
        
        shutdown_message = {
            "event": "broker_stop",
            "timestamp": datetime.now().isoformat(),
            "broker_id": config.MQTT_CLIENT_ID
        }
        
        self.broker.publish(config.SYSTEM_EVENTS_TOPIC, json.dumps(shutdown_message), qos=1)
        time.sleep(1)
        
        self.broker.disconnect()
        self.broker.loop_stop()
        
        logger.info("Message broker stopped")
        return True
    


