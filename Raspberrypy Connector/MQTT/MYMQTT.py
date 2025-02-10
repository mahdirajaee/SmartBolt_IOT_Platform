import paho.mqtt.client as mqtt
import json

class MYMQTT:
    def __init__(self, clientID):
        self.clientID = clientID
        self.client = mqtt.Client(clientID)

    def start(self, broker, port):
        self.client.connect(broker, port, 60)
        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()

    def myPublish(self, topic, message):
        self.client.publish(topic, json.dumps(message))

    def mySubscribe(self, topic):
        self.client.subscribe(topic)

    def setCallback(self, callback):
        self.client.on_message = callback
