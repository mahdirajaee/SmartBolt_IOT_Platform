import json
import time
import logging
import threading
import requests
from datetime import datetime
import paho.mqtt.client as mqtt

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("control_center.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ControlCenter")

class ControlCenter:
    def __init__(self, config_file="control_center_config.json"):
        """Initialize the Control Center with configuration from a file."""
        # Load configuration
        self.load_config(config_file)
        
        # Initialize data storage
        self.sensor_data = {}
        self.device_statuses = {}
        
        # Threading lock for thread-safe operations
        self.lock = threading.Lock()
        
        # MQTT client setup
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message
        self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
        
        # Add username/password if provided in config
        if hasattr(self, 'mqtt_username') and hasattr(self, 'mqtt_password'):
            self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)
        
        # Flag to control the main loop
        self.running = False
        
        logger.info("Control Center initialized")

    def load_config(self, config_file):
        """Load configuration from a JSON file."""
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
                
            # Set attributes from config
            for key, value in config.items():
                setattr(self, key, value)
                
            logger.info(f"Configuration loaded from {config_file}")
            
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            # Set default values
            self.catalog_url = "http://localhost:8080"
            self.mqtt_broker = "localhost"
            self.mqtt_port = 1883
            self.mqtt_topics = ["sensors/+/temperature", "sensors/+/pressure"]
            self.control_topic = "actuators/{device_id}/valve"
            self.alert_topic = "alerts/telegram"
            self.check_interval = 5  # seconds
            self.temp_threshold_high = 85.0  # example threshold
            self.pressure_threshold_high = 8.5  # example threshold
            self.update_catalog_interval = 60  # seconds
            
            logger.warning("Using default configuration values")

    def fetch_from_catalog(self):
        """Fetch required information from the Resource/Service Catalog via REST."""
        try:
            # Get MQTT broker information
            response = requests.get(f"{self.catalog_url}/broker")
            if response.status_code == 200:
                broker_info = response.json()
                self.mqtt_broker = broker_info.get("address", self.mqtt_broker)
                self.mqtt_port = broker_info.get("port", self.mqtt_port)
                logger.info(f"Updated MQTT broker: {self.mqtt_broker}:{self.mqtt_port}")
            
            # Get device list and their thresholds
            response = requests.get(f"{self.catalog_url}/devices")
            if response.status_code == 200:
                devices = response.json()
                for device in devices:
                    device_id = device.get("id")
                    if device.get("type") == "sensor":
                        # Store device thresholds
                        if "thresholds" in device:
                            temp_threshold = device["thresholds"].get("temperature", self.temp_threshold_high)
                            pressure_threshold = device["thresholds"].get("pressure", self.pressure_threshold_high)
                            self.device_thresholds = {
                                device_id: {
                                    "temperature": temp_threshold,
                                    "pressure": pressure_threshold
                                }
                            }
                logger.info(f"Updated device information from catalog")
            
            # Get control strategies/rules
            response = requests.get(f"{self.catalog_url}/strategies")
            if response.status_code == 200:
                strategies = response.json()
                self.control_strategies = strategies
                logger.info(f"Updated control strategies from catalog")
                
        except Exception as e:
            logger.error(f"Error fetching from catalog: {e}")

    def connect_mqtt(self):
        """Connect to the MQTT broker and start the network loop."""
        try:
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.mqtt_client.loop_start()
            logger.info(f"Connected to MQTT broker at {self.mqtt_broker}:{self.mqtt_port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False

    def on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback for when the client receives a CONNACK response from the server."""
        if rc == 0:
            logger.info("Connected to MQTT broker")
            # Subscribe to all configured topics
            for topic in self.mqtt_topics:
                client.subscribe(topic)
                logger.info(f"Subscribed to {topic}")
        else:
            logger.error(f"Failed to connect to MQTT broker with code {rc}")

    def on_mqtt_message(self, client, userdata, msg):
        """Callback for when a PUBLISH message is received from the server."""
        try:
            payload = json.loads(msg.payload.decode())
            topic_parts = msg.topic.split('/')
            
            if len(topic_parts) >= 3:
                device_id = topic_parts[1]
                measurement_type = topic_parts[2]  # temperature or pressure
                
                # Store the sensor data
                with self.lock:
                    if device_id not in self.sensor_data:
                        self.sensor_data[device_id] = {}
                    
                    self.sensor_data[device_id][measurement_type] = {
                        "value": payload.get("value"),
                        "timestamp": payload.get("timestamp", datetime.now().isoformat())
                    }
                
                logger.info(f"Received {measurement_type} data from {device_id}: {payload.get('value')}")
                
                # Process the data immediately
                self.process_sensor_data(device_id, measurement_type, payload)
            
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from message: {msg.payload}")
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    def on_mqtt_disconnect(self, client, userdata, rc):
        """Callback for when the client disconnects from the server."""
        if rc != 0:
            logger.warning(f"Unexpected MQTT disconnection with code {rc}. Attempting to reconnect...")
            self.connect_mqtt()

    def process_sensor_data(self, device_id, measurement_type, payload):
        """Process incoming sensor data and apply control logic."""
        try:
            value = payload.get("value")
            
            if value is None:
                logger.warning(f"No value provided in {measurement_type} data from {device_id}")
                return
            
            # Get thresholds for this device
            threshold_high = None
            
            if hasattr(self, 'device_thresholds') and device_id in self.device_thresholds:
                device_threshold = self.device_thresholds[device_id]
                if measurement_type in device_threshold:
                    threshold_high = device_threshold[measurement_type]
            
            # Use default thresholds if no device-specific thresholds are found
            if threshold_high is None:
                if measurement_type == "temperature":
                    threshold_high = self.temp_threshold_high
                elif measurement_type == "pressure":
                    threshold_high = self.pressure_threshold_high
            
            # Apply threshold logic
            if value > threshold_high:
                logger.warning(f"High {measurement_type} alert for {device_id}: {value} > {threshold_high}")
                
                # Send control command to close valve
                self.send_valve_command(device_id, "close")
                
                # Send alert
                self.send_alert(
                    device_id=device_id,
                    alert_type=f"high_{measurement_type}",
                    message=f"High {measurement_type} detected: {value} (threshold: {threshold_high})",
                    value=value,
                    threshold=threshold_high
                )
            
        except Exception as e:
            logger.error(f"Error processing sensor data: {e}")

    def send_valve_command(self, device_id, command):
        """Send a command to control the valve actuator via MQTT."""
        try:
            topic = self.control_topic.format(device_id=device_id)
            payload = {
                "command": command,
                "timestamp": datetime.now().isoformat(),
                "source": "control_center"
            }
            
            result = self.mqtt_client.publish(topic, json.dumps(payload), qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Sent {command} command to valve actuator for device {device_id}")
                return True
            else:
                logger.error(f"Failed to send command to valve actuator: {result.rc}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending valve command: {e}")
            return False

    def send_alert(self, device_id, alert_type, message, value, threshold):
        """Send an alert to the Telegram Bot via MQTT."""
        try:
            payload = {
                "device_id": device_id,
                "alert_type": alert_type,
                "message": message,
                "value": value,
                "threshold": threshold,
                "timestamp": datetime.now().isoformat()
            }
            
            result = self.mqtt_client.publish(self.alert_topic, json.dumps(payload), qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Sent alert for device {device_id}: {message}")
                return True
            else:
                logger.error(f"Failed to send alert: {result.rc}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending alert: {e}")
            return False

    def update_catalog_status(self):
        """Update the Control Center status in the Resource/Service Catalog."""
        try:
            status_data = {
                "id": "control_center",
                "type": "service",
                "status": "active",
                "last_updated": datetime.now().isoformat()
            }
            
            response = requests.put(f"{self.catalog_url}/services/control_center", json=status_data)
            
            if response.status_code in (200, 201):
                logger.info("Updated Control Center status in catalog")
                return True
            else:
                logger.error(f"Failed to update status in catalog: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating catalog status: {e}")
            return False

    def run(self):
        """Main method to run the Control Center."""
        logger.info("Starting Control Center")
        
        # Fetch initial configuration from catalog
        self.fetch_from_catalog()
        
        # Connect to MQTT broker
        if not self.connect_mqtt():
            logger.error("Failed to connect to MQTT broker. Control Center cannot start.")
            return
        
        # Set running flag
        self.running = True
        
        # Track last catalog update time
        last_catalog_update = time.time()
        
        try:
            while self.running:
                # Periodic checks and updates
                current_time = time.time()
                
                # Update catalog status periodically
                if current_time - last_catalog_update >= self.update_catalog_interval:
                    self.update_catalog_status()
                    self.fetch_from_catalog()  # Also refresh our configuration
                    last_catalog_update = current_time
                
                # Sleep for the check interval
                time.sleep(self.check_interval)
                
        except KeyboardInterrupt:
            logger.info("Control Center stopping due to keyboard interrupt")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
        finally:
            # Clean shutdown
            self.running = False
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            logger.info("Control Center stopped")

    def stop(self):
        """Stop the Control Center."""
        self.running = False
        logger.info("Control Center stopping...")


# REST API endpoints for external control
def create_rest_api(control_center):
    """Create a REST API for the Control Center using Flask."""
    from flask import Flask, request, jsonify
    
    app = Flask(__name__)
    
    @app.route('/status', methods=['GET'])
    def get_status():
        """Get the current status of the Control Center."""
        return jsonify({
            "status": "active" if control_center.running else "inactive",
            "sensor_data": control_center.sensor_data,
            "connected_to_mqtt": control_center.mqtt_client.is_connected()
        })
    
    @app.route('/valve/<device_id>', methods=['POST'])
    def control_valve(device_id):
        """Control a valve actuator manually."""
        data = request.json
        command = data.get('command')
        
        if command not in ('open', 'close'):
            return jsonify({"error": "Invalid command. Use 'open' or 'close'"}), 400
        
        success = control_center.send_valve_command(device_id, command)
        
        if success:
            return jsonify({"message": f"Command {command} sent to valve {device_id}"}), 200
        else:
            return jsonify({"error": "Failed to send command"}), 500
    
    @app.route('/thresholds/<device_id>', methods=['GET', 'PUT'])
    def manage_thresholds(device_id):
        """Get or update thresholds for a device."""
        if request.method == 'GET':
            # Return current thresholds for the device
            if hasattr(control_center, 'device_thresholds') and device_id in control_center.device_thresholds:
                return jsonify(control_center.device_thresholds[device_id])
            else:
                return jsonify({
                    "temperature": control_center.temp_threshold_high,
                    "pressure": control_center.pressure_threshold_high
                })
        
        elif request.method == 'PUT':
            # Update thresholds for the device
            data = request.json
            
            if not hasattr(control_center, 'device_thresholds'):
                control_center.device_thresholds = {}
            
            if device_id not in control_center.device_thresholds:
                control_center.device_thresholds[device_id] = {}
            
            if 'temperature' in data:
                control_center.device_thresholds[device_id]['temperature'] = float(data['temperature'])
            
            if 'pressure' in data:
                control_center.device_thresholds[device_id]['pressure'] = float(data['pressure'])
            
            return jsonify({"message": f"Thresholds updated for device {device_id}"}), 200
    
    return app


# Main entry point
if __name__ == "__main__":
    import argparse
    import threading
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='IoT Smart Bolt Control Center')
    parser.add_argument('--config', type=str, default='control_center_config.json',
                        help='Path to configuration file')
    parser.add_argument('--api-port', type=int, default=5000,
                        help='Port for REST API')
    args = parser.parse_args()
    
    # Create and start the Control Center
    control_center = ControlCenter(args.config)
    
    # Create and start the REST API in a separate thread
    app = create_rest_api(control_center)
    threading.Thread(
        target=lambda: app.run(host='0.0.0.0', port=args.api_port, debug=False),
        daemon=True
    ).start()
    
    # Run the Control Center
    try:
        control_center.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        control_center.stop()