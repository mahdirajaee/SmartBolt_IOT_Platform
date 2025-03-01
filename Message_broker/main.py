import paho.mqtt.client as mqtt
import time
import json
import logging
from datetime import datetime
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("message_broker")

# MQTT Broker Settings
BROKER = 'localhost'
PORT = 1883
KEEP_ALIVE_INTERVAL = 60

# Topic Structure
SENSOR_TOPICS = [
    "smartbolt/sector/+/bolt/+/temperature",
    "smartbolt/sector/+/bolt/+/pressure"
]
ACTUATOR_COMMAND_TOPIC = "smartbolt/actuator/+/command"
ACTUATOR_STATE_TOPIC = "smartbolt/actuator/+/state"
ALERT_TOPIC = "smartbolt/alerts/+"

# In-memory storage for received messages (for debugging/monitoring)
received_messages = {
    "sensors": {},
    "actuators": {},
    "alerts": []
}
message_lock = threading.Lock()

# Define callback functions
def on_connect(client, userdata, flags, rc):
    """Callback for when the client connects to the broker."""
    if rc == 0:
        logger.info("Connected to MQTT broker successfully")
        
        # Subscribe to all relevant topics
        for topic in SENSOR_TOPICS:
            client.subscribe(topic, qos=1)
            logger.info(f"Subscribed to: {topic}")
        
        client.subscribe(ACTUATOR_COMMAND_TOPIC, qos=2)
        logger.info(f"Subscribed to: {ACTUATOR_COMMAND_TOPIC}")
        
        client.subscribe(ACTUATOR_STATE_TOPIC, qos=1)
        logger.info(f"Subscribed to: {ACTUATOR_STATE_TOPIC}")
        
        client.subscribe(ALERT_TOPIC, qos=2)
        logger.info(f"Subscribed to: {ALERT_TOPIC}")
    else:
        logger.error(f"Failed to connect to MQTT broker with result code {rc}")
        
        # RC Error Codes
        error_codes = {
            1: "Connection refused - incorrect protocol version",
            2: "Connection refused - invalid client identifier",
            3: "Connection refused - server unavailable",
            4: "Connection refused - bad username or password",
            5: "Connection refused - not authorized"
        }
        if rc in error_codes:
            logger.error(f"Error details: {error_codes[rc]}")

def on_message(client, userdata, msg):
    """Callback for when a message is received from the broker."""
    try:
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        
        # Try to parse JSON payload
        try:
            payload_data = json.loads(payload)
        except json.JSONDecodeError:
            payload_data = payload
            
        logger.info(f"Message received on {topic}")
        logger.debug(f"Message content: {payload}")
        
        # Store message in memory for monitoring
        with message_lock:
            # Handle sensor data
            if any(topic.startswith(t.replace('+', '')) for t in SENSOR_TOPICS):
                topic_parts = topic.split('/')
                if len(topic_parts) >= 6:
                    sector_id = topic_parts[2]
                    bolt_id = topic_parts[4]
                    data_type = topic_parts[5]
                    
                    if sector_id not in received_messages["sensors"]:
                        received_messages["sensors"][sector_id] = {}
                    if bolt_id not in received_messages["sensors"][sector_id]:
                        received_messages["sensors"][sector_id][bolt_id] = {}
                        
                    received_messages["sensors"][sector_id][bolt_id][data_type] = {
                        "value": payload_data.get("value", payload),
                        "timestamp": datetime.now().isoformat()
                    }
            
            # Handle actuator commands/states
            elif topic.startswith("smartbolt/actuator/"):
                topic_parts = topic.split('/')
                if len(topic_parts) >= 4:
                    actuator_id = topic_parts[2]
                    message_type = topic_parts[3]  # command or state
                    
                    if actuator_id not in received_messages["actuators"]:
                        received_messages["actuators"][actuator_id] = {}
                        
                    received_messages["actuators"][actuator_id][message_type] = {
                        "value": payload_data,
                        "timestamp": datetime.now().isoformat()
                    }
            
            # Handle alerts
            elif topic.startswith("smartbolt/alerts/"):
                topic_parts = topic.split('/')
                if len(topic_parts) >= 3:
                    sector_id = topic_parts[2]
                    
                    received_messages["alerts"].append({
                        "sector_id": sector_id,
                        "alert": payload_data,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    # Keep only last 100 alerts
                    if len(received_messages["alerts"]) > 100:
                        received_messages["alerts"] = received_messages["alerts"][-100:]
        
    except Exception as e:
        logger.error(f"Error processing message: {e}")

def on_disconnect(client, userdata, rc):
    """Callback for when the client disconnects from the broker."""
    if rc != 0:
        logger.warning(f"Unexpected disconnection from MQTT broker with code {rc}")
    else:
        logger.info("Disconnected from MQTT broker")

def on_publish(client, userdata, mid):
    """Callback for when a message is published."""
    logger.debug(f"Message {mid} published")

def on_subscribe(client, userdata, mid, granted_qos):
    """Callback for when the client subscribes to a topic."""
    logger.debug(f"Subscribed with message ID {mid} and QoS {granted_qos}")

def on_log(client, userdata, level, buf):
    """Callback for MQTT client logging."""
    if level == mqtt.MQTT_LOG_ERR:
        logger.error(f"MQTT Log: {buf}")
    elif level == mqtt.MQTT_LOG_WARNING:
        logger.warning(f"MQTT Log: {buf}")
    else:
        logger.debug(f"MQTT Log: {buf}")

def create_client():
    """Create and configure MQTT client."""
    client_id = f"smartbolt-broker-{int(time.time())}"
    client = mqtt.Client(client_id=client_id)
    
    # Set callbacks
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    client.on_publish = on_publish
    client.on_subscribe = on_subscribe
    client.on_log = on_log
    
    # Enable logging
    client.enable_logger(logger)
    
    return client

def publish_message(client, topic, payload, qos=1, retain=False):
    """Publish a message to a topic."""
    try:
        # Convert dict to JSON string if needed
        if isinstance(payload, dict):
            payload = json.dumps(payload)
            
        # Publish message
        result = client.publish(topic, payload, qos=qos, retain=retain)
        result.wait_for_publish()
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            logger.info(f"Message published to {topic}")
            return True
        else:
            logger.error(f"Failed to publish message to {topic}: {result.rc}")
            return False
    except Exception as e:
        logger.error(f"Error publishing message: {e}")
        return False

def print_status():
    """Print the current status of the message broker."""
    while True:
        try:
            time.sleep(60)  # Print status every minute
            
            with message_lock:
                sensor_count = sum(len(bolts) for sector, bolts in received_messages["sensors"].items())
                actuator_count = len(received_messages["actuators"])
                alert_count = len(received_messages["alerts"])
                
            logger.info(f"Status: {sensor_count} sensors, {actuator_count} actuators, {alert_count} alerts processed")
        except Exception as e:
            logger.error(f"Error printing status: {e}")

def start_broker():
    """Start the MQTT message broker."""
    try:
        logger.info("Starting SmartBolt MQTT Message Broker")
        
        # Create MQTT client
        client = create_client()
        
        # Connect to MQTT broker
        logger.info(f"Connecting to MQTT broker at {BROKER}:{PORT}")
        client.connect(BROKER, PORT, KEEP_ALIVE_INTERVAL)
        
        # Start the status thread
        threading.Thread(target=print_status, daemon=True).start()
        
        # Start the loop to process callbacks
        client.loop_forever()
        
    except KeyboardInterrupt:
        logger.info("Message broker stopped by user")
        if client:
            client.disconnect()
    except Exception as e:
        logger.error(f"Error in message broker: {e}")
        if client:
            client.disconnect()

if __name__ == "__main__":
    start_broker()