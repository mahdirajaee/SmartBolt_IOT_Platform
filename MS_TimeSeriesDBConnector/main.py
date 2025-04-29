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

import os
import sys

# Add the parent directory to sys.path to ensure MessageBroker can be found
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

try:
    from MessageBroker.client import MQTTClient
except ImportError:
    # Try an alternate path in case directory structure is different
    alt_broker_path = os.path.join(parent_dir, 'MessageBroker')
    if os.path.exists(alt_broker_path):
        sys.path.insert(0, alt_broker_path)
        try:
            from client import MQTTClient  # Direct import when path is added
        except ImportError:
            print("Error: Could not import message broker client. Please ensure the MessageBroker module is available.")
            print(f"Tried paths: {parent_dir}, {alt_broker_path}")
            print(f"Available files in MessageBroker: {os.listdir(alt_broker_path) if os.path.exists(alt_broker_path) else 'directory not found'}")
            sys.exit(1)
    else:
        print("Error: Could not import message broker client. Please ensure the MessageBroker module is available.")
        print(f"MessageBroker directory not found at {alt_broker_path}")
        sys.exit(1)

if config.LOGGING_ENABLED:
    logging.basicConfig(
        filename=config.LOG_FILE,
        level=getattr(logging, config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
else:
    logging.basicConfig(level=logging.WARNING)

logger = logging.getLogger('timeseries_connector')

console = logging.StreamHandler()
console.setLevel(getattr(logging, config.LOG_LEVEL))
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)

class TimeSeriesConnector:
    
    def __init__(self):
        self.storage = get_storage()
        self.mqtt_client = None
        self.running = False
        self.connected_to_broker = False
        self.connection_retry_count = 0
        self.max_connection_retries = 5
        self.connection_retry_interval = 5
        
    def connect_to_broker(self):
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
        if not self.connected_to_broker:
            logger.error("Cannot subscribe: not connected to message broker")
            return False
            
        try:
            self.mqtt_client.subscribe(
                config.SENSOR_DATA_TOPIC, 
                qos=1,
                callback=self.process_sensor_data
            )
            logger.info(f"Subscribed to sensor data topic: {config.SENSOR_DATA_TOPIC}")
            
            self.mqtt_client.subscribe(
                config.VALVE_STATUS_TOPIC, 
                qos=1,
                callback=self.process_valve_status
            )
            logger.info(f"Subscribed to valve status topic: {config.VALVE_STATUS_TOPIC}")
            
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
        try:
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8')
                
            data = json.loads(payload)
            logger.debug(f"Received sensor data: {data}")
            
            timestamp = data.get('timestamp', datetime.now().isoformat())
            device_id = data.get('device_id', 'unknown')
            readings = data.get('readings', {})
            metadata = {
                "topic": topic,
                "qos": qos
            }
            
            if 'device_info' in data:
                metadata['device_info'] = data['device_info']
            if 'sector_info' in data:
                metadata['sector_info'] = data['sector_info']
            
            for sensor_type, reading in readings.items():
                if isinstance(reading, dict):
                    value = reading.get('value')
                    unit = reading.get('unit')
                else:
                    value = reading
                    unit = None
                
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
        try:
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8')
                
            data = json.loads(payload)
            logger.debug(f"Received valve status: {data}")
            
            timestamp = data.get('timestamp', datetime.now().isoformat())
            sector_id = data.get('sector_id')
            valve_state = data.get('state')
            if not sector_id or not valve_state:
                logger.warning("Missing sector_id or valve_state in valve status message")
                return
            
            metadata = {
                "topic": topic,
                "qos": qos,
                "last_action": data.get('last_action')
            }
            
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
        try:
            if isinstance(payload, bytes):
                payload = payload.decode('utf-8')
                
            data = json.loads(payload)
            event = data.get('event')
            
            logger.debug(f"Received system event: {event}")
            
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in system event message: {payload}")
        except Exception as e:
            logger.error(f"Error processing system event: {e}")
    
    def start(self):
        if self.running:
            logger.warning("Connector is already running")
            return False
        
        logger.info("Starting Time Series DB Connector")
        
        if not self.connect_to_broker():
            while (self.connection_retry_count < self.max_connection_retries):
                self.connection_retry_count += 1
                logger.info(f"Retrying connection to broker ({self.connection_retry_count}/{self.max_connection_retries})...")
                time.sleep(self.connection_retry_interval)
                if self.connect_to_broker():
                    break
            
            if not self.connected_to_broker:
                logger.error(f"Failed to connect to broker after {self.max_connection_retries} attempts")
                return False
        
        if not self.subscribe_to_topics():
            logger.error("Failed to subscribe to topics")
            self.mqtt_client.stop()
            return False
        
        self.running = True
        logger.info("Time Series DB Connector started successfully")
        
        return True
    
    def stop(self):
        if not self.running:
            return False
        
        logger.info("Stopping Time Series DB Connector")
        
        if self.mqtt_client:
            self.mqtt_client.stop()
        
        if self.storage:
            self.storage.close()
        
        self.running = False
        self.connected_to_broker = False
        logger.info("Time Series DB Connector stopped")
        
        return True


connector = None

def start_api_server(host='0.0.0.0', port=config.API_PORT):
    import cherrypy
    
    cherrypy.config.update({
        'server.socket_host': host,
        'server.socket_port': port,
        'engine.autoreload.on': False,
        'log.screen': True
    })
    
    conf = {
        '/': {
            'tools.sessions.on': False,
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'application/json')],
            'tools.encode.on': True,
            'tools.encode.encoding': 'utf-8'
        }
    }
    
    cherrypy.tree.mount(TimeSeriesAPI(), '/', conf)
    
    cherrypy.engine.start()
    logger.info(f"API server started on http://{host}:{port}")
    
    return cherrypy.engine

def signal_handler(sig, frame):
    logger.info(f"Received signal {sig}, shutting down...")
    
    update_status("offline")
    
    if connector:
        connector.stop()
    
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
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    import argparse
    parser = argparse.ArgumentParser(description='Time Series DB Connector')
    parser.add_argument('--api-only', action='store_true', help='Run only the API server without the message broker connector')
    parser.add_argument('--connector-only', action='store_true', help='Run only the message broker connector without the API server')
    parser.add_argument('--api-port', type=int, default=config.API_PORT, help='Port for the API server')
    args = parser.parse_args()
    
    print("Smart Bolt - Time Series DB Connector")
    print(f"Starting service...")
    
    if config.STORAGE_TYPE.lower() == "influxdb":
        try:
            from influxdb_client import InfluxDBClient
            client = InfluxDBClient(
                url=f"http://{config.INFLUXDB_HOST}:{config.INFLUXDB_PORT}",
                token=config.INFLUXDB_TOKEN,
                org=config.INFLUXDB_ORG
            )
            
            health = client.health()
            if health and health.status == "pass":
                print(f"Successfully connected to InfluxDB at {config.INFLUXDB_HOST}:{config.INFLUXDB_PORT}")
                
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
    
    print("Registering with Resource Catalog...")
    success = start_registration(background=True)
    if success:
        print("Successfully registered with Resource Catalog")
    else:
        print("Warning: Failed to register with Resource Catalog, will retry in background")
    
    run_connector = not args.api_only
    run_api = not args.connector_only
    
    if run_connector:
        connector = TimeSeriesConnector()
        
        if connector.start():
            print(f"Connector started successfully. Listening for messages on broker: {config.MQTT_HOST}:{config.MQTT_PORT}")
        else:
            print("Failed to start connector. Check logs for details.")
            update_status("offline")
            if not run_api:
                sys.exit(1)
    
    if run_api:
        try:
            print(f"Starting API server on port {args.api_port}...")
            api_engine = start_api_server(port=args.api_port)
            print(f"API server running at http://0.0.0.0:{args.api_port}")
        except Exception as e:
            print(f"Failed to start API server: {e}")
            update_status("offline")
            if not run_connector or not connector.running:
                sys.exit(1)
    
    print("Press Ctrl+C to stop.")
    try:
        while (run_connector and connector and connector.running) or (run_api and 'api_engine' in locals()):
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    

if __name__ == "__main__":
    main()