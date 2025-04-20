import os
import json
import time
import threading
import socket
import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import cherrypy
import requests
from datetime import datetime
from dotenv import load_dotenv

class TimeSeriesDBConnector:
    exposed = True
    
    def __init__(self):
        self.load_env_config()
        
        self.service_id = "time_series_db_connector"
        self.service_port = self.get_available_port(int(os.environ.get('TIMESERIES_PORT', 8081)))
        
        self.service_info = {
            "id": self.service_id,
            "name": "Time Series DB Connector",
            "endpoint": f"http://localhost:{self.service_port}",
            "timestamp": int(time.time())
        }
        
        # Default configurations
        self.mqtt_broker = os.environ.get('MQTT_BROKER')
        self.mqtt_port = int(os.environ.get('MQTT_PORT'))
        self.influxdb_url = os.environ.get('INFLUXDB_URL')
        self.influxdb_token = os.environ.get('INFLUXDB_TOKEN')
        self.influxdb_org = os.environ.get('INFLUXDB_ORG')
        self.influxdb_bucket = os.environ.get('INFLUXDB_BUCKET')
        self.influxdb_client = None
        self.mqtt_client = None
        self.write_api = None
        self.query_api = None
        
        try:
            self.get_config_from_catalog()
        except Exception as e:
            print(f"Warning: Could not get config from catalog - using default values: {e}")
        
        self.setup_influxdb()
        self.setup_mqtt()
        
        try:
            self.register_with_catalog()
            self.start_registration_update_thread()
        except Exception as e:
            print(f"Warning: Could not register with catalog: {e}")
    
    def load_env_config(self):
        load_dotenv()
        
    def get_available_port(self, preferred_port, max_attempts=10):
        port = preferred_port
        attempts = 0
        
        while attempts < max_attempts:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.bind(("0.0.0.0", port))
                sock.close()
                print(f"Using port {port}")
                return port
            except socket.error:
                attempts += 1
                port += 1
                print(f"Port {port-1} is busy, trying {port}")
                
        print(f"Warning: Could not find available port after {max_attempts} attempts. Using {port}")
        return port
    
    def get_config_from_catalog(self):
        try:
            catalog_url = os.environ.get('CATALOG_URL')
            response = requests.get(f"{catalog_url}/services/{self.service_id}", timeout=5)
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
            sensor_type = topic_parts[2]
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
            catalog_url = os.environ.get('CATALOG_URL')
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
                f"{catalog_url}/service",
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
        
        if path[0] == "measurements":
            if len(path) > 1 and path[1] == "latest":
                sector = params.get("sector")
                device = params.get("device")
                return self.get_latest_measurements(sector, device)
            
            if len(path) > 1 and path[1] == "query":
                sector = params.get("sector")
                from_time = params.get("from")
                to_time = params.get("to")
                aggregation = params.get("aggregation", "hourly")
                return self.get_historical_measurements(sector, from_time, to_time, aggregation)
            
            # Default measurements endpoint
            return {
                "endpoints": {
                    "latest": "/measurements/latest?sector=sector_id&device=device_id",
                    "query": "/measurements/query?sector=sector_id&from=time&to=time&aggregation=hourly"
                }
            }
        
        if path[0] == "health":
            return {"status": "healthy", "timestamp": time.time()}
            
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

    def get_latest_measurements(self, sector_id=None, device_id=None):
        """Get the latest measurements for the specified sector/device"""
        if not self.query_api:
            return {"error": "InfluxDB query API not initialized"}
        
        try:
            # Get temperature data
            temp_query = f'from(bucket: "{self.influxdb_bucket}") |> range(start: -10m)'
            temp_query += ' |> filter(fn: (r) => r._measurement == "temperature")'
            
            if sector_id:
                temp_query += f' |> filter(fn: (r) => r.sector_id == "{sector_id}")'
            if device_id:
                temp_query += f' |> filter(fn: (r) => r.device_id == "{device_id}")'
                
            temp_query += ' |> last()'
            
            # Get pressure data
            pressure_query = f'from(bucket: "{self.influxdb_bucket}") |> range(start: -10m)'
            pressure_query += ' |> filter(fn: (r) => r._measurement == "pressure")'
            
            if sector_id:
                pressure_query += f' |> filter(fn: (r) => r.sector_id == "{sector_id}")'
            if device_id:
                pressure_query += f' |> filter(fn: (r) => r.device_id == "{device_id}")'
                
            pressure_query += ' |> last()'
            
            temp_tables = self.query_api.query(temp_query)
            pressure_tables = self.query_api.query(pressure_query)
            
            # Process temperature data
            temp_results = []
            for table in temp_tables:
                for record in table.records:
                    temp_results.append({
                        "timestamp": record.get_time().isoformat(),
                        "device_id": record.values.get("device_id"),
                        "sector_id": record.values.get("sector_id"),
                        "value": record.get_value(),
                        "unit": "celsius"
                    })
            
            # Process pressure data
            pressure_results = []
            for table in pressure_tables:
                for record in table.records:
                    pressure_results.append({
                        "timestamp": record.get_time().isoformat(),
                        "device_id": record.values.get("device_id"),
                        "sector_id": record.values.get("sector_id"),
                        "value": record.get_value(),
                        "unit": "kPa"
                    })
            
            # If no real data exists, generate mock data
            if not temp_results and not pressure_results:
                # Generate some mock data for demo
                import random
                from datetime import datetime
                
                mock_time = datetime.now().isoformat()
                
                if not sector_id:
                    sector_id = "sector1"
                
                devices = ["dev001", "dev020"] if not device_id else [device_id]
                
                for dev in devices:
                    temp_results.append({
                        "timestamp": mock_time,
                        "device_id": dev,
                        "sector_id": sector_id,
                        "value": round(random.uniform(20, 35), 2),
                        "unit": "celsius"
                    })
                    
                    pressure_results.append({
                        "timestamp": mock_time,
                        "device_id": dev,
                        "sector_id": sector_id,
                        "value": round(random.uniform(40, 70), 2),
                        "unit": "kPa"
                    })
            
            return {
                "temperature": temp_results,
                "pressure": pressure_results
            }
            
        except Exception as e:
            print(f"Error querying latest measurements: {e}")
            return {"error": str(e)}

    def get_historical_measurements(self, sector_id, from_time=None, to_time=None, aggregation="hourly"):
        """Get historical data with specified aggregation"""
        if not self.query_api:
            return {"error": "InfluxDB query API not initialized"}
            
        try:
            # Set default time range if not specified
            if not from_time:
                from_time = "-1h"
            if not to_time:
                to_time = "now()"
                
            # Set window based on aggregation
            window = "1m"
            if aggregation == "hourly":
                window = "1h"
            elif aggregation == "daily":
                window = "1d"
            elif aggregation == "weekly":
                window = "1w"
            elif aggregation == "monthly":
                window = "30d"
            
            # Get temperature data
            temp_query = f'from(bucket: "{self.influxdb_bucket}") |> range(start: {from_time}, stop: {to_time})'
            temp_query += ' |> filter(fn: (r) => r._measurement == "temperature")'
            
            if sector_id:
                temp_query += f' |> filter(fn: (r) => r.sector_id == "{sector_id}")'
                
            temp_query += f' |> aggregateWindow(every: {window}, fn: mean)'
            
            # Get pressure data
            pressure_query = f'from(bucket: "{self.influxdb_bucket}") |> range(start: {from_time}, stop: {to_time})'
            pressure_query += ' |> filter(fn: (r) => r._measurement == "pressure")'
            
            if sector_id:
                pressure_query += f' |> filter(fn: (r) => r.sector_id == "{sector_id}")'
                
            pressure_query += f' |> aggregateWindow(every: {window}, fn: mean)'
            
            temp_tables = self.query_api.query(temp_query)
            pressure_tables = self.query_api.query(pressure_query)
            
            # Process results
            temp_results = []
            for table in temp_tables:
                for record in table.records:
                    temp_results.append({
                        "timestamp": record.get_time().isoformat(),
                        "device_id": record.values.get("device_id"),
                        "sector_id": record.values.get("sector_id"),
                        "value": record.get_value(),
                        "unit": "celsius"
                    })
            
            pressure_results = []
            for table in pressure_tables:
                for record in table.records:
                    pressure_results.append({
                        "timestamp": record.get_time().isoformat(),
                        "device_id": record.values.get("device_id"),
                        "sector_id": record.values.get("sector_id"),
                        "value": record.get_value(),
                        "unit": "kPa"
                    })
            
            # If no real data exists, generate mock data
            if not temp_results and not pressure_results:
                # Generate mock data for demo purposes
                import random
                from datetime import datetime, timedelta
                
                if not sector_id:
                    sector_id = "sector1"
                
                devices = ["dev001", "dev020"]
                mock_data_points = 24  # Generate 24 points for demonstration
                
                base_time = datetime.now() - timedelta(hours=mock_data_points)
                
                for i in range(mock_data_points):
                    point_time = (base_time + timedelta(hours=i)).isoformat()
                    
                    for dev in devices:
                        # Add some randomness but keep a trend
                        trend_factor = i / mock_data_points  # 0 to 1 over time
                        
                        temp_results.append({
                            "timestamp": point_time,
                            "device_id": dev,
                            "sector_id": sector_id,
                            "value": round(20 + (trend_factor * 10) + random.uniform(-2, 2), 2),
                            "unit": "celsius"
                        })
                        
                        pressure_results.append({
                            "timestamp": point_time,
                            "device_id": dev,
                            "sector_id": sector_id,
                            "value": round(40 + (trend_factor * 20) + random.uniform(-5, 5), 2),
                            "unit": "kPa"
                        })
            
            return {
                "temperature": temp_results,
                "pressure": pressure_results,
                "aggregation": aggregation
            }
            
        except Exception as e:
            print(f"Error querying historical measurements: {e}")
            return {"error": str(e)}


def main():
    connector = TimeSeriesDBConnector()
    
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': connector.service_port,
    })
    
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