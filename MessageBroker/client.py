#!/usr/bin/env python3

import json
import time
import logging
import threading
from datetime import datetime
from queue import Queue, Empty 
import paho.mqtt.client as mqtt
import os
import sys

try:
    from messagebroker import config as broker_config
except ImportError:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import config as broker_config
    except ImportError:
        print("Warning: Could not import message broker config")
        class MinimalConfig:
            MQTT_HOST = "localhost"
            MQTT_PORT = 1883
            MQTT_USERNAME = ""
            MQTT_PASSWORD = ""
            TLS_ENABLED = False
            VALVE_CONTROL_TOPIC = "valve/control"
            VALVE_STATUS_TOPIC = "valve/status"
        broker_config = MinimalConfig()

logger = logging.getLogger('mqtt_client')

class MQTTClient:
    
    def __init__(self, client_id=None, clean_session=True):
        if not client_id:
            client_id = f"smartbolt_client_{int(time.time())}"
            
        self.client_id = client_id
        self.client = mqtt.Client(client_id=client_id, clean_session=clean_session)
        self.connected = False
        self.last_connection_time = None
        
        self.subscriptions = {}
        self.message_queue = Queue()
        self.message_callbacks = {}
        
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        self.worker_thread = None
        self.running = False
        
        mqtt_username = getattr(broker_config, 'MQTT_USERNAME', "")
        mqtt_password = getattr(broker_config, 'MQTT_PASSWORD', "")
        tls_enabled = getattr(broker_config, 'TLS_ENABLED', False)
        
        if mqtt_username and mqtt_password:
            self.client.username_pw_set(mqtt_username, mqtt_password)
            
        if tls_enabled:
            self.client.tls_set()
    
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            self.last_connection_time = datetime.now()
            logger.info(f"Connected to MQTT broker as {self.client_id}")
            
            for topic, qos in self.subscriptions.items():
                self.client.subscribe(topic, qos)
                logger.debug(f"Resubscribed to {topic} with QoS {qos}")
        else:
            self.connected = False
            logger.error(f"Failed to connect to MQTT broker with code: {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker with code: {rc}")
        else:
            logger.info("Disconnected from MQTT broker")
    
    def _on_message(self, client, userdata, msg):
        logger.debug(f"Message received on {msg.topic}: {msg.payload}")
        
        self.message_queue.put(msg)
    
    def _process_messages(self):
        while self.running:
            try:
                msg = self.message_queue.get(timeout=1.0)
                
                self._handle_message(msg)
                
                self.message_queue.task_done()
                
            except Empty:
                pass
            except Exception as e:
                logger.error(f"Error processing message: {e}")
    
    def _handle_message(self, msg):
        try:
            if msg.topic in self.message_callbacks:
                for callback in self.message_callbacks[msg.topic]:
                    try:
                        callback(msg.topic, msg.payload, msg.qos)
                    except Exception as e:
                        logger.error(f"Error in callback for topic {msg.topic}: {e}")
            
            for topic, callbacks in self.message_callbacks.items():
                if '+' in topic or '#' in topic:
                    if mqtt.topic_matches_sub(topic, msg.topic):
                        for callback in callbacks:
                            try:
                                callback(msg.topic, msg.payload, msg.qos)
                            except Exception as e:
                                logger.error(f"Error in callback for wildcard topic {topic}: {e}")
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    def connect(self, host=None, port=None, keepalive=60):
        if host is None:
            host = getattr(broker_config, 'MQTT_HOST', 'localhost')
        if port is None:
            port = getattr(broker_config, 'MQTT_PORT', 1883)
            
        try:
            self.client.connect(host, port, keepalive)
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False
    
    def disconnect(self):
        if not self.connected:
            return

        try:
            self.client.disconnect()
        except Exception as e:
            logger.error(f"Error disconnecting from MQTT broker: {e}")
    
    def start(self):
        if self.running:
            logger.warning("MQTT client already running")
            return False
            
        self.client.loop_start()
        
        self.running = True
        self.worker_thread = threading.Thread(target=self._process_messages)
        self.worker_thread.daemon = True
        self.worker_thread.start()
        
        logger.info("MQTT client started")
        return True
    
    def stop(self):
        if not self.running:
            return
            
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=2.0)
            
        self.disconnect()
        self.client.loop_stop()
        
        logger.info("MQTT client stopped")
    
    def subscribe(self, topic, qos=0, callback=None):
        if not self.connected:
            logger.warning(f"Not connected to broker, queuing subscription to {topic}")
            
        self.subscriptions[topic] = qos
        
        if callback:
            if topic not in self.message_callbacks:
                self.message_callbacks[topic] = []
            self.message_callbacks[topic].append(callback)
        
        if self.connected:
            result, _ = self.client.subscribe(topic, qos)
            return result == mqtt.MQTT_ERR_SUCCESS
        
        return False
    
    def unsubscribe(self, topic):
        if topic in self.subscriptions:
            del self.subscriptions[topic]
        
        if topic in self.message_callbacks:
            del self.message_callbacks[topic]
        
        if self.connected:
            result, _ = self.client.unsubscribe(topic)
            return result == mqtt.MQTT_ERR_SUCCESS
        
        return False
    
    def publish(self, topic, payload, qos=0, retain=False):
        try:
            if isinstance(payload, (dict, list)):
                payload = json.dumps(payload)
            
            if self.connected:
                result = self.client.publish(topic, payload, qos=qos, retain=retain)
                return result.rc == mqtt.MQTT_ERR_SUCCESS
            else:
                logger.error("Cannot publish: not connected to broker")
                return False
                
        except Exception as e:
            logger.error(f"Error publishing message: {e}")
            return False
    
    def wait_for_message(self, topic, timeout=5.0):
        msg_queue = Queue()
        received = threading.Event()
        
        def temp_callback(recv_topic, payload, qos):
            if topic == recv_topic:
                try:
                    try:
                        json_payload = json.loads(payload)
                        msg_queue.put(json_payload)
                    except json.JSONDecodeError:
                        msg_queue.put(payload)
                    received.set()
                except Exception as e:
                    logger.error(f"Error in wait_for_message callback: {e}")
        
        previous_callbacks = None
        if topic in self.message_callbacks:
            previous_callbacks = self.message_callbacks[topic]
        
        self.message_callbacks[topic] = [temp_callback]
        self.subscribe(topic)
        
        try:
            success = received.wait(timeout)
            if success:
                return msg_queue.get(block=False)
            else:
                return None
        finally:
            if previous_callbacks:
                self.message_callbacks[topic] = previous_callbacks
            else:
                del self.message_callbacks[topic]


class ValveControlClient:
    
    def __init__(self, client_id=None):
        if not client_id:
            client_id = f"valve_controller_{int(time.time())}"
            
        self.mqtt_client = MQTTClient(client_id=client_id)
        self.status_callbacks = {}
    
    def connect(self):
        success = self.mqtt_client.connect()
        if success:
            self.mqtt_client.start()
            self.mqtt_client.subscribe(
                getattr(broker_config, 'VALVE_STATUS_TOPIC', 'valve/status'), 
                qos=1, 
                callback=self._on_valve_status
            )
            self.mqtt_client.subscribe(
                f"{getattr(broker_config, 'VALVE_CONTROL_TOPIC', 'valve/control')}/ack", 
                qos=1, 
                callback=self._on_valve_control_ack
            )
        return success
    
    def disconnect(self):
        self.mqtt_client.stop()
    
    def _on_valve_status(self, topic, payload, qos):
        try:
            status = json.loads(payload)
            sector_id = status.get("sector_id")
            
            logger.debug(f"Valve status update for sector {sector_id}: {status}")
            
            if sector_id in self.status_callbacks:
                for callback in self.status_callbacks[sector_id]:
                    try:
                        callback(status)
                    except Exception as e:
                        logger.error(f"Error in valve status callback for sector {sector_id}: {e}")
        except Exception as e:
            logger.error(f"Error processing valve status: {e}")
    
    def _on_valve_control_ack(self, topic, payload, qos):
        try:
            ack = json.loads(payload)
            original_message = ack.get("original_message", {})
            sector_id = original_message.get("sector_id")
            
            logger.debug(f"Valve control acknowledgment for sector {sector_id}: {ack}")
        except Exception as e:
            logger.error(f"Error processing valve control ack: {e}")
    
    def open_valve(self, sector_id):
        message = {
            "sector_id": sector_id,
            "action": "open",
            "timestamp": datetime.now().isoformat()
        }
        return self.mqtt_client.publish(
            getattr(broker_config, 'VALVE_CONTROL_TOPIC', 'valve/control'), 
            message, 
            qos=1
        )
    
    def close_valve(self, sector_id):
        message = {
            "sector_id": sector_id,
            "action": "close",
            "timestamp": datetime.now().isoformat()
        }
        return self.mqtt_client.publish(
            getattr(broker_config, 'VALVE_CONTROL_TOPIC', 'valve/control'), 
            message, 
            qos=1
        )
    
    def set_valve_partial(self, sector_id, percentage):
        if not 0 <= percentage <= 100:
            logger.error(f"Invalid percentage value: {percentage}")
            return False
            
        message = {
            "sector_id": sector_id,
            "action": "partial",
            "percentage": percentage,
            "timestamp": datetime.now().isoformat()
        }
        return self.mqtt_client.publish(
            getattr(broker_config, 'VALVE_CONTROL_TOPIC', 'valve/control'), 
            message, 
            qos=1
        )
    
    def get_valve_status(self, sector_id, timeout=5.0):
        request_message = {
            "request": "status",
            "sector_id": sector_id,
            "timestamp": datetime.now().isoformat()
        }
        
        self.mqtt_client.publish(
            f"{getattr(broker_config, 'VALVE_STATUS_TOPIC', 'valve/status')}/request", 
            request_message, 
            qos=1
        )
        
        return self.mqtt_client.wait_for_message(
            getattr(broker_config, 'VALVE_STATUS_TOPIC', 'valve/status'), 
            timeout=timeout
        )
    
    def register_status_callback(self, sector_id, callback):
        if sector_id not in self.status_callbacks:
            self.status_callbacks[sector_id] = []
        self.status_callbacks[sector_id].append(callback)