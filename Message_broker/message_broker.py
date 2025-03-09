#!/usr/bin/env python3
"""
Smart IoT Bolt Message Broker

This script implements the message broker component for the Smart IoT Bolt system.
It facilitates communication between various microservices using the MQTT protocol.

The broker handles:
- Sensor data from Raspberry Pi Connectors (temperature and pressure)
- Control commands to valve actuators
- Data distribution to the Time Series DB Connector and Control Center
"""

import json
import logging
import os
import signal
import sys
import time
from typing import Dict, Any

import paho.mqtt.client as mqtt

class MessageBroker:
    """
    MessageBroker class implements a wrapper around the MQTT client to facilitate
    message exchange between IoT components.
    """
    def __init__(self, config_path: str = 'config.json'):
        """
        Initialize the MessageBroker with configuration from a JSON file.
        
        Args:
            config_path (str): Path to the configuration file
        """
        self.config = self._load_config(config_path)
        self._setup_logging()
        self.logger.info("MessageBroker initializing...")
        
        # Initialize MQTT client
        self.client = mqtt.Client(
            client_id=self.config['broker']['client_id'],
            clean_session=True
        )
        
        # Set up callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self.client.on_publish = self._on_publish
        self.client.on_subscribe = self._on_subscribe
        
        # Set up security if configured
        if self.config['security']['username'] and self.config['security']['password']:
            self.client.username_pw_set(
                self.config['security']['username'],
                self.config['security']['password']
            )
        
        if self.config['security']['enable_tls']:
            if self.config['security']['cert_file'] and self.config['security']['key_file']:
                self.client.tls_set(
                    self.config['security']['cert_file'],
                    self.config['security']['key_file']
                )
        
        # Set up message routing table
        self.routes = {}
        
        # Flag to indicate if the broker is running
        self.running = False
        
        # Setup graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """
        Load configuration from a JSON file.
        
        Args:
            config_path (str): Path to the configuration file
            
        Returns:
            Dict[str, Any]: Configuration dictionary
        """
        try:
            with open(config_path, 'r') as config_file:
                return json.load(config_file)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            print(f"Error loading configuration: {str(e)}")
            sys.exit(1)
    
    def _setup_logging(self) -> None:
        """Set up logging based on configuration."""
        log_config = self.config['logging']
        logging.basicConfig(
            level=getattr(logging, log_config['level']),
            format=log_config['format'],
            handlers=[
                logging.FileHandler(log_config['file']),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("MessageBroker")
    
    def _on_connect(self, client, userdata, flags, rc) -> None:
        """
        Callback for when the client connects to the broker.
        
        Args:
            client: The client instance
            userdata: User data defined in Client initialization
            flags: Response flags sent by the broker
            rc: The connection result
        """
        if rc == 0:
            self.logger.info("Connected to MQTT Broker!")
            
            # Subscribe to all relevant topics
            qos = self.config['qos']['subscribe']
            for category in self.config['topics']:
                for topic_name, topic_path in self.config['topics'][category].items():
                    self.client.subscribe(topic_path, qos)
                    self.logger.info(f"Subscribed to topic: {topic_path}")
        else:
            connection_results = {
                1: "Connection refused - incorrect protocol version",
                2: "Connection refused - invalid client identifier",
                3: "Connection refused - server unavailable",
                4: "Connection refused - bad username or password",
                5: "Connection refused - not authorized"
            }
            error_msg = connection_results.get(rc, f"Unknown error code: {rc}")
            self.logger.error(f"Failed to connect: {error_msg}")
    
    def _on_message(self, client, userdata, msg) -> None:
        """
        Callback for when a message is received from the broker.
        
        Args:
            client: The client instance
            userdata: User data defined in Client initialization
            msg: The message received
        """
        topic = msg.topic
        payload = msg.payload.decode('utf-8')
        self.logger.debug(f"Message received on topic '{topic}': {payload}")
        
        # Message routing logic
        try:
            # For debugging and monitoring purposes
            # In a real implementation, you would add specific routing logic here
            # Log the message for now
            self.logger.info(f"[ROUTING] {topic} -> {payload}")
        except Exception as e:
            self.logger.error(f"Error processing message: {str(e)}")
    
    def _on_disconnect(self, client, userdata, rc) -> None:
        """
        Callback for when the client disconnects from the broker.
        
        Args:
            client: The client instance
            userdata: User data defined in Client initialization
            rc: The disconnection result
        """
        if rc != 0:
            self.logger.warning("Unexpected disconnection.")
        else:
            self.logger.info("Disconnected from broker.")
    
    def _on_publish(self, client, userdata, mid) -> None:
        """
        Callback for when a message is published.
        
        Args:
            client: The client instance
            userdata: User data defined in Client initialization
            mid: Message ID
        """
        self.logger.debug(f"Message published with ID: {mid}")
    
    def _on_subscribe(self, client, userdata, mid, granted_qos) -> None:
        """
        Callback for when a subscription is confirmed.
        
        Args:
            client: The client instance
            userdata: User data defined in Client initialization
            mid: Message ID
            granted_qos: Granted QoS level
        """
        self.logger.debug(f"Subscription confirmed. ID: {mid}, QoS: {granted_qos}")
    
    def _signal_handler(self, signum, frame) -> None:
        """
        Handle termination signals gracefully.
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)
    
    def start(self) -> None:
        """Start the message broker."""
        if self.running:
            self.logger.warning("Message broker is already running.")
            return
        
        try:
            # Connect to the MQTT broker
            self.client.connect(
                self.config['broker']['host'],
                self.config['broker']['port'],
                self.config['broker']['keepalive']
            )
            
            # Start the loop
            self.client.loop_start()
            self.running = True
            self.logger.info("Message broker started successfully.")
            
            # Keep the script running
            while self.running:
                time.sleep(1)
                
        except Exception as e:
            self.logger.error(f"Error starting message broker: {str(e)}")
            self.stop()
    
    def stop(self) -> None:
        """Stop the message broker."""
        if not self.running:
            return
        
        self.running = False
        self.client.loop_stop()
        self.client.disconnect()
        self.logger.info("Message broker stopped.")
    
    def publish_message(self, topic: str, payload: str, qos: int = None) -> None:
        """
        Publish a message to a topic.
        
        Args:
            topic (str): The topic to publish to
            payload (str): The message payload
            qos (int, optional): Quality of Service level. Defaults to config value.
        """
        if qos is None:
            qos = self.config['qos']['publish']
            
        try:
            result = self.client.publish(topic, payload, qos)
            if result.rc != mqtt.MQTT_ERR_SUCCESS:
                self.logger.error(f"Failed to publish message to {topic}: {mqtt.error_string(result.rc)}")
            else:
                self.logger.debug(f"Published message to {topic}: {payload}")
        except Exception as e:
            self.logger.error(f"Error publishing message: {str(e)}")


def main():
    """Main entry point for the message broker."""
    # Use environment variable for config path if provided
    config_path = os.environ.get('BROKER_CONFIG_PATH', 'config.json')
    
    broker = MessageBroker(config_path)
    try:
        broker.start()
    except KeyboardInterrupt:
        broker.stop()


if __name__ == "__main__":
    main()