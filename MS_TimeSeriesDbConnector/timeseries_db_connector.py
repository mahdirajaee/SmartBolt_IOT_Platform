import cherrypy
import paho.mqtt.client as mqtt
import json
import time
import requests
import os
import threading
import logging
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("TimeSeriesDBConnector")

class TimeSeriesDBConnector:
    def __init__(self):
        self.service_id = "TimeSeriesDBConnector"
        self.catalog_url = os.getenv("CATALOG_URL", "http://localhost:8080")
        
        # Get configuration from catalog
        self.load_config_from_catalog()
        
        # Setup InfluxDB connection
        self.setup_influxdb()
        
        # Setup MQTT client
        self.setup_mqtt()
        
        # Register with catalog
        self.register_with_catalog()
        
        # Start registration refresh thread
        self.start_registration_refresh()
    
    def load_config_from_catalog(self):
        """Load configuration from the catalog"""
        try:
            response = requests.get(f"{self.catalog_url}/services")
            if response.status_code == 200:
                services = response.json()
                
                # Find InfluxDB config
                for service in services:
                    if service.get("service_id") == "InfluxDB":
                        self.influxdb_url = service.get("url", "http://localhost:8086")
                        self.influxdb_token = service.get("token", "")
                        self.influxdb_org = service.get("org", "organization")
                        self.influxdb_bucket = service.get("bucket", "bucket")
                
                # Find MQTT broker config
                for service in services:
                    if service.get("service_id") == "MessageBroker":
                        self.mqtt_broker = service.get("host", "localhost")
                        self.mqtt_port = service.get("port", 1883)
                        self.mqtt_username = service.get("username", "")
                        self.mqtt_password = service.get("password", "")
                
                logger.info("Configuration loaded from catalog")
            else:
                logger.error(f"Failed to get config from catalog: {response.status_code}")
                # Use default values
                self.setup_default_config()
        except Exception as e:
            logger.error(f"Error loading config from catalog: {str(e)}")
            # Use default values
            self.setup_default_config()
    
    def setup_default_config(self):
        """Setup default configuration if catalog is unavailable"""
        # Default InfluxDB configuration
        self.influxdb_url = os.getenv("INFLUXDB_URL", "http://localhost:8086")
        self.influxdb_token = os.getenv("INFLUXDB_TOKEN", "")
        self.influxdb_org = os.getenv("INFLUXDB_ORG", "organization")
        self.influxdb_bucket = os.getenv("INFLUXDB_BUCKET", "bucket")
        
        # Default MQTT configuration
        self.mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
        self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
        self.mqtt_username = os.getenv("MQTT_USERNAME", "")
        self.mqtt_password = os.getenv("MQTT_PASSWORD", "")
        
        logger.info("Using default configuration")
    
    def setup_influxdb(self):
        """Setup InfluxDB client"""
        try:
            self.influxdb_client = InfluxDBClient(
                url=self.influxdb_url,
                token=self.influxdb_token,
                org=self.influxdb_org
            )
            self.write_api = self.influxdb_client.write_api(write_options=SYNCHRONOUS)
            self.query_api = self.influxdb_client.query_api()
            logger.info(f"Connected to InfluxDB at {self.influxdb_url}")
        except Exception as e:
            logger.error(f"Error connecting to InfluxDB: {str(e)}")
    
    def setup_mqtt(self):
        """Setup MQTT client and subscription"""
        try:
            self.mqtt_client = mqtt.Client(client_id=f"TimeSeriesDBConnector-{int(time.time())}")
            
            # Set username and password if provided
            if self.mqtt_username and self.mqtt_password:
                self.mqtt_client.username_pw_set(self.mqtt_username, self.mqtt_password)
            
            # Set callbacks
            self.mqtt_client.on_connect = self.on_mqtt_connect
            self.mqtt_client.on_message = self.on_mqtt_message
            self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
            
            # Connect to broker
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
            
            # Start the loop in a non-blocking way
            self.mqtt_client.loop_start()
            logger.info(f"Connected to MQTT broker at {self.mqtt_broker}:{self.mqtt_port}")
        except Exception as e:
            logger.error(f"Error setting up MQTT: {str(e)}")
    
    def on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            logger.info("Connected to MQTT broker")
            # Subscribe to sensor topics
            client.subscribe("/sensor/temperature")
            client.subscribe("/sensor/pressure")
            logger.info("Subscribed to sensor topics")
        else:
            logger.error(f"Failed to connect to MQTT broker with code {rc}")
    
    def on_mqtt_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        logger.warning(f"Disconnected from MQTT broker with code {rc}")
        # Attempt to reconnect
        if rc != 0:
            logger.info("Attempting to reconnect to MQTT broker")
            try:
                client.reconnect()
            except Exception as e:
                logger.error(f"Error reconnecting to MQTT broker: {str(e)}")
    
    def on_mqtt_message(self, client, userdata, msg):
        """Callback when message is received from MQTT broker"""
        try:
            topic = msg.topic
            payload = msg.payload.decode("utf-8")
            logger.debug(f"Received message on topic {topic}: {payload}")
            
            # Parse the JSON payload
            data = json.loads(payload)
            
            # Store data in InfluxDB
            self.store_sensor_data(topic, data)
        except Exception as e:
            logger.error(f"Error processing MQTT message: {str(e)}")
    
    def store_sensor_data(self, topic, data):
        """Store sensor data in InfluxDB"""
        try:
            # Extract sensor type from topic
            sensor_type = topic.split("/")[-1]  # Get 'temperature' or 'pressure'
            
            # Create a Point
            point = Point(sensor_type)
            
            # Add tags for filtering
            point = point.tag("pipeline_id", data.get("pipeline_id", "unknown"))
            point = point.tag("device_id", data.get("device_id", "unknown"))
            
            # Add value
            point = point.field("value", float(data.get("value", 0)))
            
            # Add timestamp if provided, otherwise use current time
            timestamp = data.get("timestamp")
            if timestamp:
                point = point.time(datetime.fromtimestamp(timestamp))
            
            # Write to InfluxDB
            self.write_api.write(bucket=self.influxdb_bucket, record=point)
            logger.debug(f"Stored {sensor_type} data in InfluxDB: {data}")
        except Exception as e:
            logger.error(f"Error storing data in InfluxDB: {str(e)}")
    
    def register_with_catalog(self):
        """Register this service with the catalog"""
        try:
            # Get host and port from environment or use defaults
            host = os.getenv("HOST", "localhost")
            port = int(os.getenv("PORT", "8081"))
            
            service_info = {
                "service_id": self.service_id,
                "service_type": "data-connector",
                "host": host,
                "port": port,
                "protocol": "http",
                "endpoints": [
                    {"path": "/data", "method": "GET", "description": "Get sensor data"},
                    {"path": "/data/latest", "method": "GET", "description": "Get latest sensor data"},
                    {"path": "/data/range", "method": "GET", "description": "Get sensor data in time range"},
                    {"path": "/analytics/data", "method": "GET", "description": "Get data for analytics"},
                    {"path": "/telegram/summary", "method": "GET", "description": "Get summary for telegram bot"}
                ],
                "timestamp": int(time.time())
            }
            
            response = requests.post(f"{self.catalog_url}/services/register", json=service_info)
            if response.status_code == 200 or response.status_code == 201:
                logger.info(f"Registered with catalog: {response.json()}")
            else:
                logger.error(f"Failed to register with catalog: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"Error registering with catalog: {str(e)}")
    
    def refresh_registration(self):
        """Refresh registration with the catalog periodically"""
        while True:
            try:
                time.sleep(60)  # Refresh every 60 seconds
                self.register_with_catalog()
            except Exception as e:
                logger.error(f"Error refreshing registration: {str(e)}")
    
    def start_registration_refresh(self):
        """Start a thread for refreshing registration"""
        refresh_thread = threading.Thread(target=self.refresh_registration)
        refresh_thread.daemon = True
        refresh_thread.start()
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self):
        """Root endpoint providing service info"""
        return {
            "service": self.service_id,
            "status": "running",
            "endpoints": [
                "/data", 
                "/data/latest", 
                "/data/range",
                "/analytics/data",
                "/telegram/summary"
            ]
        }
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def data(self, sensor_type=None, pipeline_id=None, device_id=None, limit=100):
        """
        Get sensor data with optional filtering
        Example: /data?sensor_type=temperature&pipeline_id=001&device_id=dev010&limit=50
        """
        try:
            # Build Flux query
            fluxquery = f'from(bucket: "{self.influxdb_bucket}")'
            
            # Filter by measurement (sensor_type)
            if sensor_type:
                fluxquery += f' |> filter(fn: (r) => r._measurement == "{sensor_type}")'
            
            # Filter by pipeline_id
            if pipeline_id:
                fluxquery += f' |> filter(fn: (r) => r.pipeline_id == "{pipeline_id}")'
            
            # Filter by device_id
            if device_id:
                fluxquery += f' |> filter(fn: (r) => r.device_id == "{device_id}")'
            
            # Add time range (last 24 hours by default)
            fluxquery += ' |> range(start: -24h)'
            
            # Limit results
            fluxquery += f' |> limit(n: {int(limit)})'
            
            # Execute query
            result = self.query_api.query(org=self.influxdb_org, query=fluxquery)
            
            # Convert result to a list of dictionaries
            data = []
            for table in result:
                for record in table.records:
                    data.append({
                        "time": record.get_time().isoformat(),
                        "measurement": record.get_measurement(),
                        "value": record.get_value(),
                        "pipeline_id": record.values.get("pipeline_id"),
                        "device_id": record.values.get("device_id")
                    })
            
            return {"data": data, "count": len(data)}
        except Exception as e:
            logger.error(f"Error querying data: {str(e)}")
            raise cherrypy.HTTPError(500, f"Error querying data: {str(e)}")
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def data_latest(self, sensor_type=None, pipeline_id=None, device_id=None):
        """
        Get latest sensor data with optional filtering
        Example: /data/latest?sensor_type=temperature&pipeline_id=001&device_id=dev010
        """
        try:
            # Build Flux query
            fluxquery = f'from(bucket: "{self.influxdb_bucket}")'
            
            # Filter by measurement (sensor_type)
            if sensor_type:
                fluxquery += f' |> filter(fn: (r) => r._measurement == "{sensor_type}")'
            
            # Filter by pipeline_id
            if pipeline_id:
                fluxquery += f' |> filter(fn: (r) => r.pipeline_id == "{pipeline_id}")'
            
            # Filter by device_id
            if device_id:
                fluxquery += f' |> filter(fn: (r) => r.device_id == "{device_id}")'
            
            # Add time range (last hour to be safe)
            fluxquery += ' |> range(start: -1h)'
            
            # Get latest points
            fluxquery += ' |> last()'
            
            # Execute query
            result = self.query_api.query(org=self.influxdb_org, query=fluxquery)
            
            # Convert result to a list of dictionaries
            data = []
            for table in result:
                for record in table.records:
                    data.append({
                        "time": record.get_time().isoformat(),
                        "measurement": record.get_measurement(),
                        "value": record.get_value(),
                        "pipeline_id": record.values.get("pipeline_id"),
                        "device_id": record.values.get("device_id")
                    })
            
            return {"data": data, "count": len(data)}
        except Exception as e:
            logger.error(f"Error querying latest data: {str(e)}")
            raise cherrypy.HTTPError(500, f"Error querying latest data: {str(e)}")
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def data_range(self, sensor_type=None, pipeline_id=None, device_id=None, 
                  start="-24h", end="now()", aggregation=None, window=None):
        """
        Get sensor data in a specific time range with optional aggregation
        Example: /data/range?sensor_type=temperature&pipeline_id=001&start=-7d&aggregation=mean&window=1h
        """
        try:
            # Build Flux query
            fluxquery = f'from(bucket: "{self.influxdb_bucket}")'
            
            # Filter by measurement (sensor_type)
            if sensor_type:
                fluxquery += f' |> filter(fn: (r) => r._measurement == "{sensor_type}")'
            
            # Filter by pipeline_id
            if pipeline_id:
                fluxquery += f' |> filter(fn: (r) => r.pipeline_id == "{pipeline_id}")'
            
            # Filter by device_id
            if device_id:
                fluxquery += f' |> filter(fn: (r) => r.device_id == "{device_id}")'
            
            # Add time range
            fluxquery += f' |> range(start: {start}, stop: {end})'
            
            # Add aggregation if specified
            if aggregation and window:
                fluxquery += f' |> aggregateWindow(every: {window}, fn: {aggregation}, createEmpty: false)'
            
            # Execute query
            result = self.query_api.query(org=self.influxdb_org, query=fluxquery)
            
            # Convert result to a list of dictionaries
            data = []
            for table in result:
                for record in table.records:
                    data.append({
                        "time": record.get_time().isoformat(),
                        "measurement": record.get_measurement(),
                        "value": record.get_value(),
                        "pipeline_id": record.values.get("pipeline_id"),
                        "device_id": record.values.get("device_id")
                    })
            
            return {"data": data, "count": len(data)}
        except Exception as e:
            logger.error(f"Error querying data range: {str(e)}")
            raise cherrypy.HTTPError(500, f"Error querying data range: {str(e)}")
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def analytics_data(self, sensor_type=None, pipeline_id=None, start="-7d", end="now()"):
        """
        Get data specifically formatted for analytics microservice
        Example: /analytics/data?sensor_type=temperature&pipeline_id=001&start=-30d
        """
        try:
            # Build Flux query with more data for analytics
            fluxquery = f'from(bucket: "{self.influxdb_bucket}")'
            
            # Filter by measurement (sensor_type)
            if sensor_type:
                fluxquery += f' |> filter(fn: (r) => r._measurement == "{sensor_type}")'
            
            # Filter by pipeline_id
            if pipeline_id:
                fluxquery += f' |> filter(fn: (r) => r.pipeline_id == "{pipeline_id}")'
            
            # Add time range (more historical data for analytics)
            fluxquery += f' |> range(start: {start}, stop: {end})'
            
            # Sort by time
            fluxquery += ' |> sort(columns: ["_time"])'
            
            # Execute query
            result = self.query_api.query(org=self.influxdb_org, query=fluxquery)
            
            # Convert result to a list of dictionaries organized by device_id
            data_by_device = {}
            
            for table in result:
                for record in table.records:
                    device_id = record.values.get("device_id", "unknown")
                    
                    if device_id not in data_by_device:
                        data_by_device[device_id] = []
                    
                    data_by_device[device_id].append({
                        "time": record.get_time().isoformat(),
                        "value": record.get_value(),
                        "pipeline_id": record.values.get("pipeline_id")
                    })
            
            return {
                "data": data_by_device, 
                "sensor_type": sensor_type,
                "pipeline_id": pipeline_id,
                "time_range": {"start": start, "end": end}
            }
        except Exception as e:
            logger.error(f"Error preparing analytics data: {str(e)}")
            raise cherrypy.HTTPError(500, f"Error preparing analytics data: {str(e)}")
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def telegram_summary(self, pipeline_id=None):
        """
        Get a simplified summary for the Telegram bot
        Example: /telegram/summary?pipeline_id=001
        """
        try:
            summaries = []
            
            # Get the latest temperature readings
            temp_query = f'from(bucket: "{self.influxdb_bucket}") |> filter(fn: (r) => r._measurement == "temperature")'
            
            if pipeline_id:
                temp_query += f' |> filter(fn: (r) => r.pipeline_id == "{pipeline_id}")'
            
            temp_query += ' |> range(start: -1h) |> last() |> group(columns: ["device_id"])'
            
            temp_result = self.query_api.query(org=self.influxdb_org, query=temp_query)
            
            # Get the latest pressure readings
            pressure_query = f'from(bucket: "{self.influxdb_bucket}") |> filter(fn: (r) => r._measurement == "pressure")'
            
            if pipeline_id:
                pressure_query += f' |> filter(fn: (r) => r.pipeline_id == "{pipeline_id}")'
            
            pressure_query += ' |> range(start: -1h) |> last() |> group(columns: ["device_id"])'
            
            pressure_result = self.query_api.query(org=self.influxdb_org, query=pressure_query)
            
            # Process temperature results
            temp_data = {}
            for table in temp_result:
                for record in table.records:
                    device_id = record.values.get("device_id", "unknown")
                    pipeline_id = record.values.get("pipeline_id", "unknown")
                    temp_data[(pipeline_id, device_id)] = {
                        "temperature": record.get_value(),
                        "time": record.get_time().isoformat()
                    }
            
            # Process pressure results and combine with temperature
            for table in pressure_result:
                for record in table.records:
                    device_id = record.values.get("device_id", "unknown")
                    pipeline_id = record.values.get("pipeline_id", "unknown")
                    
                    if (pipeline_id, device_id) in temp_data:
                        # Add pressure to existing record
                        summary = {
                            "pipeline_id": pipeline_id,
                            "device_id": device_id,
                            "temperature": temp_data[(pipeline_id, device_id)]["temperature"],
                            "pressure": record.get_value(),
                            "time": record.get_time().isoformat()
                        }
                        summaries.append(summary)
                    else:
                        # Just pressure data available
                        summary = {
                            "pipeline_id": pipeline_id,
                            "device_id": device_id,
                            "pressure": record.get_value(),
                            "time": record.get_time().isoformat()
                        }
                        summaries.append(summary)
            
            # Add any temperature-only devices
            for (pid, did), data in temp_data.items():
                if not any(s["pipeline_id"] == pid and s["device_id"] == did for s in summaries):
                    summary = {
                        "pipeline_id": pid,
                        "device_id": did,
                        "temperature": data["temperature"],
                        "time": data["time"]
                    }
                    summaries.append(summary)
            
            return {"summaries": summaries, "count": len(summaries)}
        except Exception as e:
            logger.error(f"Error preparing telegram summary: {str(e)}")
            raise cherrypy.HTTPError(500, f"Error preparing telegram summary: {str(e)}")


def main():
    # Get port from environment or use default
    port = int(os.getenv("PORT", "8081"))
    
    # CherryPy configuration
    conf = {
        '/': {
            'tools.sessions.on': False,
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'application/json')]
        }
    }
    
    # Create and start the server
    connector = TimeSeriesDBConnector()
    cherrypy.tree.mount(connector, '/', conf)
    
    # Update server socket host and port
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': port
    })
    
    # Start the CherryPy server
    cherrypy.engine.start()
    cherrypy.engine.block()


if __name__ == "__main__":
    main()