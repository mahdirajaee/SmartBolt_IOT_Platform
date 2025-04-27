"""
Time Series Database Connector Configuration
"""

# Message Broker settings
MQTT_HOST = "localhost"
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60
MQTT_CLIENT_ID = "timeseries_db_connector"
MQTT_USERNAME = ""
MQTT_PASSWORD = ""

# Topics to subscribe to
SENSOR_DATA_TOPIC = "sensor/readings"
VALVE_STATUS_TOPIC = "valve/status"
SYSTEM_EVENTS_TOPIC = "system/events"

# Storage settings
STORAGE_TYPE = "influxdb"  
SQLITE_DB_FILE = "timeseries_data.db"

# InfluxDB settings (v2.x)
INFLUXDB_HOST = "localhost"
INFLUXDB_PORT = 8086
INFLUXDB_ORG = "INFLUXDB_TOKEN"  # Your organization name
INFLUXDB_TOKEN = "AQFaXwV-179yDwbMBzALoYdnwVK5fUqhhJGb6Dikey1Wu6c9tBf51cKjRy_uJOurrpJ5xTdPSebqx4R0FI5bWA=="  # Your API token
INFLUXDB_BUCKET = "smart_bolt_v1"  # The bucket we'll use for all data

# TimescaleDB settings (if used)
TIMESCALEDB_HOST = "localhost"
TIMESCALEDB_PORT = 5432
TIMESCALEDB_USER = "postgres"
TIMESCALEDB_PASSWORD = "password"
TIMESCALEDB_DATABASE = "smartbolt"

# Resource Catalog Configuration
RESOURCE_CATALOG_URL = "http://localhost:8080"
SERVICE_ID = "timeseries_db_connector"
SERVICE_NAME = "Time Series DB Connector"
SERVICE_DESCRIPTION = "Stores sensor data and valve states in a time series database"
SERVICE_TYPE = "data_storage"
REGISTRATION_INTERVAL = 60  # Seconds between re-registration attempts (heartbeat)

# Logging settings
LOGGING_ENABLED = True
LOG_LEVEL = "INFO"
LOG_FILE = "timeseries_db_connector.log"