import json
import time
import logging
import threading
import requests
import cherrypy
import paho.mqtt.client as mqtt
from datetime import datetime

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
    def __init__(self, config_file="config.py"):
        self.load_config(config_file)
        self.sensor_data = {}
        self.device_statuses = {}
        self.lock = threading.Lock()
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message
        self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
        if hasattr(self, 'mqtt_username') and hasattr(self, 'mqtt_password'):
            self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)
        self.running = False
        logger.info("Control Center initialized")

    def load_config(self, config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            for key, value in config.items():
                setattr(self, key, value)
            logger.info(f"Configuration loaded from {config_file}")
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            self.catalog_url = "http://localhost:8080"
            self.mqtt_broker = "localhost"
            self.mqtt_port = 1883
            self.mqtt_topics = ["sensors/+/temperature", "sensors/+/pressure"]
            self.control_topic = "actuators/{device_id}/valve"
            self.alert_topic = "alerts/telegram"
            self.check_interval = 5
            self.temp_threshold_high = 85.0
            self.pressure_threshold_high = 8.5
            self.update_catalog_interval = 60
            logger.warning("Using default configuration values")

    def fetch_from_catalog(self):
        try:
            response = requests.get(f"{self.catalog_url}/broker")
            if response.status_code == 200:
                broker_info = response.json()
                self.mqtt_broker = broker_info.get("address", self.mqtt_broker)
                self.mqtt_port = broker_info.get("port", self.mqtt_port)
                logger.info(f"Updated MQTT broker: {self.mqtt_broker}:{self.mqtt_port}")
            response = requests.get(f"{self.catalog_url}/devices")
            if response.status_code == 200:
                devices = response.json()
                for device in devices:
                    device_id = device.get("id")
                    if device.get("type") == "sensor":
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
            response = requests.get(f"{self.catalog_url}/strategies")
            if response.status_code == 200:
                strategies = response.json()
                self.control_strategies = strategies
                logger.info(f"Updated control strategies from catalog")
        except Exception as e:
            logger.error(f"Error fetching from catalog: {e}")

    def connect_mqtt(self):
        try:
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.mqtt_client.loop_start()
            logger.info(f"Connected to MQTT broker at {self.mqtt_broker}:{self.mqtt_port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False

    def on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("Connected to MQTT broker")
            for topic in self.mqtt_topics:
                client.subscribe(topic)
                logger.info(f"Subscribed to {topic}")
        else:
            logger.error(f"Failed to connect to MQTT broker with code {rc}")

    def on_mqtt_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            topic_parts = msg.topic.split('/')
            if len(topic_parts) >= 3:
                device_id = topic_parts[1]
                measurement_type = topic_parts[2]
                with self.lock:
                    if device_id not in self.sensor_data:
                        self.sensor_data[device_id] = {}
                    self.sensor_data[device_id][measurement_type] = {
                        "value": payload.get("value"),
                        "timestamp": payload.get("timestamp", datetime.now().isoformat())
                    }
                logger.info(f"Received {measurement_type} data from {device_id}: {payload.get('value')}")
                self.process_sensor_data(device_id, measurement_type, payload)
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from message: {msg.payload}")
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    def on_mqtt_disconnect(self, client, userdata, rc):
        if rc != 0:
            logger.warning(f"Unexpected MQTT disconnection with code {rc}. Attempting to reconnect...")
            self.connect_mqtt()

    def process_sensor_data(self, device_id, measurement_type, payload):
        try:
            value = payload.get("value")
            if value is None:
                logger.warning(f"No value provided in {measurement_type} data from {device_id}")
                return
            threshold_high = None
            if hasattr(self, 'device_thresholds') and device_id in self.device_thresholds:
                device_threshold = self.device_thresholds[device_id]
                if measurement_type in device_threshold:
                    threshold_high = device_threshold[measurement_type]
            if threshold_high is None:
                if measurement_type == "temperature":
                    threshold_high = self.temp_threshold_high
                elif measurement_type == "pressure":
                    threshold_high = self.pressure_threshold_high
            if value > threshold_high:
                logger.warning(f"High {measurement_type} alert for {device_id}: {value} > {threshold_high}")
                self.send_valve_command(device_id, "close")
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

    def background_operations(self):
        logger.info("Starting background operations thread")
        self.fetch_from_catalog()
        if not self.connect_mqtt():
            logger.error("Failed to connect to MQTT broker. Control Center cannot operate properly.")
            return
        last_catalog_update = time.time()
        try:
            while self.running:
                current_time = time.time()
                if current_time - last_catalog_update >= self.update_catalog_interval:
                    self.update_catalog_status()
                    self.fetch_from_catalog()
                    last_catalog_update = current_time
                time.sleep(self.check_interval)
        except Exception as e:
            logger.error(f"Error in background operations: {e}")
        finally:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
            logger.info("Background operations thread stopped")

    def start(self):
        if not self.running:
            self.running = True
            self.bg_thread = threading.Thread(target=self.background_operations, daemon=True)
            self.bg_thread.start()
            logger.info("Control Center started")
            return True
        else:
            logger.warning("Control Center is already running")
            return False

    def stop(self):
        if self.running:
            self.running = False
            logger.info("Control Center stopping...")
            if hasattr(self, 'bg_thread') and self.bg_thread.is_alive():
                self.bg_thread.join(timeout=5.0)
            return True
        else:
            logger.warning("Control Center is not running")
            return False

class ControlCenterAPI:
    def __init__(self, control_center):
        self.control_center = control_center

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self):
        return {
            "service": "Control Center",
            "status": "active" if self.control_center.running else "inactive",
            "version": "1.0"
        }

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def status(self):
        return {
            "status": "active" if self.control_center.running else "inactive",
            "sensor_data": self.control_center.sensor_data,
            "connected_to_mqtt": self.control_center.mqtt_client.is_connected() if hasattr(self.control_center, 'mqtt_client') else False
        }

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def valve(self, device_id=None):
        if not device_id:
            raise cherrypy.HTTPError(400, "Device ID is required")
        if cherrypy.request.method == 'POST':
            data = cherrypy.request.json
            command = data.get('command')
            if command not in ('open', 'close'):
                raise cherrypy.HTTPError(400, "Invalid command. Use 'open' or 'close'")
            success = self.control_center.send_valve_command(device_id, command)
            if success:
                return {"message": f"Command {command} sent to valve {device_id}"}
            else:
                raise cherrypy.HTTPError(500, "Failed to send command")
        else:
            raise cherrypy.HTTPError(405, "Method not allowed")

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def thresholds(self, device_id=None):
        if not device_id:
            raise cherrypy.HTTPError(400, "Device ID is required")
        if cherrypy.request.method == 'GET':
            if hasattr(self.control_center, 'device_thresholds') and device_id in self.control_center.device_thresholds:
                return self.control_center.device_thresholds[device_id]
            else:
                return {
                    "temperature": self.control_center.temp_threshold_high,
                    "pressure": self.control_center.pressure_threshold_high
                }
        elif cherrypy.request.method == 'PUT':
            data = cherrypy.request.json
            if not hasattr(self.control_center, 'device_thresholds'):
                self.control_center.device_thresholds = {}
            if device_id not in self.control_center.device_thresholds:
                self.control_center.device_thresholds[device_id] = {}
            if 'temperature' in data:
                self.control_center.device_thresholds[device_id]['temperature'] = float(data['temperature'])
            if 'pressure' in data:
                self.control_center.device_thresholds[device_id]['pressure'] = float(data['pressure'])
            return {"message": f"Thresholds updated for device {device_id}"}
        else:
            raise cherrypy.HTTPError(405, "Method not allowed")

def start_control_center(config_file="config.py", api_port=8081):
    control_center = ControlCenter(config_file)
    control_center.start()
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': api_port,
        'engine.autoreload.on': False,
        'log.screen': True,
        'log.access_file': 'access.log',
        'log.error_file': 'error.log'
    })
    api = ControlCenterAPI(control_center)
    conf = {
        '/': {
            'tools.sessions.on': True,
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'application/json')],
        }
    }
    cherrypy.tree.mount(api, '/api', conf)
    cherrypy.engine.start()
    def cleanup():
        control_center.stop()
        cherrypy.engine.exit()
    cherrypy.engine.subscribe('stop', cleanup)
    cherrypy.engine.block()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='IoT Smart Bolt Control Center')
    parser.add_argument('--config', type=str, default='config.py',
                        help='Path to configuration file')
    parser.add_argument('--api-port', type=int, default=8081,
                        help='Port for REST API')
    args = parser.parse_args()
    start_control_center(args.config, args.api_port)