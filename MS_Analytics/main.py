import cherrypy
import json
import numpy as np
import paho.mqtt.client as mqtt
import time
import threading
import os

# MQTT Configuration
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC_SENSOR = "/sensor/data"
MQTT_TOPIC_ANALYTICS = "/analytics/results"

# Sensor Data Storage
sensor_data = {
    "timestamps": [],
    "temperature": [],
    "pressure": [],
}

# Threshold Values
THRESHOLD_TEMP = 28  # Celsius
THRESHOLD_PRESSURE = 250  # Pascal
MAX_DATA_POINTS = 100  # Limit data stored


class AnalyticsService:
    """Handles post-processing analytics functions."""

    @staticmethod
    def detect_anomalies(values):
        """Detect anomalies using Z-score (outliers)."""
        if len(values) < 10:
            return []

        arr = np.array(values[-10:])
        mean = np.mean(arr)
        std_dev = np.std(arr)

        anomalies = []
        for i, val in enumerate(arr):
            z_score = abs((val - mean) / std_dev) if std_dev else 0
            if z_score > 2:
                anomalies.append({"index": i, "value": val, "z_score": round(z_score, 2)})

        return anomalies

    @staticmethod
    def rolling_average(values):
        """Compute rolling average of last 10 values."""
        if len(values) < 10:
            return None
        return round(np.mean(values[-10:]), 2)

    @staticmethod
    def classify_severity(count):
        """Classify severity based on threshold violations."""
        return "Critical" if count >= 3 else "Warning"

    @staticmethod
    def energy_recommendation(temp, pressure):
        """Generate energy efficiency recommendations."""
        recommendation = []
        if temp > THRESHOLD_TEMP:
            recommendation.append("Temperature high: Consider adjusting cooling system.")
        else:
            recommendation.append("Temperature optimal.")

        if pressure > THRESHOLD_PRESSURE:
            recommendation.append("Pressure high: Consider opening valve.")
        else:
            recommendation.append("Pressure normal.")

        return " ".join(recommendation)

    @staticmethod
    def calculate_correlation(arr_x, arr_y):
        """Calculate Pearson correlation coefficient between temperature and pressure."""
        if len(arr_x) < 10 or len(arr_y) < 10:
            return None

        corr = np.corrcoef(arr_x[-10:], arr_y[-10:])[0, 1]
        return round(corr, 2)

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


def process_sensor_data():
    """Analyze incoming sensor data and publish results."""
    global sensor_data

    while True:
        if len(sensor_data["temperature"]) > 0 and len(sensor_data["pressure"]) > 0:
            analytics = {}

            # Extract latest values
            latest_temp = sensor_data["temperature"][-1]
            latest_pressure = sensor_data["pressure"][-1]

            # Perform analytics
            analytics["anomalies_temp"] = AnalyticsService.detect_anomalies(sensor_data["temperature"])
            analytics["anomalies_pressure"] = AnalyticsService.detect_anomalies(sensor_data["pressure"])
            analytics["rolling_avg_temp"] = AnalyticsService.rolling_average(sensor_data["temperature"])
            analytics["rolling_avg_pressure"] = AnalyticsService.rolling_average(sensor_data["pressure"])
            analytics["severity_temp"] = AnalyticsService.classify_severity(len(analytics["anomalies_temp"]))
            analytics["severity_pressure"] = AnalyticsService.classify_severity(len(analytics["anomalies_pressure"]))
            analytics["energy_recommendation"] = AnalyticsService.energy_recommendation(latest_temp, latest_pressure)
            analytics["correlation_temp_pressure"] = AnalyticsService.calculate_correlation(
                sensor_data["temperature"], sensor_data["pressure"]
            )
            analytics["temperature_forecast"] = AnalyticsService.compute_predictions(sensor_data["temperature"])
            analytics["pressure_forecast"] = AnalyticsService.compute_predictions(sensor_data["pressure"])

            # Publish analytics to MQTT
            mqtt_client.publish(MQTT_TOPIC_ANALYTICS, json.dumps(analytics))

            print("Published analytics:", analytics)

        time.sleep(5)  # Process every 5 seconds


# MQTT Callbacks
def on_connect(client, userdata, flags, rc):
    print("Connected to MQTT Broker:", MQTT_BROKER)
    client.subscribe(MQTT_TOPIC_SENSOR)


def on_message(client, userdata, msg):
    """Handle incoming sensor data from MQTT."""
    global sensor_data

    try:
        payload = json.loads(msg.payload.decode())
        timestamp = time.time()
        temperature = float(payload.get("temperature", 0))
        pressure = float(payload.get("pressure", 0))

        # Store latest sensor values
        sensor_data["timestamps"].append(timestamp)
        sensor_data["temperature"].append(temperature)
        sensor_data["pressure"].append(pressure)

        # Maintain data limit
        if len(sensor_data["temperature"]) > MAX_DATA_POINTS:
            for key in sensor_data:
                sensor_data[key].pop(0)

        print(f"Received Data: Temp={temperature}°C, Pressure={pressure}Pa")

    except Exception as e:
        print("Error processing MQTT message:", e)


# MQTT Client Setup
mqtt_client = mqtt.Client()
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message
mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
mqtt_client.loop_start()


# REST API for retrieving analytics data
class AnalyticsAPI:
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def analytics(self):
        """Expose last analytics results via REST API."""
        return {
            "last_temperature": sensor_data["temperature"][-1] if sensor_data["temperature"] else None,
            "last_pressure": sensor_data["pressure"][-1] if sensor_data["pressure"] else None,
            "anomalies_temp": AnalyticsService.detect_anomalies(sensor_data["temperature"]),
            "anomalies_pressure": AnalyticsService.detect_anomalies(sensor_data["pressure"]),
            "rolling_avg_temp": AnalyticsService.rolling_average(sensor_data["temperature"]),
            "rolling_avg_pressure": AnalyticsService.rolling_average(sensor_data["pressure"]),
            "severity_temp": AnalyticsService.classify_severity(len(sensor_data["temperature"])),
            "severity_pressure": AnalyticsService.classify_severity(len(sensor_data["pressure"])),
            "correlation_temp_pressure": AnalyticsService.calculate_correlation(
                sensor_data["temperature"], sensor_data["pressure"]
            ),
        }


# Start analytics processing thread
threading.Thread(target=process_sensor_data, daemon=True).start()

# Start CherryPy REST API
if __name__ == "__main__":
    cherrypy.config.update({"server.socket_host": "0.0.0.0", "server.socket_port": 8080})
    cherrypy.quickstart(AnalyticsAPI(), "/")
