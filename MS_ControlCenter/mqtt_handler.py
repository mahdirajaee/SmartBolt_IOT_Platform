#!/usr/bin/env python3

import sys
import os
import json
import time
import logging
from datetime import datetime
import threading

broker_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'messagebroker'))
sys.path.insert(0, broker_path)

try:
    from messagebroker.client import MQTTClient
except ImportError:
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    try:
        from messagebroker.client import MQTTClient
    except ImportError:
        print("Could not import MQTT client. Running in standalone mode.")
        MQTTClient = None

import config

logger = logging.getLogger('mqtt_handler')

class MQTTHandler:
    def __init__(self, sensor_callback=None, valve_status_callback=None):
        self.client = None
        self.client_id = f"{config.MQTT_CLIENT_ID}_{int(time.time())}"
        self.sensor_callback = sensor_callback
        self.valve_status_callback = valve_status_callback
        self.running = False
        
    def connect(self):
        if MQTTClient is None:
            logger.error("MQTTClient not available")
            return False
            
        try:
            self.client = MQTTClient(client_id=self.client_id)
            success = self.client.connect(
                host=config.MQTT_HOST,
                port=config.MQTT_PORT
            )
            
            if success:
                self.client.start()
                logger.info(f"Connected to MQTT broker at {config.MQTT_HOST}:{config.MQTT_PORT}")
                return True
            else:
                logger.error("Failed to connect to MQTT broker")
                return False
        except Exception as e:
            logger.error(f"Error connecting to MQTT broker: {e}")
            return False
            
    def subscribe_to_topics(self):
        if self.client is None:
            logger.error("MQTT client not initialized")
            return False
            
        logger.info("Subscribing to MQTT topics")
        
        if self.sensor_callback:
            self.client.subscribe(
                config.SENSOR_DATA_TOPIC, 
                qos=1, 
                callback=self._on_sensor_data
            )
            logger.info(f"Subscribed to sensor data topic: {config.SENSOR_DATA_TOPIC}")
            
        if self.valve_status_callback:
            self.client.subscribe(
                config.VALVE_STATUS_TOPIC,
                qos=1,
                callback=self._on_valve_status
            )
            logger.info(f"Subscribed to valve status topic: {config.VALVE_STATUS_TOPIC}")
            
        return True
            
    def _on_sensor_data(self, topic, payload, qos):
        logger.debug(f"Received sensor data on topic {topic}")
        try:
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8')
                
            data = json.loads(payload)
            
            if self.sensor_callback:
                self.sensor_callback(data)
        except Exception as e:
            logger.error(f"Error processing sensor data: {e}")
            
    def _on_valve_status(self, topic, payload, qos):
        logger.debug(f"Received valve status on topic {topic}")
        try:
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8')
                
            data = json.loads(payload)
            
            if self.valve_status_callback:
                self.valve_status_callback(data)
        except Exception as e:
            logger.error(f"Error processing valve status: {e}")
            
    def publish_valve_command(self, sector_id, action):
        if self.client is None:
            logger.error("MQTT client not initialized")
            return False
            
        message = {
            "sector_id": sector_id,
            "action": action,
            "timestamp": datetime.now().isoformat(),
            "source": "control_center"
        }
        
        logger.info(f"Publishing valve command: {action} for sector {sector_id}")
        
        return self.client.publish(
            config.VALVE_CONTROL_TOPIC,
            json.dumps(message),
            qos=1
        )
        
    def publish_alert(self, message, severity="warning"):
        if self.client is None:
            logger.error("MQTT client not initialized")
            return False
            
        alert = {
            "timestamp": datetime.now().isoformat(),
            "source": "control_center",
            "severity": severity,
            "message": message
        }
        
        logger.info(f"Publishing alert: {message}")
        
        return self.client.publish(
            f"{config.SYSTEM_EVENTS_TOPIC}/alerts",
            json.dumps(alert),
            qos=1
        )
        
    def start(self):
        if self.running:
            logger.warning("MQTT handler already running")
            return False
            
        if not self.connect():
            return False
            
        if not self.subscribe_to_topics():
            self.stop()
            return False
            
        self.running = True
        logger.info("MQTT handler started")
        return True
        
    def stop(self):
        if not self.running:
            return True
            
        if self.client:
            self.client.stop()
            
        self.running = False
        logger.info("MQTT handler stopped")
        return True