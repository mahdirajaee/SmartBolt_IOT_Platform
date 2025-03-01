{
    "catalog_url": "http://localhost:8080",
    "mqtt_broker": "localhost",
    "mqtt_port": 1883,
    "mqtt_username": "",
    "mqtt_password": "",
    "mqtt_topics": [
        "sensors/+/temperature",
        "sensors/+/pressure"
    ],
    "control_topic": "actuators/{device_id}/valve",
    "alert_topic": "alerts/telegram",
    "check_interval": 5,
    "temp_threshold_high": 85.0,
    "pressure_threshold_high": 8.5,
    "update_catalog_interval": 60
}