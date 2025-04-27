import json
import logging
import threading
import time
from datetime import datetime
import config as local_config  # Rename to avoid namespace conflicts
from storage import StorageManager
import sys
import os

# Add messagebroker directory to the path so we can import the client module
broker_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'messagebroker'))
sys.path.insert(0, broker_path)

try:
    # Import the broker's config module explicitly for MQTT client
    from messagebroker import config as broker_config
    from messagebroker.client import MQTTClient
except ImportError:
    # Fall back to direct import if the module structure is different
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    try:
        from messagebroker import config as broker_config
        from messagebroker.client import MQTTClient
    except ImportError:
        print("Warning: Could not import message broker client. Running in standalone mode.")
        broker_config = None
        MQTTClient = None

# Set up logging
logger = logging.getLogger('valve_controller')
if local_config.LOGGING_ENABLED:
    logger.setLevel(getattr(logging, local_config.LOG_LEVEL))
    handler = logging.FileHandler('valve_controller.log')
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
else:
    logger.addHandler(logging.NullHandler())

class ValveMessageHandler:
    """Handler for valve control messages sent via message broker"""
    
    def __init__(self):
        self.storage = StorageManager()
        self.running = False
        self.listener_thread = None
        
        # Get message broker settings from config
        self.broker_enabled = hasattr(local_config, 'VALVE_CONTROL_ENABLED') and local_config.VALVE_CONTROL_ENABLED
        self.broker_host = getattr(local_config, 'MQTT_BROKER', 'localhost')
        self.broker_port = getattr(local_config, 'MQTT_PORT', 1883)
        self.control_topic = getattr(local_config, 'VALVE_CONTROL_TOPIC', 'valve/control')
        self.status_topic = getattr(local_config, 'VALVE_STATUS_TOPIC', 'valve/status') 
        
        # MQTT client for message broker
        self.broker_client = None
        
        if self.broker_enabled and MQTTClient is not None:
            client_id = f"valve_handler_{int(time.time())}"
            # Ensure broker_config is properly referenced
            if broker_config is None:
                print("Warning: broker_config is None, creating a minimal config to avoid TLS_ENABLED errors")
                class MinimalBrokerConfig:
                    MQTT_HOST = self.broker_host
                    MQTT_PORT = self.broker_port
                    MQTT_USERNAME = ""
                    MQTT_PASSWORD = ""
                    TLS_ENABLED = False
                    VALVE_CONTROL_TOPIC = self.control_topic
                    VALVE_STATUS_TOPIC = self.status_topic
                _broker_config = MinimalBrokerConfig()
            else:
                _broker_config = broker_config
            
            # Import the MQTTClient from broker_client module
            sys.modules['config'] = _broker_config
            self.broker_client = MQTTClient(client_id=client_id)
            
    def start(self):
        """Start the valve control message listener"""
        if self.running:
            logger.warning("Valve message handler already running")
            return False
            
        self.running = True
        
        # Connect to message broker if enabled
        if self.broker_enabled and self.broker_client:
            logger.info(f"Connecting to message broker at {self.broker_host}:{self.broker_port}")
            try:
                success = self.broker_client.connect(host=self.broker_host, port=self.broker_port)
                if success:
                    self.broker_client.start()
                    # Subscribe to valve control topic
                    self.broker_client.subscribe(self.control_topic, qos=1, callback=self._on_control_message)
                    logger.info(f"Subscribed to valve control topic: {self.control_topic}")
                else:
                    logger.error("Failed to connect to message broker")
            except Exception as e:
                logger.error(f"Error connecting to message broker: {e}")
                # Continue even if broker connection fails
        
        # Start listener thread (used for standalone mode only)
        if not (self.broker_enabled and self.broker_client):
            self.listener_thread = threading.Thread(target=self._listener_loop)
            self.listener_thread.daemon = True
            self.listener_thread.start()
            
        logger.info("Valve control message handler started")
        return True
        
    def stop(self):
        """Stop the valve control message listener"""
        if not self.running:
            return False
            
        self.running = False
        
        # Disconnect from message broker
        if self.broker_client:
            self.broker_client.stop()
            
        # Stop listener thread
        if self.listener_thread:
            self.listener_thread.join(timeout=3.0)
            
        logger.info("Valve control message handler stopped")
        return True
        
    def _listener_loop(self):
        """Mock listener that will be replaced with actual message broker implementation"""
        logger.info(f"Valve control listener ready in standalone mode")
        
        while self.running:
            # This is a placeholder - we'll implement actual message broker code later
            time.sleep(1)
    
    def _on_control_message(self, topic, payload, qos):
        """Handle valve control messages received from message broker"""
        logger.info(f"Received valve control message on topic {topic}: {payload}")
        try:
            # Decode JSON message if it's bytes
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8')
                
            # Parse message and handle it
            message = json.loads(payload)
            self.handle_message(payload)
        except Exception as e:
            logger.error(f"Error processing control message: {e}")
            
    def handle_message(self, message):
        """Process a valve control message from the message broker"""
        try:
            # Parse the message as JSON if it's a string
            if isinstance(message, str):
                payload = json.loads(message)
            else:
                payload = message
                
            # Extract required fields
            sector_id = payload.get('sector_id')
            action = payload.get('action')
            
            if not sector_id or not action:
                logger.error("Invalid valve control message: missing sector_id or action")
                return False
                
            logger.info(f"Received valve control: Sector {sector_id}, Action {action}")
            
            # Process the action
            if action.lower() == 'open':
                result = self.storage.open_valve(sector_id)
                if result:
                    self.publish_valve_status(sector_id, "open")
                return result
                
            elif action.lower() == 'close':
                result = self.storage.close_valve(sector_id)
                if result:
                    self.publish_valve_status(sector_id, "closed")
                return result
                
            elif action.lower() == 'partial':
                percentage = payload.get('percentage', 50)  # Default to 50% if not specified
                try:
                    percentage = int(percentage)
                    if not 0 <= percentage <= 100:
                        percentage = 50  # Default to 50% if out of range
                except ValueError:
                    percentage = 50  # Default to 50% if invalid
                    
                result = self.storage.set_valve_partial(sector_id, percentage)
                if result:
                    self.publish_valve_status(sector_id, f"partially_open_{percentage}%")
                return result
                
            else:
                logger.error(f"Invalid valve action: {action}")
                return False
                
        except json.JSONDecodeError:
            logger.error("Failed to parse valve control message as JSON")
            return False
        except Exception as e:
            logger.error(f"Error processing valve control message: {e}")
            return False
            
    def publish_valve_status(self, sector_id, state):
        """Publish valve status update to the message broker"""
        try:
            valve = self.storage.get_valve(sector_id)
            if not valve:
                logger.error(f"Failed to get valve for sector {sector_id}")
                return False
                
            status_message = {
                "timestamp": datetime.now().isoformat(),
                "sector_id": sector_id,
                "valve_state": state,
                "last_action": valve.last_action_timestamp
            }
            
            # Publish through message broker if connected
            if self.broker_client and self.broker_enabled:
                logger.info(f"Publishing valve status to {self.status_topic}")
                return self.broker_client.publish(
                    self.status_topic,
                    json.dumps(status_message),
                    qos=1
                )
            else:
                # Log the message in standalone mode
                logger.info(f"Valve status update (standalone mode): {status_message}")
                return True
            
        except Exception as e:
            logger.error(f"Error publishing valve status: {e}")
            return False


# Convenience function to get a handler instance
_valve_message_handler = None

def get_valve_message_handler():
    """Get the singleton valve message handler instance"""
    global _valve_message_handler
    if _valve_message_handler is None:
        _valve_message_handler = ValveMessageHandler()
    return _valve_message_handler