import paho.mqtt.client as mqtt

# Define the MQTT settings
BROKER = 'localhost'
PORT = 1883
KEEP_ALIVE_INTERVAL = 60
TOPIC = 'test/topic'

# Define the callback functions
def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    client.subscribe(TOPIC)

def on_message(client, userdata, msg):
    print(f"Message received: {msg.payload.decode()} on topic {msg.topic}")

def on_disconnect(client, userdata, rc):
    print("Disconnected from broker")

# Create an MQTT client instance
client = mqtt.Client()

# Assign the callback functions
client.on_connect = on_connect
client.on_message = on_message
client.on_disconnect = on_disconnect

# Connect to the broker
client.connect(BROKER, PORT, KEEP_ALIVE_INTERVAL)

# Start the loop
client.loop_forever()