import cherrypy
import paho.mqtt.client as mqtt
import json
import os
from influxdb import InfluxDBClient

# Load configuration from environment variables
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPICS = [("sensor/temperature", 0), ("sensor/pressure", 0)]

INFLUXDB_HOST = os.getenv("INFLUXDB_HOST", "localhost")
INFLUXDB_PORT = int(os.getenv("INFLUXDB_PORT", 8086))
INFLUXDB_DATABASE = os.getenv("INFLUXDB_DATABASE", "iot_data")

# Initialize InfluxDB client
client = InfluxDBClient(host=INFLUXDB_HOST, port=INFLUXDB_PORT)
client.create_database(INFLUXDB_DATABASE)
client.switch_database(INFLUXDB_DATABASE)

# MQTT Client Setup
mqtt_client = mqtt.Client()

def on_connect(client, userdata, flags, rc):
    print(f"Connected to MQTT broker with result code {rc}")
    for topic in MQTT_TOPICS:
        client.subscribe(topic)

def on_message(client, userdata, msg):
    """Handles incoming MQTT messages and stores them in InfluxDB."""
    try:
        payload = json.loads(msg.payload.decode())
        data_point = [{
            "measurement": "sensor_readings",
            "tags": {"sensor": msg.topic},
            "fields": {"value": float(payload["value"])},
        }]
        client.write_points(data_point)
        print(f"Stored in DB: {msg.topic} -> {payload}")
    except Exception as e:
        print(f"Error processing message: {e}")

mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)

# Start MQTT Loop
mqtt_client.loop_start()

class TimeSeriesAPI:
    """CherryPy REST API to fetch sensor data."""
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def data(self, sensor=None, limit=10):
        """Fetch recent sensor data from InfluxDB."""
        try:
            query = f'SELECT * FROM sensor_readings ORDER BY time DESC LIMIT {limit}'
            if sensor:
                query = f'SELECT * FROM sensor_readings WHERE sensor = \'{sensor}\' ORDER BY time DESC LIMIT {limit}'
            results = client.query(query)
            return list(results.get_points())
        except Exception as e:
            return {"error": str(e)}

# CherryPy Configuration
if __name__ == "__main__":
    cherrypy.config.update({"server.socket_host": "0.0.0.0", "server.socket_port": 5000})
    cherrypy.quickstart(TimeSeriesAPI())
