#!/usr/bin/env python3

import os
import logging

SERVICE_ID = "control_center"
SERVICE_NAME = "Control Center"
SERVICE_DESCRIPTION = "Process sensor data and control valves based on rules"
SERVICE_TYPE = "control"

RESOURCE_CATALOG_URL = "http://localhost:8080"
REGISTRATION_INTERVAL = 60

API_PORT = 5009

MQTT_HOST = "localhost"
MQTT_PORT = 1883
MQTT_CLIENT_ID = "control_center_client"
MQTT_USERNAME = ""
MQTT_PASSWORD = ""

SENSOR_DATA_TOPIC = "sensor/readings"
VALVE_CONTROL_TOPIC = "valve/control"
VALVE_STATUS_TOPIC = "valve/status"
SYSTEM_EVENTS_TOPIC = "system/events"

TEMPERATURE_THRESHOLD = 75.0
PRESSURE_THRESHOLD = 1050.0

DEFAULT_RULES = [
    {
        "id": "high_temperature",
        "description": "Close valve when temperature exceeds threshold",
        "condition": "temperature > TEMPERATURE_THRESHOLD",
        "action": "close_valve"
    },
    {
        "id": "high_pressure",
        "description": "Close valve when pressure exceeds threshold",
        "condition": "pressure > PRESSURE_THRESHOLD",
        "action": "close_valve"
    }
]

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "control_center.log")