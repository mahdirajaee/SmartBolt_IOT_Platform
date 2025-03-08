import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import json
import os
import sys
import cherrypy
import datetime
import time
import threading
import requests
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("timeseries_connector.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("TimeSeriesDBConnector")

# Load configuration - prefer environment variables
config_path = os.path.join(os.path.dirname(__file__), "config.json")
try:
    with open(config_path, "r") as config_file:
        config = json.load(config_file)
        logger.info(f"Loaded configuration from {config_path}")
except FileNotFoundError:
    logger.warning(f"Config file {config_path} not found, using environment variables")
    config = {}

# Configuration with fallbacks
BROKER_ADDRESS = os.getenv("MQTT_BROKER", config.get("broker_address", "localhost"))
BROKER_PORT = int(os.getenv("MQTT_PORT", config.get("broker_port", 1883)))
INFLUXDB_URL = os.getenv("INFLUXDB_URL", config.get("influxdb_url", "http://localhost:8086"))
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", config.get("influxdb_token", "your-token"))
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", config.get("influxdb_org", "IOT_project_Bolt"))
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", config.get("influxdb_bucket", "smart_Bolt"))
CATALOG_URL = os.getenv("CATALOG_URL", config.get("catalog_url", "http://localhost:8080"))
API_PORT = int(os.getenv("API_PORT", config.get("api_port", 5002)))
SERVICE_ID = os.getenv("SERVICE_ID", "timeseries_db_connector")

# MQTT Topics to subscribe
TEMPERATURE_TOPIC = os.getenv("TEMPERATURE_TOPIC", config.get("temperature_topic", "sensor/temperature")) + "/#"
PRESSURE_TOPIC = os.getenv("PRESSURE_TOPIC", config.get("pressure_topic", "sensor/pressure")) + "/#"
ACTUATOR_STATUS_TOPIC = os.getenv("ACTUATOR_TOPIC", config.get("actuator_command_topic", "actuator/valve")) + "/#"

logger.info(f"Subscribing to topics: {TEMPERATURE_TOPIC}, {PRESSURE_TOPIC}, {ACTUATOR_STATUS_TOPIC}")

class TimeSeriesDBConnector:
    def __init__(self):
        # Setup InfluxDB client
        self.influx_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
        self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)
        self.query_api = self.influx_client.query_api()
        
        logger.info(f"Connected to InfluxDB: {INFLUXDB_URL}, Bucket: {INFLUXDB_BUCKET}")
        
        # Setup MQTT client
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message
        self.mqtt_client.on_disconnect = self.on_disconnect
        
        # Service information for catalog registration
        self.service_info = {
            "id": SERVICE_ID,
            "name": "Time Series DB Connector",
            "type": "database_connector",
            "endpoint": f"http://{self.get_host_ip()}:{API_PORT}",
            "description": "Connects MQTT data to InfluxDB time series database",
            "apis": {
                "data": "/api/data",
                "latest": "/api/latest"
            },
            "mqtt_topics": [TEMPERATURE_TOPIC, PRESSURE_TOPIC, ACTUATOR_STATUS_TOPIC],
            "status": "active",
            "last_update": int(time.time())
        }
        
        # Connect to MQTT broker and register with catalog
        self.connect_mqtt()
        self.register_with_catalog()
        
        # Start background thread for catalog updates
        self.start_update_thread()
        
    def get_host_ip(self):
        """Get local IP address"""
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "localhost"
            
    def connect_mqtt(self):
        """Connect to MQTT broker"""
        try:
            # Try to get broker info from catalog first
            broker_info = self.get_broker_info_from_catalog()
            if broker_info:
                broker_address = broker_info.get("address", BROKER_ADDRESS)
                broker_port = broker_info.get("port", BROKER_PORT)
            else:
                broker_address = BROKER_ADDRESS
                broker_port = BROKER_PORT
                
            self.mqtt_client.connect(broker_address, broker_port, 60)
            self.mqtt_client.loop_start()
            logger.info(f"Connected to MQTT broker at {broker_address}:{broker_port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False
            
    def get_broker_info_from_catalog(self):
        """Get broker information from the catalog"""
        try:
            response = requests.get(f"{CATALOG_URL}/broker")
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            logger.error(f"Error getting broker info from catalog: {e}")
            return None
            
    def on_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            logger.info(f"Connected to MQTT broker")
            # Subscribe to all topics
            client.subscribe(TEMPERATURE_TOPIC)
            client.subscribe(PRESSURE_TOPIC)
            client.subscribe(ACTUATOR_STATUS_TOPIC)
            logger.info(f"Subscribed to topics: {TEMPERATURE_TOPIC}, {PRESSURE_TOPIC}, {ACTUATOR_STATUS_TOPIC}")
        else:
            logger.error(f"Failed to connect to MQTT broker with code {rc}")
            
    def on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        if rc != 0:
            logger.warning(f"Unexpected MQTT disconnection. Attempting to reconnect...")
            # Try to reconnect in 5 seconds
            threading.Timer(5.0, self.connect_mqtt).start()
            
    def on_message(self, client, userdata, msg):
        """Callback when a message is received from MQTT broker"""
        try:
            # Extract topic components
            topic_parts = msg.topic.split('/')
            if len(topic_parts) < 3:
                logger.warning(f"Invalid topic format: {msg.topic}")
                return
                
            # Determine measurement type
            if topic_parts[0] == "sensor":
                measurement_type = topic_parts[1]  # temperature or pressure
                pipeline_id = topic_parts[2]
                device_id = topic_parts[3] if len(topic_parts) > 3 else "unknown"
            elif topic_parts[0] == "actuator":
                measurement_type = topic_parts[1]  # valve
                pipeline_id = topic_parts[2]
                device_id = topic_parts[3] if len(topic_parts) > 3 else "unknown"
            else:
                logger.warning(f"Unknown measurement type in topic: {msg.topic}")
                return
                
            # Parse payload
            payload = json.loads(msg.payload.decode())
            
            # Create InfluxDB point
            point = Point(f"{topic_parts[0]}_{topic_parts[1]}")
            
            # Add tags
            point.tag("pipeline_id", pipeline_id)
            point.tag("device_id", device_id)
            
            # Add fields based on measurement type
            if measurement_type in ["temperature", "pressure"]:
                point.field("value", float(payload.get("value", 0)))
                if "unit" in payload:
                    point.tag("unit", payload["unit"])
            elif measurement_type == "valve":
                point.field("status", payload.get("status", "unknown"))
                
            # Add timestamp if available
            if "timestamp" in payload:
                try:
                    timestamp = datetime.datetime.fromisoformat(payload["timestamp"])
                    point.time(timestamp)
                except ValueError:
                    # Use current time if timestamp parsing fails
                    pass
                
            # Write to InfluxDB
            self.write_api.write(bucket=INFLUXDB_BUCKET, record=point)
            logger.info(f"Data written to InfluxDB: {msg.topic} -> {payload}")
            
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from {msg.topic}: {msg.payload}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            
    def register_with_catalog(self):
        """Register this service with the Resource/Service Catalog"""
        try:
            response = requests.post(
                f"{CATALOG_URL}/services",
                json=self.service_info
            )
            if response.status_code in (200, 201):
                logger.info("Successfully registered with catalog")
                return True
            else:
                logger.error(f"Failed to register with catalog: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error registering with catalog: {e}")
            return False
            
    def update_status_with_catalog(self):
        """Update the service status in the catalog"""
        self.service_info["last_update"] = int(time.time())
        try:
            response = requests.put(
                f"{CATALOG_URL}/services/{SERVICE_ID}",
                json=self.service_info
            )
            if response.status_code == 200:
                logger.info("Successfully updated status with catalog")
                return True
            else:
                logger.error(f"Failed to update status with catalog: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error updating status with catalog: {e}")
            return False
            
    def start_update_thread(self):
        """Start a thread to periodically update the catalog"""
        def update_loop():
            while True:
                self.update_status_with_catalog()
                time.sleep(60)  # Update every minute
                
        thread = threading.Thread(target=update_loop)
        thread.daemon = True
        thread.start()
        logger.info("Started catalog update thread")
        
    def query_data(self, measurement=None, pipeline_id=None, device_id=None, start=None, end=None, limit=100):
        """Query data from InfluxDB"""
        try:
            # Build query parts
            query_parts = []
            
            # Base query with time range
            if start:
                time_range = f'start: {start}'
            else:
                time_range = 'start: -1h'  # Default to last hour
                
            if end:
                time_range += f', stop: {end}'
                
            query_parts.append(f'from(bucket: "{INFLUXDB_BUCKET}") |> range({time_range})')
            
            # Filter by measurement
            if measurement:
                query_parts.append(f'|> filter(fn: (r) => r._measurement =~ /{measurement}/)')
                
            # Filter by pipeline_id
            if pipeline_id:
                query_parts.append(f'|> filter(fn: (r) => r.pipeline_id == "{pipeline_id}")')
                
            # Filter by device_id
            if device_id:
                query_parts.append(f'|> filter(fn: (r) => r.device_id == "{device_id}")')
                
            # Sort by time descending to get newest first
            query_parts.append('|> sort(columns: ["_time"], desc: true)')
                
            # Limit results
            query_parts.append(f'|> limit(n: {int(limit)})')
            
            # Execute query
            query = ' '.join(query_parts)
            logger.debug(f"Executing query: {query}")
            result = self.query_api.query(query=query)
            
            # Process results
            data = []
            for table in result:
                for record in table.records:
                    data.append({
                        "measurement": record.get_measurement(),
                        "pipeline_id": record.values.get("pipeline_id", ""),
                        "device_id": record.values.get("device_id", ""),
                        "field": record.get_field(),
                        "value": record.get_value(),
                        "time": record.get_time().isoformat()
                    })
                    
            return data
        except Exception as e:
            logger.error(f"Error querying data: {e}")
            return []
            
    def get_latest_data(self, measurement=None, pipeline_id=None, device_id=None):
        """Get latest values for each device/measurement combination"""
        try:
            # Query last 5 minutes of data
            data = self.query_data(
                measurement=measurement,
                pipeline_id=pipeline_id,
                device_id=device_id,
                start="-5m"
            )
            
            # Get latest value for each measurement/device combination
            latest_data = {}
            for item in data:
                key = f"{item['measurement']}_{item['pipeline_id']}_{item['device_id']}"
                if key not in latest_data or item['time'] > latest_data[key]['time']:
                    latest_data[key] = item
                    
            return list(latest_data.values())
        except Exception as e:
            logger.error(f"Error getting latest data: {e}")
            return []

# CherryPy REST API
class TimeSeriesAPI:
    def __init__(self, connector):
        self.connector = connector
        
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self):
        """Root endpoint returning service info"""
        return {
            "service": "Time Series DB Connector",
            "version": "1.0",
            "status": "running",
            "endpoints": {
                "data": "/api/data",
                "latest": "/api/latest"
            }
        }
        
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def data(self, measurement=None, pipeline_id=None, device_id=None, start=None, end=None, limit=100):
        """Endpoint to query time series data"""
        try:
            data = self.connector.query_data(
                measurement=measurement,
                pipeline_id=pipeline_id,
                device_id=device_id,
                start=start,
                end=end,
                limit=int(limit)
            )
            return {"data": data, "count": len(data)}
        except Exception as e:
            cherrypy.response.status = 500
            return {"error": str(e)}
            
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def latest(self, measurement=None, pipeline_id=None, device_id=None):
        """Endpoint to get latest values"""
        try:
            data = self.connector.get_latest_data(
                measurement=measurement,
                pipeline_id=pipeline_id,
                device_id=device_id
            )
            return {"data": data, "count": len(data)}
        except Exception as e:
            cherrypy.response.status = 500
            return {"error": str(e)}

# Main entry point
def main():
    # Create connector
    connector = TimeSeriesDBConnector()
    
    # Configure CherryPy
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': API_PORT,
        'log.access_file': 'access.log',
        'log.error_file': 'error.log'
    })
    
    # Mount the API
    cherrypy.tree.mount(TimeSeriesAPI(connector), '/api', {
        '/': {
            'tools.sessions.on': True,
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'application/json')]
        }
    })
    
    # Start CherryPy server
    cherrypy.engine.start()
    cherrypy.engine.block()

if __name__ == "__main__":
    main()