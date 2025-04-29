import os
import sys

alt_broker_path = os.path.join(parent_dir, 'MessageBroker')
if os.path.exists(alt_broker_path):
    sys.path.insert(0, alt_broker_path)
    try:
        from MessageBroker.client import MQTTClient
    except ImportError:
        print("Error: Could not import message broker client. Please ensure the MessageBroker module is available.")
        print(f"Tried paths: {parent_dir}, {alt_broker_path}")
        sys.exit(1)