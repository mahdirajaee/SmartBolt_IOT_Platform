import json
import logging
import paho.mqtt.client as mqtt
from config import CONFIG

logger = logging.getLogger(__name__)

class MQTTClient:
    """MQTT Client for subscribing to sensor data and alerts"""
    
    def __init__(self, on_sensor_data=None, on_alert=None):
        """Initialize MQTT client with callbacks
        
        Args:
            on_sensor_data: Callback function for sensor data
            on_alert: Callback function for alerts
        """
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        
        self.broker = CONFIG["mqtt"]["broker"] 
        self.port = CONFIG["mqtt"]["port"]
        self.topics = CONFIG["mqtt"]["topics"]
        
        self.on_sensor_data_callback = on_sensor_data
        self.on_alert_callback = on_alert
        
        self.is_connected = False
        
    def on_connect(self, client, userdata, flags, rc):
        """Callback when client connects to the broker"""
        if rc == 0:
            logger.info("Connected to MQTT broker")
            self.is_connected = True
            
            # Subscribe to topics
            self.client.subscribe(self.topics["sensor_data"])
            self.client.subscribe(self.topics["alerts"])
        else:
            logger.error(f"Failed to connect to MQTT broker, return code: {rc}")
            self.is_connected = False
    
    def on_message(self, client, userdata, msg):
        """Callback when message is received"""
        try:
            payload = json.loads(msg.payload.decode())
            topic = msg.topic
            
            if topic.startswith("smart_bolt/sensors/"):
                if self.on_sensor_data_callback:
                    self.on_sensor_data_callback(payload)
            elif topic == self.topics["alerts"]:
                if self.on_alert_callback:
                    self.on_alert_callback(payload)
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON payload: {msg.payload}")
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
    
    def connect(self):
        """Connect to MQTT broker"""
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
        except Exception as e:
            logger.error(f"Error connecting to MQTT broker: {str(e)}")
    
    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.is_connected:
            self.client.loop_stop()
            self.client.disconnect()
            self.is_connected = False
            
    def publish_command(self, command):
        """Publish command to command topic"""
        try:
            self.client.publish(
                self.topics["commands"],
                json.dumps(command)
            )
            return True
        except Exception as e:
            logger.error(f"Error publishing command: {str(e)}")
            return False