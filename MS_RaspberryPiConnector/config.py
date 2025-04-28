SIMULATION_INTERVAL = 1
RANDOM_VARIATION = True

TEMP_BASE_VALUE = 25.0
TEMP_VARIATION = 2.0
TEMP_MIN = 0.0
TEMP_MAX = 100.0

PRESSURE_BASE_VALUE = 1013.25
PRESSURE_VARIATION = 10.0
PRESSURE_MIN = 900.0
PRESSURE_MAX = 1100.0

SERVER_URL = "http://localhost:5000/api/sensor-data"
API_KEY = "your_api_key_here"
USE_MQTT = True

MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "sensor/readings"
MQTT_CLIENT_ID = "raspberrypi_simulator"
MQTT_USERNAME = ""
MQTT_PASSWORD = ""

# New message broker config for valve control
VALVE_CONTROL_ENABLED = True
VALVE_CONTROL_TOPIC = "valve/control"
VALVE_STATUS_TOPIC = "valve/status"

LOGGING_ENABLED = True
LOG_LEVEL = "INFO"
LOG_FILE = "sensor_simulator.log"

# Resource Catalog Configuration
RESOURCE_CATALOG_URL = "http://localhost:8080"
DEVICE_ID = "raspberry_pi_connector"
DEVICE_NAME = "Raspberry Pi Connector"
DEVICE_DESCRIPTION = "Smart Bolt Raspberry Pi connector for sensor data collection and transmission"
DEVICE_TYPE = "connector"
REGISTRATION_INTERVAL = 60  # Seconds between re-registration attempts (heartbeat)