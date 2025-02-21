import os
from dotenv import load_dotenv
from mqtt_client import create_mqtt_client

# Load environment variables
load_dotenv("config.env")

# By default, let's subscribe to "/sensor/#"
SUBSCRIBE_TOPIC = os.getenv("MQTT_TOPIC_LISTEN_TEST", "/sensor/temperature")
MQTT_Broker = os.getenv("MQTT_BROKER", "localhost")
MQTT_Port = int(os.getenv("MQTT_PORT", "1883"))

def on_message(client, userdata, msg):
    """
    Callback function for when a message is received.
    """
    payload = msg.payload.decode()
    print(f"[SUBSCRIBER] Received message on {msg.topic}: {payload}")
    # Print the message received from the publisher
    print(f"Message from topic {msg.topic}: {payload}")

def start_subscriber():
    """
    Subscribes to the specified topic and waits for messages.
    """
    mqtt_client = create_mqtt_client()
    mqtt_client.on_message = on_message

    # Subscribe to the configured topic (wildcards allowed)
    mqtt_client.subscribe(SUBSCRIBE_TOPIC)
    print(f"[SUBSCRIBER] Subscribed to '{SUBSCRIBE_TOPIC}'")
    print("[SUBSCRIBER] Waiting for messages...")
    #get mesaages
    

    mqtt_client.loop_forever()  # Blocking call

if __name__ == "__main__":
    start_subscriber()
