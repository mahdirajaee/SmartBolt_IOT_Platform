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

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

# Load Configuration
config_path = os.path.join(os.path.dirname(__file__), "config.json")
try:
    with open(config_path, "r") as config_file:
        config = json.load(config_file)
except FileNotFoundError:
    print(f"Error: {config_path} not found. Creating default configuration.")
    

# MQTT Configuration
BROKER_ADDRESS = config["broker_address"]
BROKER_PORT = config["broker_port"]

# InfluxDB Configuration
INFLUXDB_URL = config["influxdb_url"]
INFLUXDB_TOKEN = config["influxdb_token"]
INFLUXDB_ORG = config["influxdb_org"]
INFLUXDB_BUCKET = config["influxdb_bucket"]

# MQTT Topics to subscribe
TEMPERATURE_TOPIC = config["temperature_topic"]+"/#"  # Wildcard to capture all pipelines/devices
PRESSURE_TOPIC = config["pressure_topic"]+"/#"
ACTUATOR_STATUS_TOPIC = config["actuator_command_topic"]+"/#"
print ("TEMPERATURE_TOPIC:----->>> ", TEMPERATURE_TOPIC)
print ("PRESSURE_TOPIC:------>>>> ", PRESSURE_TOPIC)
print ("ACTUATOR_STATUS_TOPIC:------>>>> ", ACTUATOR_STATUS_TOPIC)
# Service information for catalog registration
service_info = {
    "service_id": "timeseries_db_connector",
    "service_type": "database_connector",
    "description": "Connects MQTT data to InfluxDB time series database",
    "endpoints": {
        "mqtt": {
            "broker": BROKER_ADDRESS,
            "port": BROKER_PORT,
            "subscribe": [TEMPERATURE_TOPIC, PRESSURE_TOPIC, ACTUATOR_STATUS_TOPIC]
        },
        "rest": {
            "url": f"http://localhost:{config['api_port']}/api",
            "methods": ["GET"]
        }
    },
    "last_update": datetime.datetime.now().isoformat()
}

# InfluxDB Client Setup
influx_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)
query_api = influx_client.query_api()
print(f"Connecting to InfluxDB: {INFLUXDB_URL}, Bucket: {INFLUXDB_BUCKET}")
# Function to register with catalog
def register_with_catalog():
    try:
        response = requests.post(
            config["catalog_url"],
            headers={"Content-Type": "application/json"},
            json=service_info
        )
        if response.status_code == 200:
            print(f"Successfully registered with catalog: {response.json()}")
        else:
            print(f"Failed to register with catalog: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"Error registering with catalog: {e}")

# Function to update status with catalog
def update_status_with_catalog():
    update_url = f"{config['catalog_url']}/{service_info['service_id']}"
    try:
        service_info["last_update"] = datetime.datetime.now().isoformat()
        response = requests.put(
            update_url,
            headers={"Content-Type": "application/json"},
            json=service_info
        )
        if response.status_code == 200:
            print("Updated status with catalog")
        else:
            print(f"Failed to update status: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"Error updating status: {e}")

# MQTT Client Setup
def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker with result code {rc}")
    # Subscribe to all topics
    client.subscribe(TEMPERATURE_TOPIC)
    client.subscribe(PRESSURE_TOPIC)
    client.subscribe(ACTUATOR_STATUS_TOPIC)

def on_message(client, userdata, msg):
    try:
        # Extract pipeline_id and device_id from topic
        # Example topic: sensor/temperature/pipe001/dev010
        topic_parts = msg.topic.split('/')
        measurement_type = topic_parts[0]  # sensor or actuator
        data_type = topic_parts[1]  # temperature, pressure, or valve
        
        # For status topics, we have an extra part
        if len(topic_parts) >= 5 and topic_parts[2] == "status":
            pipeline_id = topic_parts[3]
            device_id = topic_parts[4]
        else:
            pipeline_id = topic_parts[2]
            device_id = topic_parts[3]
        
        # Parse the JSON payload
        data = json.loads(msg.payload.decode())
        
        # Create InfluxDB point
        point = Point(f"{measurement_type}_{data_type}")
        
        # Add tags
        point.tag("pipeline_id", pipeline_id)
        point.tag("device_id", device_id)
        
        # Add fields based on data type
        if data_type in ["temperature", "pressure"]:
            point.field("value", float(data["value"]))
            if "unit" in data:
                point.tag("unit", data["unit"])
        elif data_type == "valve":
            point.field("status", data["status"])
        
        
        # Write to InfluxDB
        write_api.write(bucket=INFLUXDB_BUCKET, record=point)
        print(f"Data written to InfluxDB: {msg.topic} -> {data}")
        
    except json.JSONDecodeError:
        print(f"Error decoding JSON data from {msg.topic}")
    except KeyError as e:
        print(f"Error: Missing key in JSON data from {msg.topic}: {e}")
    except Exception as e:
        print(f"Error writing to InfluxDB: {e}")

mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

# Connect to MQTT broker
try:
    mqtt_client.connect(BROKER_ADDRESS, BROKER_PORT, 60)
    mqtt_client.loop_start()
    print(f"Connected to MQTT broker at {BROKER_ADDRESS}:{BROKER_PORT}")
except Exception as e:
    print(f"Failed to connect to MQTT broker: {e}")
    sys.exit(1)

# Register with catalog at startup
register_with_catalog()

# Start a thread to periodically update status with catalog
def status_update_thread():
    while True:
        update_status_with_catalog()
        time.sleep(60)  # Update every minute

status_thread = threading.Thread(target=status_update_thread)
status_thread.daemon = True
status_thread.start()

# CherryPy REST API for data retrieval
class TimeSeriesAPI:
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self):
        return {"status": "running", "service": "Time Series DB Connector"}
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def data(self, measurement=None, pipeline_id=None, device_id=None, start=None, end=None, limit=100):
        """
        Retrieve data from InfluxDB with filtering options
        """
        try:
            # Build query
            query_parts = []
            
            # Base query
            if measurement:
                measurement_query = f'from(bucket: "{INFLUXDB_BUCKET}") |> range('
            else:
                # If no measurement specified, query all
                measurement_query = f'from(bucket: "{INFLUXDB_BUCKET}") |> range('
            
            # Time range
            if start:
                measurement_query += f'start: {start}'
            else:
                measurement_query += 'start: -1h'  # Default: last hour
                
            if end:
                measurement_query += f', stop: {end}'
                
            measurement_query += ')'
            
            query_parts.append(measurement_query)
            
            # Filter by measurement
            if measurement:
                query_parts.append(f'|> filter(fn: (r) => r._measurement =~ /{measurement}/)')
                
            # Filter by pipeline_id
            if pipeline_id:
                query_parts.append(f'|> filter(fn: (r) => r.pipeline_id == "{pipeline_id}")')
                
            # Filter by device_id
            if device_id:
                query_parts.append(f'|> filter(fn: (r) => r.device_id == "{device_id}")')
                
            # Limit results
            query_parts.append(f'|> limit(n: {int(limit)})')
            
            # Execute query
            query = ' '.join(query_parts)
            result = query_api.query(query=query)
            
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
            
            return {"data": data, "count": len(data)}
            
        except Exception as e:
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def latest(self, measurement=None, pipeline_id=None, device_id=None):
        """
        Get latest values for specified sensors
        """
        try:
            # Build query for latest values
            query_parts = [f'from(bucket: "{INFLUXDB_BUCKET}") |> range(start: -5m)']
            
            # Filter by measurement
            if measurement:
                query_parts.append(f'|> filter(fn: (r) => r._measurement =~ /{measurement}/)')
                
            # Filter by pipeline_id
            if pipeline_id:
                query_parts.append(f'|> filter(fn: (r) => r.pipeline_id == "{pipeline_id}")')
                
            # Filter by device_id
            if device_id:
                query_parts.append(f'|> filter(fn: (r) => r.device_id == "{device_id}")')
                
            # Get latest value for each series
            query_parts.append('|> last()')
            
            # Execute query
            query = ' '.join(query_parts)
            result = query_api.query(query=query)
            
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
            
            return {"data": data, "count": len(data)}
            
        except Exception as e:
            return {"error": str(e)}

# Configure and start CherryPy server
if __name__ == "__main__":
    # CherryPy configuration
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': config['api_port'],
        'engine.autoreload.on': False
    })
    
    # Mount API and start server
    cherrypy.tree.mount(TimeSeriesAPI(), '/api')
    cherrypy.engine.start()
    
    try:
        # Keep main thread running
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
        cherrypy.engine.stop()
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        sys.exit(0)