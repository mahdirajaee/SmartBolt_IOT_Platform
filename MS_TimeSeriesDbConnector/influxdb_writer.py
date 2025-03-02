import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
import json

# Load Configuration from config.json
try:
    with open("config.json", "r") as config_file:
        config = json.load(config_file)
except FileNotFoundError:
    print("Error: config.json not found.")
    exit(1)

# MQTT Broker Configuration
BROKER_ADDRESS = config["broker_address"]
BROKER_PORT = config["broker_port"]

# InfluxDB Configuration
INFLUXDB_URL = config["influxdb_url"]
INFLUXDB_TOKEN = config["influxdb_token"]
INFLUXDB_ORG = config["influxdb_org"]
INFLUXDB_BUCKET = config["influxdb_bucket"]

# MQTT Topic
INFLUXDB_TOPIC = config["influxdb_topic"]

# InfluxDB Client Setup
client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
write_api = client.write_api(write_precision=WritePrecision.NS, write_options=SYNCHRONOUS)

# MQTT Client Setup
def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT broker with result code " + str(rc))
    client.subscribe(INFLUXDB_TOPIC)

def on_message(client, userdata, msg):
    if msg.topic == INFLUXDB_TOPIC:
        try:
            data = json.loads(msg.payload.decode())
            temperature = data["temperature"]
            pressure = data["pressure"]

            point = Point("sensor_readings").field("temperature", temperature).field("pressure", pressure)
            write_api.write(bucket=INFLUXDB_BUCKET, record=point)
            print("Data written to InfluxDB")

        except json.JSONDecodeError:
            print("Error decoding JSON data")
        except KeyError:
            print("Error: Missing keys in JSON data")
        except Exception as e:
            print(f"Error writing to InfluxDB: {e}")

mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

mqtt_client.connect(BROKER_ADDRESS, BROKER_PORT, 60)
mqtt_client.loop_start()

try:
    while True:
        pass
except KeyboardInterrupt:
    print("Exiting InfluxDB writer...")
    mqtt_client.loop_stop()
    mqtt_client.disconnect()