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


# API settings
API_PORT = 8084

# Storage settings
STORAGE_TYPE = "influxdb"  
SQLITE_DB_FILE = "timeseries_data.db"

# InfluxDB settings (v2.x)
INFLUXDB_HOST = "localhost"
INFLUXDB_PORT = 8086
INFLUXDB_ORG = "IOT_project_Bolt"  # Your organization name
INFLUXDB_TOKEN = "gpy9bH7w4f_l6fSoBp-A5KfJBp4FxNinry2kwkTssSd6x9pQzEEc71wSxwes1GUe4oncxRyGJ1vA6HJfqTmixA=="  # Your API token
INFLUXDB_BUCKET = "smart_bolt_V3"  # The bucket we'll use for all data

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