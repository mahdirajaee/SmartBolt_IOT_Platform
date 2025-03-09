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

class TimeSeriesDBConnector:
    def __init__(self, config_file="config.json"):
        # Load configuration
        self.load_config(config_file)
        
        # Configure logging
        self.setup_logging()
        
        # Setup InfluxDB connection
        self.setup_influxdb()
        
        # Setup MQTT client
        self.setup_mqtt()
        
        # Register with catalog
        self.register_with_catalog()
        
        # Start registration refresh thread
        self.start_registration_refresh()
    
    def load_config(self, config_file):
        """Load configuration from file or environment variables"""
        try:
            # Try to load from config file
            with open(config_file, 'r') as f:
                config = json.load(f)
                
                # Service configuration
                service_config = config.get("service", {})
                self.service_id = service_config.get("id", "TimeSeriesDBConnector")
                self.host = service_config.get("host", "localhost")
                self.port = service_config.get("port", 8081)
                
                # Catalog configuration
                catalog_config = config.get("catalog", {})
                self.catalog_url = catalog_config.get("url", "http://localhost:8080")
                
                # InfluxDB configuration
                influxdb_config = config.get("influxdb", {})
                self.influxdb_url = influxdb_config.get("url", "http://localhost:8086")
                self.influxdb_token = influxdb_config.get("token", "")
                self.influxdb_org = influxdb_config.get("org", "organization")
                self.influxdb_bucket = influxdb_config.get("bucket", "bucket")
                
                # MQTT configuration
                mqtt_config = config.get("mqtt", {})
                self.mqtt_broker = mqtt_config.get("broker", "localhost")
                self.mqtt_port = mqtt_config.get("port", 1883)
                self.mqtt_username = mqtt_config.get("username", "")
                self.mqtt_password = mqtt_config.get("password", "")
                self.mqtt_client_id_prefix = mqtt_config.get("client_id_prefix", "TimeSeriesDBConnector")
                self.mqtt_topics = mqtt_config.get("topics", ["/sensor/temperature", "/sensor/pressure"])
                
                # Logging configuration
                logging_config = config.get("logging", {})
                self.log_level = logging_config.get("level", "INFO")
                self.log_format = logging_config.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
                
                # Refresh interval
                self.refresh_interval = config.get("refresh_interval", 60)
                
                print(f"Loaded configuration from {config_file}")
            
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Could not load config file: {str(e)}. Using environment variables.")
            
            # Service configuration
            self.service_id = os.getenv("SERVICE_ID", "TimeSeriesDBConnector")
            self.host = os.getenv("HOST", "localhost")
            self.port = int(os.getenv("PORT", "8081"))
            
            # Catalog configuration
            self.catalog_url = os.getenv("CATALOG_URL", "http://localhost:8080")
            
            # InfluxDB configuration
            self.influxdb_url = os.getenv("INFLUXDB_URL", "http://localhost:8086")
            self.influxdb_token = os.getenv("INFLUXDB_TOKEN", "")
            self.influxdb_org = os.getenv("INFLUXDB_ORG", "organization")
            self.influxdb_bucket = os.getenv("INFLUXDB_BUCKET", "bucket")
            
            # MQTT configuration
            self.mqtt_broker = os.getenv("MQTT_BROKER", "localhost")
            self.mqtt_port = int(os.getenv("MQTT_PORT", "1883"))
            self.mqtt_username = os.getenv("MQTT_USERNAME", "")
            self.mqtt_password = os.getenv("MQTT_PASSWORD", "")
            self.mqtt_client_id_prefix = os.getenv("MQTT_CLIENT_ID_PREFIX", "TimeSeriesDBConnector")
            self.mqtt_topics = ["/sensor/temperature", "/sensor/pressure"]  # Default topics
            
            # Logging configuration
            self.log_level = os.getenv("LOG_LEVEL", "INFO")
            self.log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            
            # Refresh interval
            self.refresh_interval = int(os.getenv("REFRESH_INTERVAL", "60"))
    
    def setup_logging(self):
        """Configure logging based on configuration"""
        log_level = getattr(logging, self.log_level.upper(), logging.INFO)
        logging.basicConfig(level=log_level, format=self.log_format)
        self.logger = logging.getLogger(self.service_id)
        self.logger.info("Logging configured")
    
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
            self.logger.info(f"Connected to InfluxDB at {self.influxdb_url}")
        except Exception as e:
            self.logger.error(f"Error connecting to InfluxDB: {str(e)}")
    
    def setup_mqtt(self):
        """Setup MQTT client and subscription"""
        try:
            client_id = f"{self.mqtt_client_id_prefix}-{int(time.time())}"
            self.mqtt_client = mqtt.Client(client_id=client_id)
            
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
            self.logger.info(f"Connecting to MQTT broker at {self.mqtt_broker}:{self.mqtt_port}")
        except Exception as e:
            self.logger.error(f"Error setting up MQTT: {str(e)}")
    
    def on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        if rc == 0:
            self.logger.info("Connected to MQTT broker")
            # Subscribe to configured topics
            for topic in self.mqtt_topics:
                client.subscribe(topic)
                self.logger.info(f"Subscribed to topic: {topic}")
        else:
            self.logger.error(f"Failed to connect to MQTT broker with code {rc}")
    
    def on_mqtt_disconnect(self, client, userdata, rc):
        """Callback when disconnected from MQTT broker"""
        self.logger.warning(f"Disconnected from MQTT broker with code {rc}")
        # Attempt to reconnect
        if rc != 0:
            self.logger.info("Attempting to reconnect to MQTT broker")
            try:
                client.reconnect()
            except Exception as e:
                self.logger.error(f"Error reconnecting to MQTT broker: {str(e)}")
    
    def on_mqtt_message(self, client, userdata, msg):
        """Callback when message is received from MQTT broker"""
        try:
            topic = msg.topic
            payload = msg.payload.decode("utf-8")
            self.logger.debug(f"Received message on topic {topic}: {payload}")
            
            # Parse the JSON payload
            data = json.loads(payload)
            
            # Store data in InfluxDB
            self.store_sensor_data(topic, data)
        except Exception as e:
            self.logger.error(f"Error processing MQTT message: {str(e)}")
    
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
            self.logger.debug(f"Stored {sensor_type} data in InfluxDB: {data}")
        except Exception as e:
            self.logger.error(f"Error storing data in InfluxDB: {str(e)}")
    
    def register_with_catalog(self):
        """Register this service with the catalog"""
        try:
            service_info = {
                "service_id": self.service_id,
                "service_type": "data-connector",
                "host": self.host,
                "port": self.port,
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
                self.logger.info(f"Registered with catalog: {response.json()}")
            else:
                self.logger.error(f"Failed to register with catalog: {response.status_code} - {response.text}")
        except Exception as e:
            self.logger.error(f"Error registering with catalog: {str(e)}")
    
    def refresh_registration(self):
        """Refresh registration with the catalog periodically"""
        while True:
            try:
                time.sleep(self.refresh_interval)  # Use configured refresh interval
                self.register_with_catalog()
            except Exception as e:
                self.logger.error(f"Error refreshing registration: {str(e)}")
    
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
            self.logger.error(f"Error querying data: {str(e)}")
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
            self.logger.error(f"Error querying latest data: {str(e)}")
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
            self.logger.error(f"Error querying data range: {str(e)}")
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
            self.logger.error(f"Error preparing analytics data: {str(e)}")
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
            self.logger.error(f"Error preparing telegram summary: {str(e)}")
            raise cherrypy.HTTPError(500, f"Error preparing telegram summary: {str(e)}")


def main():
    # Look for config file path in environment variable or use default
    config_file = os.getenv("CONFIG_FILE", "config.json")
    
    # Create and start the server
    connector = TimeSeriesDBConnector(config_file=config_file)
    
    # CherryPy configuration
    conf = {
        '/': {
            'tools.sessions.on': False,
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'application/json')]
        }
    }
    
    cherrypy.tree.mount(connector, '/', conf)
    
    # Update server socket host and port
    cherrypy.config.update({
        'server.socket_host': connector.host,
        'server.socket_port': connector.port
    })
    
    # Start the CherryPy server
    cherrypy.engine.start()
    cherrypy.engine.block()


if __name__ == "__main__":
    main()