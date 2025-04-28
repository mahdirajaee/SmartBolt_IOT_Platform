#!/usr/bin/env python3

import json
import logging
import signal
import sys
import threading
import time
from datetime import datetime

import config
from storage import get_storage
from registration import start_registration, update_status
from api import TimeSeriesAPI

# Add messagebroker directory to the path so we can import the client module
import os
import sys
broker_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'messagebroker'))
sys.path.insert(0, broker_path)

try:
    from messagebroker.client import MQTTClient
except ImportError:
    # Fall back to direct import if the module structure is different
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    try:
        from messagebroker.client import MQTTClient
    except ImportError:
        print("Error: Could not import message broker client. Please ensure the messagebroker module is available.")
        sys.exit(1)

# Set up logging
if config.LOGGING_ENABLED:
    logging.basicConfig(
        filename=config.LOG_FILE,
        level=getattr(logging, config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
else:
    logging.basicConfig(level=logging.WARNING)

logger = logging.getLogger('timeseries_connector')

# Add console handler to display logs in terminal
console = logging.StreamHandler()
console.setLevel(getattr(logging, config.LOG_LEVEL))
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)

class TimeSeriesConnector:
    """Connector between Message Broker and Time Series Database"""
    
    def __init__(self):
        self.storage = get_storage()
        self.mqtt_client = None
        self.running = False
        self.connected_to_broker = False
        self.connection_retry_count = 0
        self.max_connection_retries = 5
        self.connection_retry_interval = 5  # seconds
        
    def connect_to_broker(self):
        """Connect to the MQTT message broker"""
        try:
            client_id = f"timeseries_connector_{int(time.time())}"
            self.mqtt_client = MQTTClient(client_id=client_id)
            
            logger.info(f"Connecting to message broker at {config.MQTT_HOST}:{config.MQTT_PORT}")
            success = self.mqtt_client.connect(host=config.MQTT_HOST, port=config.MQTT_PORT)
            
            if success:
                self.mqtt_client.start()
                self.connected_to_broker = True
                self.connection_retry_count = 0
                logger.info("Connected to message broker")
                return True
            else:
                logger.error(f"Failed to connect to message broker at {config.MQTT_HOST}:{config.MQTT_PORT}")
                return False
                
        except Exception as e:
            logger.error(f"Error connecting to message broker: {e}")
            return False
    
    def subscribe_to_topics(self):
        """Subscribe to the relevant MQTT topics"""
        if not self.connected_to_broker:
            logger.error("Cannot subscribe: not connected to message broker")
            return False
            
        try:
            # Subscribe to sensor readings topic
            self.mqtt_client.subscribe(
                config.SENSOR_DATA_TOPIC, 
                qos=1,
                callback=self.process_sensor_data
            )
            logger.info(f"Subscribed to sensor data topic: {config.SENSOR_DATA_TOPIC}")
            
            # Subscribe to valve status topic
            self.mqtt_client.subscribe(
                config.VALVE_STATUS_TOPIC, 
                qos=1,
                callback=self.process_valve_status
            )
            logger.info(f"Subscribed to valve status topic: {config.VALVE_STATUS_TOPIC}")
            
            # Subscribe to system events for monitoring
            self.mqtt_client.subscribe(
                config.SYSTEM_EVENTS_TOPIC,
                qos=0,
                callback=self.process_system_event
            )
            logger.info(f"Subscribed to system events topic: {config.SYSTEM_EVENTS_TOPIC}")
            
            return True
        except Exception as e:
            logger.error(f"Error subscribing to topics: {e}")
            return False
    
    def process_sensor_data(self, topic, payload, qos):
        """Process sensor data received from the message broker"""
        try:
            # Convert payload from bytes to string if necessary
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8')
                
            # Parse the JSON message
            data = json.loads(payload)
            logger.debug(f"Received sensor data: {data}")
            
            timestamp = data.get('timestamp', datetime.now().isoformat())
            device_id = data.get('device_id', 'unknown')
            readings = data.get('readings', {})
            # Create metadata from the message
            metadata = {
                "topic": topic,
                "qos": qos
            }
            
            # Add any device info or sector info to metadata
            if 'device_info' in data:
                metadata['device_info'] = data['device_info']
            if 'sector_info' in data:
                metadata['sector_info'] = data['sector_info']
            
            # Process each sensor reading
            for sensor_type, reading in readings.items():
                if isinstance(reading, dict):
                    value = reading.get('value')
                    unit = reading.get('unit')
                else:
                    value = reading
                    unit = None
                
                # Store in time series database
                if value is not None:
                    success = self.storage.store_sensor_data(
                        timestamp=timestamp,
                        device_id=device_id,
                        sensor_type=sensor_type,
                        value=float(value),
                        unit=unit,
                        metadata=metadata
                    )
                    
                    if success:
                        logger.debug(f"Stored {sensor_type} reading: {value}{' '+unit if unit else ''} for device {device_id}")
                    else:
                        logger.warning(f"Failed to store {sensor_type} reading for device {device_id}")
            
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in sensor data message: {payload}")
        except Exception as e:
            logger.error(f"Error processing sensor data: {e}")
    
    def process_valve_status(self, topic, payload, qos):
        """Process valve status updates received from the message broker"""
        try:
            # Convert payload from bytes to string if necessary
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8')
                
            # Parse the JSON message
            data = json.loads(payload)
            logger.debug(f"Received valve status: {data}")
            
            timestamp = data.get('timestamp', datetime.now().isoformat())
            sector_id = data.get('sector_id')
            valve_state = data.get('state')
            if not sector_id or not valve_state:
                logger.warning("Missing sector_id or valve_state in valve status message")
                return
            
            # Create metadata from the message
            metadata = {
                "topic": topic,
                "qos": qos,
                "last_action": data.get('last_action')
            }
            
            # Store in time series database
            success = self.storage.store_valve_state(
                timestamp=timestamp,
                sector_id=sector_id,
                state=valve_state,
                metadata=metadata
            )
            
            if success:
                logger.debug(f"Stored valve state: {valve_state} for sector {sector_id}")
            else:
                logger.warning(f"Failed to store valve state for sector {sector_id}")
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in valve status message: {payload}")
        except Exception as e:
            logger.error(f"Error processing valve status: {e}")
    
    def process_system_event(self, topic, payload, qos):
        """Process system events from the message broker"""
        try:
            # Convert payload from bytes to string if necessary
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8')
                
            # Parse the JSON message
            data = json.loads(payload)
            event = data.get('event')
            
            logger.debug(f"Received system event: {event}")
            
            # Here we could handle specific system events if needed
            # For now, we just log them
            
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in system event message: {payload}")
        except Exception as e:
            logger.error(f"Error processing system event: {e}")
    
    def start(self):
        """Start the connector"""
        if self.running:
            logger.warning("Connector is already running")
            return False
        
        logger.info("Starting Time Series DB Connector")
        
        # Connect to the message broker
        if not self.connect_to_broker():
            # Try to reconnect a few times before giving up
            while (self.connection_retry_count < self.max_connection_retries):
                self.connection_retry_count += 1
                logger.info(f"Retrying connection to broker ({self.connection_retry_count}/{self.max_connection_retries})...")
                time.sleep(self.connection_retry_interval)
                if self.connect_to_broker():
                    break
            
            if not self.connected_to_broker:
                logger.error(f"Failed to connect to broker after {self.max_connection_retries} attempts")
                return False
        
        # Subscribe to topics
        if not self.subscribe_to_topics():
            logger.error("Failed to subscribe to topics")
            self.mqtt_client.stop()
            return False
        
        # Set running state
        self.running = True
        logger.info("Time Series DB Connector started successfully")
        
        return True
    
    def stop(self):
        """Stop the connector"""
        if not self.running:
            return False
        
        logger.info("Stopping Time Series DB Connector")
        
        # Disconnect from the broker
        if self.mqtt_client:
            self.mqtt_client.stop()
        
        # Close database connections
        if self.storage:
            self.storage.close()
        
        self.running = False
        self.connected_to_broker = False
        logger.info("Time Series DB Connector stopped")
        
        return True


# Global connector instance for signal handling
connector = None

def start_api_server(host='0.0.0.0', port=8000):
    """Start the API server in a separate thread"""
    import cherrypy
    
    # Global configuration for CherryPy
    cherrypy.config.update({
        'server.socket_host': host,
        'server.socket_port': port,
        'engine.autoreload.on': False,
        'log.screen': True
    })
    
    # Application specific configuration
    conf = {
        '/': {
            'tools.sessions.on': False,
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'application/json')],
            'tools.encode.on': True,
            'tools.encode.encoding': 'utf-8'
        }
    }
    
    # Mount the API
    cherrypy.tree.mount(TimeSeriesAPI(), '/', conf)
    
    # Start the server
    cherrypy.engine.start()
    logger.info(f"API server started on http://{host}:{port}")
    
    return cherrypy.engine

def signal_handler(sig, frame):
    """Handle termination signals"""
    logger.info(f"Received signal {sig}, shutting down...")
    
    # Update status to offline
    update_status("offline")
    
    # Stop the connector
    if connector:
        connector.stop()
    
    # Stop the API server if it's running
    try:
        import cherrypy
        if cherrypy.engine.state == cherrypy.engine.states.STARTED:
            cherrypy.engine.exit()
            logger.info("API server stopped")
    except:
        pass
        
    sys.exit(0)

def main():
    global connector
    
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Time Series DB Connector')
    parser.add_argument('--api-only', action='store_true', help='Run only the API server without the message broker connector')
    parser.add_argument('--connector-only', action='store_true', help='Run only the message broker connector without the API server')
    parser.add_argument('--api-port', type=int, default=8000, help='Port for the API server')
    args = parser.parse_args()
    
    # Print startup message
    print("╔════════════════════════════════════════╗")
    print("║  Smart Bolt - Time Series DB Connector ║")
    print("╚════════════════════════════════════════╝")
    print(f"Starting service...")
    
    # Check if we're using InfluxDB and it's properly set up
    if config.STORAGE_TYPE.lower() == "influxdb":
        try:
            # Use InfluxDB v2.x client
            from influxdb_client import InfluxDBClient
            client = InfluxDBClient(
                url=f"http://{config.INFLUXDB_HOST}:{config.INFLUXDB_PORT}",
                token=config.INFLUXDB_TOKEN,
                org=config.INFLUXDB_ORG
            )
            
            # Check if the client can connect
            health = client.health()
            if health and health.status == "pass":
                print(f"Successfully connected to InfluxDB at {config.INFLUXDB_HOST}:{config.INFLUXDB_PORT}")
                
                # Check if bucket exists
                buckets_api = client.buckets_api()
                bucket = buckets_api.find_bucket_by_name(config.INFLUXDB_BUCKET)
                if not bucket:
                    print(f"Warning: InfluxDB bucket '{config.INFLUXDB_BUCKET}' not found.")
                    print("Please run setup_influxdb.py to create the bucket first.")
                    print("Continuing anyway, but data storage may fail.")
            else:
                print("Warning: InfluxDB health check failed.")
                print("Please ensure InfluxDB is running and properly configured.")
                print("Continuing anyway, but data storage may fail.")
        except Exception as e:
            print(f"Warning: Could not connect to InfluxDB: {e}")
            print("Please ensure InfluxDB v2.x is installed and running.")
            print("Continuing anyway, but data storage may fail.")
    
    # Register with Resource Catalog
    print("Registering with Resource Catalog...")
    success = start_registration(background=True)
    if success:
        print("Successfully registered with Resource Catalog")
    else:
        print("Warning: Failed to register with Resource Catalog, will retry in background")
    
    # Determine which components to run
    run_connector = not args.api_only
    run_api = not args.connector_only
    
    # Start the connector if requested
    if run_connector:
        connector = TimeSeriesConnector()
        
        if connector.start():
            print(f"Connector started successfully. Listening for messages on broker: {config.MQTT_HOST}:{config.MQTT_PORT}")
        else:
            print("Failed to start connector. Check logs for details.")
            update_status("offline")
            if not run_api:  # Only exit if we're not also running the API
                sys.exit(1)
    
    # Start the API server if requested
    if run_api:
        try:
            print(f"Starting API server on port {args.api_port}...")
            api_engine = start_api_server(port=args.api_port)
            print(f"API server running at http://0.0.0.0:{args.api_port}")
        except Exception as e:
            print(f"Failed to start API server: {e}")
            update_status("offline")
            if not run_connector or not connector.running:  # Exit if connector isn't running
                sys.exit(1)
    
    # Keep the main thread alive
    print("Press Ctrl+C to stop.")
    try:
        while (run_connector and connector and connector.running) or (run_api and 'api_engine' in locals()):
            time.sleep(1)
    except KeyboardInterrupt:
        # Handle with the signal handler
        pass
    

if __name__ == "__main__":
    main()