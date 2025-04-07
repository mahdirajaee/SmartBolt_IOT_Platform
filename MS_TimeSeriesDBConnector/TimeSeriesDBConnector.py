import os
import json
import time
import threading
import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import cherrypy
import requests
from datetime import datetime

class TimeSeriesDBConnector:
    exposed = True
    
    def __init__(self):
        self.catalog_url = os.environ.get('CATALOG_URL', 'http://localhost:8080')
        self.service_id = "time_series_db_connector"
        self.service_port = int(os.environ.get('SERVICE_PORT', 8081))
        
        self.service_info = {
            "id": self.service_id,
            "name": "Time Series DB Connector",
            "endpoint": f"http://localhost:{self.service_port}",
            "timestamp": int(time.time())
        }
        
        # Default configurations
        self.mqtt_broker = os.environ.get('MQTT_BROKER', 'localhost')
        self.mqtt_port = int(os.environ.get('MQTT_PORT', 1883))
        self.influxdb_url = os.environ.get('INFLUXDB_URL', 'http://localhost:8086')
        self.influxdb_token = os.environ.get('INFLUXDB_TOKEN', '')
        self.influxdb_org = os.environ.get('INFLUXDB_ORG', 'smart_iot')
        self.influxdb_bucket = os.environ.get('INFLUXDB_BUCKET', 'sensor_data')
        
        self.influxdb_client = None
        self.mqtt_client = None
        self.write_api = None
        self.query_api = None
        
        # Try to get config from catalog, but don't fail if unavailable
        try:
            self.get_config_from_catalog()
        except Exception as e:
            print(f"Warning: Could not get config from catalog - using default values: {e}")
        
        self.setup_influxdb()
        self.setup_mqtt()
        
        # Try to register with catalog, but don't fail if unavailable
        try:
            self.register_with_catalog()
            self.start_registration_update_thread()
        except Exception as e:
            print(f"Warning: Could not register with catalog: {e}")
    
    def get_config_from_catalog(self):
        try:
            response = requests.get(f"{self.catalog_url}/services/{self.service_id}", timeout=5)
            if response.status_code == 200:
                config = response.json()
                
                self.mqtt_broker = config.get('mqtt_broker', self.mqtt_broker)
                self.mqtt_port = config.get('mqtt_port', self.mqtt_port)
                
                self.influxdb_url = config.get('influxdb_url', self.influxdb_url)
                self.influxdb_token = config.get('influxdb_token', self.influxdb_token)
                self.influxdb_org = config.get('influxdb_org', self.influxdb_org)
                self.influxdb_bucket = config.get('influxdb_bucket', self.influxdb_bucket)
                
                print(f"Loaded configuration from catalog")
        except Exception as e:
            raise Exception(f"Error getting configuration from catalog: {e}")
    
    def setup_mqtt(self):
        try:
            # Modified MQTT client initialization to avoid version check
            self.mqtt_client = mqtt.Client()
                
            self.mqtt_client.on_connect = self.on_mqtt_connect
            self.mqtt_client.on_message = self.on_mqtt_message
            
            print(f"Connecting to MQTT broker at {self.mqtt_broker}:{self.mqtt_port}")
            self.mqtt_client.connect(self.mqtt_broker, self.mqtt_port, 60)
            self.mqtt_client.loop_start()
        except Exception as e:
            print(f"Failed to connect to MQTT broker: {e}")
            print("MQTT functionality will be disabled")
    
    def on_mqtt_connect(self, client, userdata, flags, rc):
        print(f"Connected to MQTT broker with result code {rc}")
        client.subscribe("/sensor/temperature/#")
        client.subscribe("/sensor/pressure/#")
    
    def on_mqtt_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            
            topic_parts = msg.topic.split('/')
            sensor_type = topic_parts[2]  # temperature or pressure
            sector_id = topic_parts[3]
            device_id = topic_parts[4]
            
            value = payload.get('value')
            timestamp = payload.get('timestamp')
            unit = payload.get('unit')
            
            self.store_sensor_data(sensor_type, sector_id, device_id, value, unit, timestamp)
        except Exception as e:
            print(f"Error processing MQTT message: {e}")
    
    def setup_influxdb(self):
        try:
            print(f"Connecting to InfluxDB at {self.influxdb_url}")
            
            # Set a default token for development
            if not self.influxdb_token:
                self.influxdb_token = "mydevtoken123"
                print(f"Using default development token for InfluxDB")
                
            self.influxdb_client = InfluxDBClient(
                url=self.influxdb_url,
                token=self.influxdb_token,
                org=self.influxdb_org
            )
            
            self.write_api = self.influxdb_client.write_api(write_options=SYNCHRONOUS)
            self.query_api = self.influxdb_client.query_api()
            
            print("Connected to InfluxDB")
        except Exception as e:
            print(f"Failed to connect to InfluxDB: {e}")
            print("InfluxDB functionality will be disabled")
    
    def store_sensor_data(self, sensor_type, sector_id, device_id, value, unit, timestamp=None):
        if not self.write_api:
            print("InfluxDB write API not initialized - cannot store data")
            return
        
        try:
            point = Point(sensor_type)
            point.tag("sector_id", sector_id)
            point.tag("device_id", device_id)
            point.field("value", float(value))
            
            if timestamp:
                point.time(timestamp * 1000000000)
            
            self.write_api.write(bucket=self.influxdb_bucket, record=point)
            print(f"Stored {sensor_type} data for device {device_id} in sector {sector_id}")
        except Exception as e:
            print(f"Error storing data in InfluxDB: {e}")
    
    def register_with_catalog(self):
        try:
            # Updated to match the catalog API format
            service_data = {
                "name": self.service_id,
                "endpoint": f"http://localhost:{self.service_port}",
                "port": self.service_port,
                "additional_info": {
                    "description": "Time Series DB Connector Service",
                    "mqtt_broker": self.mqtt_broker,
                    "mqtt_port": self.mqtt_port,
                    "influxdb_url": self.influxdb_url
                }
            }
            
            response = requests.post(
                f"{self.catalog_url}/service",
                json=service_data,
                timeout=5
            )
            
            if response.status_code in [200, 201]:
                print(f"Successfully registered with catalog")
            else:
                print(f"Failed to register with catalog: {response.status_code}")
        except Exception as e:
            raise Exception(f"Error registering with catalog: {e}")
    
    def start_registration_update_thread(self):
        def update_registration():
            while True:
                time.sleep(60)
                try:
                    self.register_with_catalog()
                except Exception as e:
                    print(f"Failed to update registration: {e}")
        
        thread = threading.Thread(target=update_registration)
        thread.daemon = True
        thread.start()
    
    @cherrypy.tools.json_out()
    def GET(self, *path, **params):
        if len(path) == 0:
            return {"service": "Time Series DB Connector", "status": "running"}
        
        if path[0] == "data":
            sensor_type = params.get("sensor_type")
            sector_id = params.get("sector_id")
            device_id = params.get("device_id")
            start_time = params.get("start_time")
            end_time = params.get("end_time")
            
            return self.get_sensor_data(sensor_type, sector_id, device_id, start_time, end_time)
        
        raise cherrypy.HTTPError(404, "Resource not found")
    
    def get_sensor_data(self, sensor_type, sector_id=None, device_id=None, start_time=None, end_time=None):
        if not self.query_api:
            return {"error": "InfluxDB query API not initialized"}
        
        try:
            query = f'from(bucket: "{self.influxdb_bucket}") |> range('
            
            if start_time:
                query += f'start: {start_time}'
            else:
                query += 'start: -1h'
            
            if end_time:
                query += f', stop: {end_time}'
            
            query += ')'
            
            if sensor_type:
                query += f' |> filter(fn: (r) => r._measurement == "{sensor_type}")'
            
            if sector_id:
                query += f' |> filter(fn: (r) => r.sector_id == "{sector_id}")'
            
            if device_id:
                query += f' |> filter(fn: (r) => r.device_id == "{device_id}")'
            
            tables = self.query_api.query(query)
            
            results = []
            for table in tables:
                for record in table.records:
                    results.append({
                        "time": record.get_time().isoformat(),
                        "sensor_type": record.get_measurement(),
                        "sector_id": record.values.get("sector_id"),
                        "device_id": record.values.get("device_id"),
                        "value": record.get_value()
                    })
            
            return {"data": results}
        except Exception as e:
            print(f"Error querying InfluxDB: {e}")
            return {"error": str(e)}


def main():
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': int(os.environ.get('SERVICE_PORT', 8081)),
    })
    
    connector = TimeSeriesDBConnector()
    
    cherrypy.tree.mount(connector, '/', {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'application/json')],
        }
    })
    
    cherrypy.engine.start()
    cherrypy.engine.block()


if __name__ == '__main__':
    main()