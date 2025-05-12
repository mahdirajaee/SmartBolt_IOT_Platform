#!/usr/bin/env python3

import os
import sys
import signal
import logging
import sqlite3
import json
import time
import threading
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

class MessageStore:
    
    def __init__(self, db_file=config.PERSISTENCE_FILE):
        self.db_file = db_file
        self.initialize_db()
    
    def initialize_db(self):
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    qos INTEGER DEFAULT 0,
                    timestamp TEXT NOT NULL
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS retained_messages (
                    topic TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    qos INTEGER DEFAULT 0,
                    timestamp TEXT NOT NULL
                )
            ''')
            
            conn.commit()
            logger.info("Message store initialized")
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")
        finally:
            if conn:
                conn.close()
    
    def store_message(self, topic, payload, qos=0, retained=False):
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            timestamp = datetime.now().isoformat()
            
            if isinstance(payload, (dict, list)):
                payload = json.dumps(payload)
                
            cursor.execute(
                "INSERT INTO messages (topic, payload, qos, timestamp) VALUES (?, ?, ?, ?)",
                (topic, payload, qos, timestamp)
            )
            
            if retained:
                cursor.execute(
                    "INSERT OR REPLACE INTO retained_messages (topic, payload, qos, timestamp) VALUES (?, ?, ?, ?)",
                    (topic, payload, qos, timestamp)
                )
                
            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Failed to store message: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def get_retained_messages(self):
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            cursor.execute("SELECT topic, payload, qos FROM retained_messages")
            messages = cursor.fetchall()
            
            result = []
            for topic, payload_str, qos in messages:
                try:
                    payload = json.loads(payload_str)
                except (json.JSONDecodeError, TypeError):
                    payload = payload_str
                    
                result.append({
                    "topic": topic,
                    "payload": payload,
                    "qos": qos
                })
                
            return result
        except sqlite3.Error as e:
            logger.error(f"Failed to get retained messages: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def get_message_history(self, topic=None, limit=100):
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            if topic:
                cursor.execute(
                    "SELECT id, topic, payload, qos, timestamp FROM messages WHERE topic = ? ORDER BY id DESC LIMIT ?", 
                    (topic, limit)
                )
            else:
                cursor.execute(
                    "SELECT id, topic, payload, qos, timestamp FROM messages ORDER BY id DESC LIMIT ?", 
                    (limit,)
                )
                
            messages = cursor.fetchall()
            
            result = []
            for msg_id, topic, payload_str, qos, timestamp in messages:
                try:
                    payload = json.loads(payload_str)
                except (json.JSONDecodeError, TypeError):
                    payload = payload_str
                    
                result.append({
                    "id": msg_id,
                    "topic": topic,
                    "payload": payload,
                    "qos": qos,
                    "timestamp": timestamp
                })
                
            return result
        except sqlite3.Error as e:
            logger.error(f"Failed to get message history: {e}")
            return []
        finally:
            if conn:
                conn.close()


class MessageBroker:
    
    def __init__(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.client_id = config.MQTT_CLIENT_ID
        self.running = False
        
        self.message_store = None
        if config.PERSISTENCE_ENABLED:
            self.message_store = MessageStore()
        
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        
        if config.MQTT_USERNAME or config.MQTT_PASSWORD:
            self.client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)
        
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
            
            if config.PERSISTENCE_ENABLED and self.message_store:
                retained_messages = self.message_store.get_retained_messages()
                for msg in retained_messages:
                    self.client.publish(
                        msg["topic"], 
                        msg["payload"] if isinstance(msg["payload"], str) else json.dumps(msg["payload"]),
                        qos=msg["qos"],
                        retain=True
                    )
                logger.info(f"Republished {len(retained_messages)} retained messages")
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
            logger.debug(f"Message received on {msg.topic}: {msg.payload}")
            
            if msg.topic == config.VALVE_CONTROL_TOPIC:
                self.handle_valve_control(msg)
            elif msg.topic == config.VALVE_STATUS_TOPIC:
                self.handle_valve_status(msg)
            elif msg.topic == config.SENSOR_DATA_TOPIC:
                self.handle_sensor_data(msg)
            elif msg.topic == config.SYSTEM_EVENTS_TOPIC:
                self.handle_system_event(msg)
            
            if config.PERSISTENCE_ENABLED and self.message_store:
                self.message_store.store_message(
                    msg.topic, 
                    msg.payload.decode('utf-8'), 
                    msg.qos,
                    msg.retain
                )
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def handle_valve_control(self, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            logger.info(f"Valve control message received: {payload}")
            
            ack_topic = f"{config.VALVE_CONTROL_TOPIC}/ack"
            ack_payload = {
                "timestamp": datetime.now().isoformat(),
                "status": "received",
                "original_message": payload
            }
            self.client.publish(
                ack_topic,
                json.dumps(ack_payload),
                qos=1
            )
        except json.JSONDecodeError:
            logger.error(f"Invalid valve control message format: {msg.payload}")
        except Exception as e:
            logger.error(f"Error handling valve control message: {e}")
    
    def handle_valve_status(self, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            logger.info(f"Valve status message received: {payload}")
            
            timestamp = payload.get("timestamp")
            sector_id = payload.get("sector_id", "unknown")
            valve_state = payload.get("state", "unknown")
            
            logger.info(f"Valve in sector {sector_id} is {valve_state}")
            
            if valve_state == "open":
                logger.info(f"Valve in sector {sector_id} has been opened")
            elif valve_state == "closed":
                logger.info(f"Valve in sector {sector_id} has been closed")
            elif valve_state == "error":
                logger.warning(f"Valve in sector {sector_id} is reporting an error state")
                
        except json.JSONDecodeError:
            logger.error(f"Invalid valve status message format: {msg.payload}")
        except Exception as e:
            logger.error(f"Error handling valve status message: {e}")
    
    def handle_sensor_data(self, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            logger.info(f"Sensor data message received")
            
            timestamp = payload.get("timestamp")
            device_id = payload.get("device_id")
            readings = payload.get("readings", {})
            
            if "temperature" in readings:
                temp_value = readings["temperature"].get("value")
                temp_unit = readings["temperature"].get("unit", "celsius")
                logger.info(f"Temperature reading from device {device_id}: {temp_value} {temp_unit}")
                
                if temp_value is not None and temp_value > 80:
                    logger.warning(f"High temperature alert: {temp_value} {temp_unit}")
            
            if "pressure" in readings:
                pressure_value = readings["pressure"].get("value")
                pressure_unit = readings["pressure"].get("unit", "hPa")
                logger.info(f"Pressure reading from device {device_id}: {pressure_value} {pressure_unit}")
                
                if pressure_value is not None and pressure_value > 1100:
                    logger.warning(f"High pressure alert: {pressure_value} {pressure_unit}")
            
            sector_info = payload.get("sector_info", {})
            if sector_info and "valve_state" in sector_info:
                valve_state = sector_info["valve_state"]
                sector_id = sector_info.get("sector_id", "unknown")
                logger.info(f"Valve status in sector {sector_id}: {valve_state}")
                
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
            self.client.connect(config.MQTT_HOST, config.MQTT_PORT, config.MQTT_KEEPALIVE)
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False
    
    def start(self):
        if self.running:
            logger.warning("Message broker already running")
            return False
        
        self.running = True
        
        if not self.connect():
            self.running = False
            return False
        
        self.client.loop_start()
        
        logger.info("Message broker started")
        
        startup_message = {
            "event": "broker_start",
            "timestamp": datetime.now().isoformat(),
            "broker_id": config.MQTT_CLIENT_ID
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
  
    broker = MessageBroker()
    
    def signal_handler(sig, frame):
        logger.info("Shutdown signal received")
        broker.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    if broker.start():
        print(f"Message broker started on {config.MQTT_HOST}:{config.MQTT_PORT}")
        print("Press Ctrl+C to stop")
        
        try:
            while broker.running:
                time.sleep(1)
        except KeyboardInterrupt:
            broker.stop()
    else:
        print("Failed to start message broker")


if __name__ == "__main__":
    main()