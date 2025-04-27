import json
import logging
import paho.mqtt.client as mqtt
import time

class MQTTClient:
    def __init__(self, config_path="config.json"):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.broker = self.config["mqtt"]["broker"]
        self.port = self.config["mqtt"]["port"]
        self.topic_commands = self.config["mqtt"]["topic_commands"]
        self.client_id = f"telegram_bot_{int(time.time())}"
        self.logger = logging.getLogger("mqtt_client")
        
        self.client = mqtt.Client(client_id=self.client_id)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_publish = self.on_publish
        
    def connect(self):
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            return True
        except Exception as e:
            self.logger.error(f"Failed to connect to MQTT broker: {str(e)}")
            return False
    
    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()
    
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.logger.info(f"Connected to MQTT broker at {self.broker}:{self.port}")
        else:
            self.logger.error(f"Failed to connect to MQTT broker. Return code: {rc}")
    
    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            self.logger.warning("Unexpected disconnection from MQTT broker")
        else:
            self.logger.info("Disconnected from MQTT broker")
    
    def on_publish(self, client, userdata, mid):
        self.logger.debug(f"Message {mid} published")
    
    def send_command(self, actuator_id, command, value=None):
        try:
            message = {
                "timestamp": int(time.time()),
                "actuator_id": actuator_id,
                "command": command
            }
            
            if value is not None:
                message["value"] = value
                
            payload = json.dumps(message)
            result = self.client.publish(self.topic_commands, payload, qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.logger.info(f"Command sent to {actuator_id}: {command}")
                return True
            else:
                self.logger.error(f"Failed to send command: {result.rc}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending command: {str(e)}")
            return False 