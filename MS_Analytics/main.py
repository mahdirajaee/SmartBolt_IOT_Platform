import cherrypy
import json
import numpy as np
import paho.mqtt.client as mqtt
import time
import threading
import os
import logging
from influxdb_client import InfluxDBClient, Point, WritePrecision
from ws4py.server.cherrypyserver import WebSocketPlugin, WebSocketTool
from ws4py.websocket import WebSocket

# ================ Configuration ================
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC_SENSOR = os.getenv("MQTT_TOPIC_SENSOR", "/sensor/data")
MQTT_TOPIC_ANALYTICS = os.getenv("MQTT_TOPIC_ANALYTICS", "/analytics/results")
MQTT_TOPIC_ACTUATOR = os.getenv("MQTT_TOPIC_ACTUATOR", "/actuator/valve")

INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "my-secret-token")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "my-org")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "sensor_data")

THRESHOLD_TEMP = float(os.getenv("THRESHOLD_TEMP", 28))  # Celsius
THRESHOLD_PRESSURE = float(os.getenv("THRESHOLD_PRESSURE", 250))  # Pascal
MAX_DATA_POINTS = 100
PROCESS_INTERVAL = int(os.getenv("PROCESS_INTERVAL", 5))

# Initialize InfluxDB Client
influx_client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
write_api = influx_client.write_api(write_options=WritePrecision.NS)

# ================ Logging Setup ================
logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)

def log_event(event_type, details):
    """Log structured events."""
    logging.info(json.dumps({"event": event_type, "details": details}))

# ================ Data Storage ================
sensor_data = {
    "timestamps": [],
    "temperature": [],
    "pressure": [],
}

# ================ Analytics Service ================
class AnalyticsService:
    """Handles post-processing analytics functions."""

    @staticmethod
    def detect_anomalies(values):
        """Detect anomalies using Z-score."""
        if len(values) < 10:
            return []
        arr = np.array(values[-10:])
        mean = np.mean(arr)
        std_dev = np.std(arr)
        return [
            {"index": i, "value": val, "z_score": round(abs((val - mean) / std_dev), 2)}
            for i, val in enumerate(arr) if std_dev and abs((val - mean) / std_dev) > 2
        ]

    @staticmethod
    def rolling_average(values):
        """Compute rolling average of last 10 values."""
        return round(np.mean(values[-10:]), 2) if len(values) >= 10 else None

    @staticmethod
    def classify_severity(count):
        """Classify severity based on threshold violations."""
        return "Critical" if count >= 3 else "Warning"

    @staticmethod
    def energy_recommendation(temp, pressure):
        """Generate energy efficiency recommendations."""
        recommendations = []
        if temp > THRESHOLD_TEMP:
            recommendations.append("Temperature high: Consider adjusting cooling system.")
        else:
            recommendations.append("Temperature optimal.")
        if pressure > THRESHOLD_PRESSURE:
            recommendations.append("Pressure high: Consider opening valve.")
        else:
            recommendations.append("Pressure normal.")
        return " ".join(recommendations)

    @staticmethod
    def calculate_correlation(arr_x, arr_y):
        """Calculate Pearson correlation coefficient between temperature and pressure."""
        if len(arr_x) < 10 or len(arr_y) < 10:
            return None
        return round(np.corrcoef(arr_x[-10:], arr_y[-10:])[0, 1], 2)

    @staticmethod
    def compute_predictions(arr, n_past=10, n_future=5):
        """Predict future values using linear regression."""
        if len(arr) < 2:
            return [arr[-1]] * n_future if arr else [0] * n_future
        x = np.arange(len(arr[-n_past:]))
        y = np.array(arr[-n_past:])
        coeffs = np.polyfit(x, y, 1)
        trend_line = np.poly1d(coeffs)
        return [round(trend_line(i), 2) for i in range(len(arr), len(arr) + n_future)]

# ================ MQTT Handling ================
def on_connect(client, userdata, flags, rc):
    log_event("MQTT Connected", f"Broker: {MQTT_BROKER}")
    client.subscribe(MQTT_TOPIC_SENSOR)

def on_message(client, userdata, msg):
    """Handle incoming sensor data from MQTT."""
    try:
        payload = json.loads(msg.payload.decode())
        timestamp = time.time()
        temperature = float(payload.get("temperature", 0))
        pressure = float(payload.get("pressure", 0))

        threading.Thread(target=store_sensor_data, args=(timestamp, temperature, pressure), daemon=True).start()
    except Exception as e:
        log_event("MQTT Message Error", str(e))

def store_sensor_data(timestamp, temperature, pressure):
    """Store sensor data in memory and InfluxDB."""
    sensor_data["timestamps"].append(timestamp)
    sensor_data["temperature"].append(temperature)
    sensor_data["pressure"].append(pressure)

    # Maintain Data Limit
    if len(sensor_data["temperature"]) > MAX_DATA_POINTS:
        for key in sensor_data:
            sensor_data[key].pop(0)

    # Store in InfluxDB
    point = (
        Point("sensor_readings")
        .field("temperature", temperature)
        .field("pressure", pressure)
        .time(timestamp, WritePrecision.NS)
    )
    write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)

# MQTT Client Setup
mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()

# ================ Processing Data ================
def process_sensor_data():
    """Analyze incoming sensor data and publish results."""
    while True:
        if sensor_data["temperature"] and sensor_data["pressure"]:
            analytics = {
                "anomalies_temp": AnalyticsService.detect_anomalies(sensor_data["temperature"]),
                "anomalies_pressure": AnalyticsService.detect_anomalies(sensor_data["pressure"]),
                "rolling_avg_temp": AnalyticsService.rolling_average(sensor_data["temperature"]),
                "rolling_avg_pressure": AnalyticsService.rolling_average(sensor_data["pressure"]),
                "severity_temp": AnalyticsService.classify_severity(len(sensor_data["temperature"])),
                "severity_pressure": AnalyticsService.classify_severity(len(sensor_data["pressure"])),
                "energy_recommendation": AnalyticsService.energy_recommendation(
                    sensor_data["temperature"][-1], sensor_data["pressure"][-1]
                ),
                "correlation_temp_pressure": AnalyticsService.calculate_correlation(
                    sensor_data["temperature"], sensor_data["pressure"]
                ),
            }

            # Publish Analytics Results
            mqtt_client.publish(MQTT_TOPIC_ANALYTICS, json.dumps(analytics))
            log_event("Analytics Published", analytics)

            # Actuator Control Logic
            if sensor_data["pressure"][-1] > THRESHOLD_PRESSURE:
                mqtt_client.publish(MQTT_TOPIC_ACTUATOR, json.dumps({"action": "open"}))
                log_event("Actuation Triggered", "Valve Open Command Sent")

        time.sleep(PROCESS_INTERVAL)

threading.Thread(target=process_sensor_data, daemon=True).start()

# ================ WebSocket for Real-Time Dashboard ================
class AnalyticsWebSocket(WebSocket):
    def received_message(self, message):
        log_event("WebSocket Message", message)

class WebSocketHandler:
    @cherrypy.expose
    def ws(self):
        cherrypy.request.ws_handler = AnalyticsWebSocket()

WebSocketPlugin(cherrypy.engine).subscribe()

# ================ REST API ================
class AnalyticsAPI:
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def analytics(self):
        """Expose last analytics results via REST API."""
        return sensor_data

cherrypy.config.update({"server.socket_host": "0.0.0.0", "server.socket_port": 8080})
cherrypy.quickstart(WebSocketHandler(), "/ws", config={"/ws": {"tools.websocket.on": True}})
