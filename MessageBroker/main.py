#!/usr/bin/env python3

import sys
import signal
import time
import random
import string
import cherrypy
import subprocess
import os
import paho.mqtt.client as mqtt
import json
import logging
import threading
from datetime import datetime
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

class MQTTController:
    def __init__(self):
        self.running = False
        self.process = None
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="controller_" + ''.join(random.choices(string.ascii_letters + string.digits, k=8)))
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
    
    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            logger.info(f"Controller connected to MQTT broker with result code {rc}")
            self.client.subscribe("#")
        else:
            logger.error(f"Failed to connect to MQTT broker with code: {rc}")
    
    def on_message(self, client, userdata, msg, *args, **kwargs):
        try:
            logger.debug(f"Received message on topic {msg.topic}: {msg.payload.decode()}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def on_disconnect(self, client, userdata, rc, *args, **kwargs):
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker with code: {rc}")
        else:
            logger.info("Disconnected from MQTT broker")
    
    def start_mosquitto(self):
        try:
            data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mosquitto_data")
            if not os.path.exists(data_dir):
                os.makedirs(data_dir)
            
            cmd = ["mosquitto", "-p", str(config.MQTT_PORT), "-v"]
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            
            time.sleep(2)  # Give mosquitto time to start
            
            if self.process.poll() is not None:
                logger.error(f"Failed to start mosquitto: {self.process.communicate()[0].decode()}")
                return False
                
            logger.info(f"Mosquitto started with PID {self.process.pid}")
            return True
        except Exception as e:
            logger.error(f"Error starting mosquitto: {e}")
            return False
    
    def start(self):
        if self.running:
            logger.warning("MQTT broker already running")
            return False
        
        if not self.start_mosquitto():
            return False
        
        try:
            self.client.connect(config.MQTT_HOST, config.MQTT_PORT, config.MQTT_KEEPALIVE)
            self.client.loop_start()
            self.running = True
            
            startup_message = {
                "event": "broker_start",
                "timestamp": datetime.now().isoformat(),
                "broker_id": config.MQTT_CLIENT_ID
            }
            self.client.publish(config.SYSTEM_EVENTS_TOPIC, json.dumps(startup_message), qos=1)
            
            logger.info(f"MQTT controller connected to broker at {config.MQTT_HOST}:{config.MQTT_PORT}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect controller to MQTT broker: {e}")
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
        
        try:
            self.client.publish(config.SYSTEM_EVENTS_TOPIC, json.dumps(shutdown_message), qos=1)
            time.sleep(1)
            self.client.disconnect()
            self.client.loop_stop()
        except:
            logger.info("MQTT client already disconnected")
        
        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            logger.info("Mosquitto broker stopped")
        
        return True

class BrokerStatusWebService(object):
    exposed = True
    
    def __init__(self, controller):
        self.controller = controller
    
    def GET(self, *path, **query):
        status = {
            "status": "running" if self.controller.running else "stopped",
            "mqtt_port": config.MQTT_PORT,
            "broker_id": config.MQTT_CLIENT_ID
        }
        return status
    
    def POST(self, *path, **query):
        mystring = "POST RESPONSE: "
        mystring += cherrypy.request.body.read()
        return mystring
        
    def PUT(self, *path, **query):
        mystring = "PUT RESPONSE: "
        mystring += cherrypy.request.body.read()
        return mystring
        
    def DELETE(self, *path, **query):
        return {"message": "Operation not supported"}

if __name__ == "__main__":
    def signal_handler(sig, frame):
        print("Shutting down MQTT broker...")
        if controller.running:
            controller.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("Starting SmartBolt Message Broker...")
    
    controller = MQTTController()
    
    if controller.start():
        print(f"Message broker started on {config.MQTT_HOST}:{config.MQTT_PORT}")
        
        conf = {
            '/': {
                'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
                'tools.sessions.on': True,
            }
        }
        
        cherrypy.tree.mount(BrokerStatusWebService(controller), '/', conf)
        cherrypy.config.update({'server.socket_host': '0.0.0.0'})
        cherrypy.config.update({'server.socket_port': config.WEB_INTERFACE_PORT})
        cherrypy.engine.start()
        cherrypy.engine.block()
    else:
        print("Failed to start message broker")
        sys.exit(1)
