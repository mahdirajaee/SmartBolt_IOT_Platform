#!/usr/bin/env python3

import os
import logging

# Service identification
SERVICE_ID = "analytics_service"
SERVICE_NAME = "Analytics and Prediction Service"
SERVICE_DESCRIPTION = "Analyzes sensor data and predicts potential hazards"
SERVICE_TYPE = "analytics"

# Resource Catalog settings
RESOURCE_CATALOG_URL = "http://localhost:8080"
REGISTRATION_INTERVAL = 60  

# API Server settings
API_PORT = 5004  # Added API port configuration

# Time Series DB connection settings
# These will be dynamically fetched from Resource Catalog
TIMESERIES_DB_API_URL = None  # Will be populated from Resource Catalog

# Message Broker settings
# These will be dynamically fetched from Resource Catalog
MQTT_HOST = "localhost"
MQTT_PORT = 1883
MQTT_CLIENT_ID = "analytics_service_client"
MQTT_USERNAME = None
MQTT_PASSWORD = None

# Analytics settings
PREDICTION_INTERVAL_MINUTES = 5
FORECAST_HORIZON_MINUTES = 30
ANALYSIS_FREQUENCY_SECONDS = 60  # How often to run analysis
DATA_HISTORY_HOURS = 24  # How much historical data to use for predictions

# Safety thresholds
TEMPERATURE_MAX_THRESHOLD = 80.0  # degrees Celsius
TEMPERATURE_WARNING_THRESHOLD = 70.0  # degrees Celsius
PRESSURE_MAX_THRESHOLD = 150.0  # PSI
PRESSURE_WARNING_THRESHOLD = 130.0  # PSI

# Alert settings
ALERT_LEVELS = {
    "NORMAL": 0,
    "WARNING": 1,
    "DANGER": 2
}

# Notification endpoints (to be implemented later)
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
DASHBOARD_API_URL = os.environ.get("DASHBOARD_API_URL", "http://localhost:3000/api/alerts")

# Logging settings
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
# Set log file path to be inside ms_analytics folder
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analytics_service.log")
DEBUG_LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "analytics_debug.log")

# Configure logging with detailed format
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

# Create additional debug logger that captures everything
debug_handler = logging.FileHandler(DEBUG_LOG_FILE)
debug_handler.setLevel(logging.DEBUG)
debug_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(funcName)s() - %(message)s')
debug_handler.setFormatter(debug_formatter)

# Create logger
logger = logging.getLogger("analytics_service")
logger.addHandler(debug_handler)