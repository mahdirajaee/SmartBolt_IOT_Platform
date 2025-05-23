MQTT_HOST = "localhost"
MQTT_PORT = 1883
MQTT_KEEPALIVE = 60
MQTT_CLIENT_ID = "smart_bolt_message_broker"
MQTT_USERNAME = ""
MQTT_PASSWORD = ""

VALVE_CONTROL_TOPIC = "valve/control"
VALVE_STATUS_TOPIC = "valve/status"
SENSOR_DATA_TOPIC = "sensor/readings"
SYSTEM_EVENTS_TOPIC = "system/events"

WEBSOCKET_ENABLED = True
WEBSOCKET_PORT = 9001

PERSISTENCE_ENABLED = False

TLS_ENABLED = False
TLS_CERT_FILE = "server.crt"
TLS_KEY_FILE = "server.key"

LOG_LEVEL = "INFO"
LOG_FILE = "message_broker.log"

WEB_INTERFACE_ENABLED = True
WEB_INTERFACE_PORT = 8081