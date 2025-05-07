#!/usr/bin/env python3

"""
API for the Smart Bolt Time Series DB Connector

This REST API provides endpoints for querying sensor data and valve states
stored in the time series database.
"""

import json
import datetime
from datetime import timedelta
import logging
import cherrypy
import config
from storage import get_storage

# Set up logging
logger = logging.getLogger('timeseries_api')
if config.LOGGING_ENABLED:
    logger.setLevel(getattr(logging, config.LOG_LEVEL))
    handler = logging.FileHandler(config.LOG_FILE)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
else:
    logger.addHandler(logging.NullHandler())

class TimeSeriesAPI:
    """REST API for Smart Bolt Time Series Database"""
    
    def __init__(self):
        self.storage = get_storage()
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self):
        """Root endpoint with API information"""
        return {
            "name": "Smart Bolt Time Series DB API",
            "version": "1.0",
            "endpoints": {
                "sensor_data": "/sensor_data?device_id=<id>&sensor_type=<type>&start=<iso_datetime>&end=<iso_datetime>",
                "valve_states": "/valve_states?sector_id=<id>&start=<iso_datetime>&end=<iso_datetime>",
                "devices": "/devices",
                "sectors": "/sectors"
            }
        }
    
    """ get all data from the time series database """
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def all_seneor_data(self):
        """Query all sensor data"""
        try:
            
            # Define a default time range (e.g., last 24 hours)
            end_time = datetime.datetime.now()
            start_time = end_time - timedelta(hours=24)
            # Get all data from storage
            data = self.storage.get_all_sensor_data(start_time=start_time, end_time=end_time)
            
            return {
                "count": len(data),
                "data": data
            }
            
        except Exception as e:
            logger.error(f"Error processing all_sensor_data request: {e}")
            return {"error": str(e)}
    """ get all data from the time series database """

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def sensor_data(self, device_id=None, sensor_type=None, hours=None, start=None, end=None, limit=None):
        """Query sensor data"""
        try:
            # Input validation
            if not device_id:
                return {"error": "device_id parameter is required"}
            if not sensor_type:
                return {"error": "sensor_type parameter is required"}
            
            # Parse time parameters
            end_time = datetime.datetime.now()
            
            if hours:
                try:
                    hours = float(hours)
                    start_time = end_time - timedelta(hours=hours)
                except ValueError:
                    return {"error": f"Invalid hours value: {hours}"}
            elif start and end:
                try:
                    start_time = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
                    end_time = datetime.datetime.fromisoformat(end.replace('Z', '+00:00'))
                except ValueError:
                    return {"error": "Invalid datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"}
            elif start:
                try:
                    start_time = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
                except ValueError:
                    return {"error": "Invalid start datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"}
            else:
                # Default to last 24 hours
                start_time = end_time - timedelta(hours=24)
            
            # Get data from storage
            data = self.storage.get_sensor_data(
                device_id=device_id,
                sensor_type=sensor_type,
                start_time=start_time,
                end_time=end_time
            )
            
            # Apply limit if specified
            if limit:
                try:
                    limit = int(limit)
                    data = data[:limit]
                except ValueError:
                    return {"error": f"Invalid limit value: {limit}"}
            
            return {
                "device_id": device_id,
                "sensor_type": sensor_type,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "count": len(data),
                "data": data
            }
            
        except Exception as e:
            logger.error(f"Error processing sensor_data request: {e}")
            return {"error": str(e)}
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def valve_states(self, sector_id=None, hours=None, start=None, end=None, limit=None):
        """Query valve state changes"""
        try:
            # Input validation
            if not sector_id:
                return {"error": "sector_id parameter is required"}
            
            # Parse time parameters
            end_time = datetime.datetime.now()
            
            if hours:
                try:
                    hours = float(hours)
                    start_time = end_time - timedelta(hours=hours)
                except ValueError:
                    return {"error": f"Invalid hours value: {hours}"}
            elif start and end:
                try:
                    start_time = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
                    end_time = datetime.datetime.fromisoformat(end.replace('Z', '+00:00'))
                except ValueError:
                    return {"error": "Invalid datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"}
            elif start:
                try:
                    start_time = datetime.datetime.fromisoformat(start.replace('Z', '+00:00'))
                except ValueError:
                    return {"error": "Invalid start datetime format. Use ISO format (YYYY-MM-DDTHH:MM:SS)"}
            else:
                # Default to last 24 hours
                start_time = end_time - timedelta(hours=24)
            
            # Get data from storage
            data = self.storage.get_valve_states(
                sector_id=sector_id,
                start_time=start_time,
                end_time=end_time
            )
            
            # Apply limit if specified
            if limit:
                try:
                    limit = int(limit)
                    data = data[:limit]
                except ValueError:
                    return {"error": f"Invalid limit value: {limit}"}
            
            return {
                "sector_id": sector_id,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "count": len(data),
                "data": data
            }
            
        except Exception as e:
            logger.error(f"Error processing valve_states request: {e}")
            return {"error": str(e)}
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def devices(self):
        """Get unique device IDs that have data in the time series database"""
        try:
            # For InfluxDB, we need a different approach to get unique device IDs
            if config.STORAGE_TYPE.lower() == "influxdb":
                try:
                    from influxdb_client import InfluxDBClient
                    
                    try:
                        client = InfluxDBClient(
                            url=f"http://{config.INFLUXDB_HOST}:{config.INFLUXDB_PORT}",
                            token=config.INFLUXDB_TOKEN,
                            org=config.INFLUXDB_ORG,
                            timeout=30000
                        )
                        # Optional: check connection
                        health = client.health()
                        if health.status != "pass":
                            raise Exception("InfluxDB connection unhealthy")
                    except Exception as e:
                        print(f"Failed to connect to InfluxDB: {e}")
                    
                    self.query_api = client.query_api()
                    # Get unique device_ids from both temperature and pressure measurements
                    query_temp = f'''
                            from(bucket: "{config.INFLUXDB_BUCKET}")
                            |> range(start: -30d)
                            |> filter(fn: (r) => r["_measurement"] == "temperature")
                            |> map(fn: (r) => ({{ r with _value: string(v: r._value) }}))
                            |> group(columns: ["device_id"])
                            |> distinct(column: "device_id")
                    '''
                    query_pressure = f'''
                            from(bucket: "{config.INFLUXDB_BUCKET}")
                            |> range(start: -30d)
                            |> filter(fn: (r) => r._measurement == "pressure")
                            |> map(fn: (r) => ({{ r with _value: string(v: r._value) }}))
                            |> group(columns: ["device_id"])
                            |> distinct(column: "device_id")
                    '''
                    # Fetch device IDs for both temperature and pressure
                    result_temp = self.query_api.query(org=config.INFLUXDB_ORG, query=query_temp)
                    result_pressure = self.query_api.query(org=config.INFLUXDB_ORG, query=query_pressure)
                    # Extract device IDs from query results
                    temp_devices = []
                    pressure_devices = []
                    # Extract temperature device IDs
                    for table in result_temp:
                        for record in table.records:
                            temp_devices.append(record.get_value())

                    # Extract pressure device IDs
                    for table in result_pressure:
                        for record in table.records:
                            pressure_devices.append(record.get_value())
                    
                    # Combine and remove duplicates
                    all_devices = list(set(temp_devices + pressure_devices))
                    all_devices.sort()
                    num_devices = len(all_devices)
                    return {"num_devices": num_devices,"devices": all_devices}
                except Exception as e:
                    logger.error(f"Error getting device IDs from InfluxDB: {e}")
                    return {"error": str(e)}
            else:
                # For SQLite and others, we can implement a similar approach
                # This is a placeholder - actual implementation would depend on storage details
                return {"error": "Getting device list is only supported for InfluxDB"}
        except Exception as e:
            logger.error(f"Error processing devices request: {e}")
            return {"error": str(e)}
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def sectors(self):
        """Get unique sector IDs that have valve data in the time series database"""
        try:
            # For InfluxDB, we need a different approach to get unique sector IDs
            if config.STORAGE_TYPE.lower() == "influxdb":
                try:
                    from influxdb_client import InfluxDBClient
                    
                    try:
                        client = InfluxDBClient(
                            url=f"http://{config.INFLUXDB_HOST}:{config.INFLUXDB_PORT}",
                            token=config.INFLUXDB_TOKEN,
                            org=config.INFLUXDB_ORG,
                            timeout=30000
                        )
                        # Optional: check connection
                        health = client.health()
                        if health.status != "pass":
                            raise Exception("InfluxDB connection unhealthy")
                    except Exception as e:
                        print(f"Failed to connect to InfluxDB: {e}")
                    self.query_api = client.query_api()
                    # Get unique sector_ids from valve_state measurement
                    query = f'''
                            from(bucket: "{config.INFLUXDB_BUCKET}")
                            |> range(start: -30d)
                            |> filter(fn: (r) => r["_measurement"] == "valve_state")
                            |> map(fn: (r) => ({{ r with _value: string(v: r._value) }}))
                            |> group(columns: ["sector_id"])
                            |> distinct(column: "sector_id")
                    '''
                    # Fetch sector IDs
                    result = self.query_api.query(org=config.INFLUXDB_ORG, query=query)
                    # Extract sector IDs from query results
                    sectors = []
                    for table in result:
                        for record in table.records:
                            sectors.append(record.get_value())
                    # Remove duplicates
                    sectors = list(set(sectors))
                    sectors.sort()
                    # Get the number of unique sectors
                    num_sectors = len(sectors)
                    
                    return {"num_sectors": num_sectors, "sectors": sectors}
                except Exception as e:
                    logger.error(f"Error getting sector IDs from InfluxDB: {e}")
                    return {"error": str(e)}
            else:
                # For SQLite and others, we can implement a similar approach
                # This is a placeholder - actual implementation would depend on storage details
                return {"error": "Getting sector list is only supported for InfluxDB"}
        except Exception as e:
            logger.error(f"Error processing sectors request: {e}")
            return {"error": str(e)}


def start_api(host='0.0.0.0', port=config.API_PORT):
    """Start the API server"""
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
    
    # Start the server
    cherrypy.quickstart(TimeSeriesAPI(), '/', conf)


if __name__ == '__main__':
    print(f"Starting Time Series API on http://0.0.0.0:{config.API_PORT}")
    start_api()