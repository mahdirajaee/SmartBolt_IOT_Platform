import os
import json
import logging
import sqlite3
import datetime
from abc import ABC, abstractmethod

import config

# Set up logging
logger = logging.getLogger("timeseries_storage")
if config.LOGGING_ENABLED:
    logger.setLevel(getattr(logging, config.LOG_LEVEL))
    handler = logging.FileHandler(config.LOG_FILE)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
else:
    logger.addHandler(logging.NullHandler())

class TimeSeriesStorage(ABC):
    """Abstract base class for time series data storage"""
    
    @abstractmethod
    def store_sensor_data(self, timestamp, device_id, sensor_type, value, unit, metadata=None):
        """Store a single sensor reading in the time series database"""
        pass
    
    @abstractmethod
    def store_sensor_data_batch(self, readings):
        """Store multiple sensor readings in a batch"""
        pass
        
    @abstractmethod
    def store_valve_state(self, timestamp, sector_id, state, metadata=None):
        """Store a valve state change in the time series database"""
        pass
    
    @abstractmethod
    def get_sensor_data(self, device_id, sensor_type, start_time, end_time):
        """Retrieve sensor data for a specific device and sensor type within a time range"""
        pass
    
    @abstractmethod
    def get_valve_states(self, sector_id, start_time, end_time):
        """Retrieve valve state changes for a specific sector within a time range"""
        pass
    
    @abstractmethod
    def close(self):
        """Close database connections"""
        pass

class SQLiteStorage(TimeSeriesStorage):
    """SQLite implementation of time series data storage"""
    
    def __init__(self, db_file=None):
        if db_file is None:
            db_file = config.SQLITE_DB_FILE
            
        self.db_file = db_file
        self._initialize_db()
    
    def _initialize_db(self):
        """Initialize the SQLite database with required tables"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Create sensor readings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sensor_readings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    device_id TEXT NOT NULL,
                    sensor_type TEXT NOT NULL,
                    value REAL NOT NULL,
                    unit TEXT,
                    metadata TEXT
                )
            ''')
            
            # Create valve states table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS valve_states (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    sector_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    metadata TEXT
                )
            ''')
            
            # Create index on timestamp and device_id for faster queries
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_sensor_timestamp_device ON sensor_readings(timestamp, device_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_valve_timestamp_sector ON valve_states(timestamp, sector_id)')
            
            conn.commit()
            logger.info("SQLite database initialized")
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")
        finally:
            if conn:
                conn.close()
    
    def store_sensor_data(self, timestamp, device_id, sensor_type, value, unit, metadata=None):
        """Store a single sensor reading in SQLite"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Convert metadata to JSON string if provided
            metadata_str = None
            if metadata:
                metadata_str = json.dumps(metadata)
            
            cursor.execute(
                '''INSERT INTO sensor_readings 
                   (timestamp, device_id, sensor_type, value, unit, metadata) 
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (timestamp.isoformat() if isinstance(timestamp, datetime.datetime) else timestamp, 
                 str(device_id), sensor_type, value, unit, metadata_str)
            )
            
            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Error storing sensor data: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def store_sensor_data_batch(self, readings):
        """Store multiple sensor readings in a batch"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            data_to_insert = []
            for reading in readings:
                # Convert metadata to JSON string if provided
                metadata_str = None
                if 'metadata' in reading and reading['metadata']:
                    metadata_str = json.dumps(reading['metadata'])
                    
                timestamp = reading['timestamp']
                if isinstance(timestamp, datetime.datetime):
                    timestamp = timestamp.isoformat()
                    
                data_to_insert.append((
                    timestamp,
                    str(reading['device_id']),
                    reading['sensor_type'],
                    reading['value'],
                    reading.get('unit', None),
                    metadata_str
                ))
            
            cursor.executemany(
                '''INSERT INTO sensor_readings 
                   (timestamp, device_id, sensor_type, value, unit, metadata) 
                   VALUES (?, ?, ?, ?, ?, ?)''',
                data_to_insert
            )
            
            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Error storing batch sensor data: {e}")
            return False
        finally:
            if conn:
                conn.close()
                
    def store_valve_state(self, timestamp, sector_id, state, metadata=None):
        """Store a valve state change in SQLite"""
        try:
            conn = sqlite3.connect(self.db_file)
            cursor = conn.cursor()
            
            # Convert metadata to JSON string if provided
            metadata_str = None
            if metadata:
                metadata_str = json.dumps(metadata)
            
            cursor.execute(
                '''INSERT INTO valve_states 
                   (timestamp, sector_id, state, metadata) 
                   VALUES (?, ?, ?, ?)''',
                (timestamp.isoformat() if isinstance(timestamp, datetime.datetime) else timestamp, 
                 sector_id, state, metadata_str)
            )
            
            conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Error storing valve state: {e}")
            return False
        finally:
            if conn:
                conn.close()
    
    def get_sensor_data(self, device_id, sensor_type, start_time, end_time):
        """Retrieve sensor data for a specific device and sensor type within a time range"""
        try:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row  # Enable row factory to return dictionaries
            cursor = conn.cursor()
            
            # Convert datetime objects to ISO format strings if needed
            if isinstance(start_time, datetime.datetime):
                start_time = start_time.isoformat()
            if isinstance(end_time, datetime.datetime):
                end_time = end_time.isoformat()
            
            cursor.execute(
                '''SELECT timestamp, device_id, sensor_type, value, unit, metadata 
                   FROM sensor_readings 
                   WHERE device_id = ? AND sensor_type = ? AND timestamp BETWEEN ? AND ? 
                   ORDER BY timestamp''',
                (str(device_id), sensor_type, start_time, end_time)
            )
            
            rows = cursor.fetchall()
            
            # Convert rows to list of dictionaries
            result = []
            for row in rows:
                item = {key: row[key] for key in row.keys()}
                
                # Parse metadata JSON if present
                if item['metadata']:
                    try:
                        item['metadata'] = json.loads(item['metadata'])
                    except json.JSONDecodeError:
                        pass  # Keep as string if not valid JSON
                        
                result.append(item)
                
            return result
        except sqlite3.Error as e:
            logger.error(f"Error retrieving sensor data: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def get_valve_states(self, sector_id, start_time, end_time):
        """Retrieve valve state changes for a specific sector within a time range"""
        try:
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row  # Enable row factory to return dictionaries
            cursor = conn.cursor()
            
            # Convert datetime objects to ISO format strings if needed
            if isinstance(start_time, datetime.datetime):
                start_time = start_time.isoformat()
            if isinstance(end_time, datetime.datetime):
                end_time = end_time.isoformat()
            
            cursor.execute(
                '''SELECT timestamp, sector_id, state, metadata 
                   FROM valve_states 
                   WHERE sector_id = ? AND timestamp BETWEEN ? AND ? 
                   ORDER BY timestamp''',
                (sector_id, start_time, end_time)
            )
            
            rows = cursor.fetchall()
            
            # Convert rows to list of dictionaries
            result = []
            for row in rows:
                item = {key: row[key] for key in row.keys()}
                
                # Parse metadata JSON if present
                if item['metadata']:
                    try:
                        item['metadata'] = json.loads(item['metadata'])
                    except json.JSONDecodeError:
                        pass  # Keep as string if not valid JSON
                        
                result.append(item)
                
            return result
        except sqlite3.Error as e:
            logger.error(f"Error retrieving valve states: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def close(self):
        """Close database connections - nothing to do for SQLite"""
        pass


class InfluxDBStorage(TimeSeriesStorage):
    """InfluxDB v2.x implementation of time series data storage"""
    
    def __init__(self):
        try:
            # Import the v2 client library
            from influxdb_client import InfluxDBClient, Point, WritePrecision
            from influxdb_client.client.write_api import SYNCHRONOUS
            from dateutil import parser
            
            # Connect to InfluxDB v2.x
            self.client = InfluxDBClient(
                url=f"http://{config.INFLUXDB_HOST}:{config.INFLUXDB_PORT}",
                token=config.INFLUXDB_TOKEN,
                org=config.INFLUXDB_ORG
            )
            
            # Initialize write and query APIs
            self.write_api = self.client.write_api(write_options=SYNCHRONOUS)
            self.query_api = self.client.query_api()
            
            # Keep references to classes needed for operations
            self.Point = Point
            self.WritePrecision = WritePrecision
            self.parser = parser
            
            logger.info(f"Connected to InfluxDB v2.x at {config.INFLUXDB_HOST}:{config.INFLUXDB_PORT}")
            self._influxdb_available = True
        except ImportError:
            logger.error("InfluxDB Python client not installed. Install using 'pip install influxdb-client'")
            self._influxdb_available = False
        except Exception as e:
            logger.error(f"Failed to connect to InfluxDB: {e}")
            self._influxdb_available = False
    
    def store_sensor_data(self, timestamp, device_id, sensor_type, value, unit, metadata=None):
        """Store a single sensor reading in InfluxDB v2.x"""
        if not self._influxdb_available:
            return False
            
        try:
            # Create a Point
            point = self.Point(sensor_type)
            
            # Add tags
            point = point.tag("device_id", str(device_id))
            
            # Add fields
            point = point.field("value", float(value))
            if unit:
                point = point.field("unit", unit)
                
            # Add metadata as tags/fields
            if metadata:
                for key, val in metadata.items():
                    if isinstance(val, (int, float, bool, str)):
                        point = point.tag(key, str(val))
                    else:
                        # Store complex objects as JSON string in fields
                        point = point.field(key, json.dumps(val))
            
            # Set timestamp
            if isinstance(timestamp, str):
                timestamp = self.parser.parse(timestamp)
            if isinstance(timestamp, datetime.datetime):
                point = point.time(timestamp, self.WritePrecision.NS)
            
            # Write to InfluxDB
            self.write_api.write(
                bucket=config.INFLUXDB_BUCKET,
                org=config.INFLUXDB_ORG,
                record=point
            )
            return True
        except Exception as e:
            logger.error(f"Error storing sensor data in InfluxDB: {e}")
            return False
    
    def store_sensor_data_batch(self, readings):
        """Store multiple sensor readings in a batch"""
        if not self._influxdb_available:
            return False
            
        try:
            points = []
            
            for reading in readings:
                # Create a Point
                point = self.Point(reading['sensor_type'])
                
                # Add tags
                point = point.tag("device_id", str(reading['device_id']))
                
                # Add fields
                point = point.field("value", float(reading['value']))
                if 'unit' in reading and reading['unit']:
                    point = point.field("unit", reading['unit'])
                
                # Add metadata as tags/fields
                if 'metadata' in reading and reading['metadata']:
                    for key, val in reading['metadata'].items():
                        if isinstance(val, (int, float, bool, str)):
                            point = point.tag(key, str(val))
                        else:
                            # Store complex objects as JSON string in fields
                            point = point.field(key, json.dumps(val))
                
                # Set timestamp
                timestamp = reading['timestamp']
                if isinstance(timestamp, str):
                    timestamp = self.parser.parse(timestamp)
                if isinstance(timestamp, datetime.datetime):
                    point = point.time(timestamp, self.WritePrecision.NS)
                
                points.append(point)
            
            # Write batch of points
            self.write_api.write(
                bucket=config.INFLUXDB_BUCKET,
                org=config.INFLUXDB_ORG,
                record=points
            )
            return True
        except Exception as e:
            logger.error(f"Error storing batch sensor data in InfluxDB: {e}")
            return False
            
    def store_valve_state(self, timestamp, sector_id, state, metadata=None):
        """Store a valve state change in InfluxDB v2.x"""
        if not self._influxdb_available:
            return False
            
        try:
            # Create a Point
            point = self.Point("valve_state")
            
            # Add tags
            point = point.tag("sector_id", sector_id)
            
            # Add fields
            point = point.field("state", state)
            
            # Add metadata as tags/fields
            if metadata:
                for key, val in metadata.items():
                    if isinstance(val, (int, float, bool, str)):
                        point = point.tag(key, str(val))
                    else:
                        point = point.field(key, json.dumps(val))
            
            # Set timestamp
            if isinstance(timestamp, str):
                timestamp = self.parser.parse(timestamp)
            if isinstance(timestamp, datetime.datetime):
                point = point.time(timestamp, self.WritePrecision.NS)
            
            # Write to InfluxDB
            self.write_api.write(
                bucket=config.INFLUXDB_BUCKET,
                org=config.INFLUXDB_ORG,
                record=point
            )
            return True
        except Exception as e:
            logger.error(f"Error storing valve state in InfluxDB: {e}")
            return False
    
    def get_sensor_data(self, device_id, sensor_type, start_time, end_time):
        """Retrieve sensor data for a specific device and sensor type within a time range"""
        if not self._influxdb_available:
            return []
            
        try:
            # Format time ranges for InfluxDB Flux query
            if isinstance(start_time, datetime.datetime):
                start_time_str = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
            else:
                start_time_str = start_time
                
            if isinstance(end_time, datetime.datetime):
                end_time_str = end_time.strftime('%Y-%m-%dT%H:%M:%SZ')
            else:
                end_time_str = end_time
            
            # Create Flux query
            query = f'''
                from(bucket: "{config.INFLUXDB_BUCKET}")
                    |> range(start: {start_time_str}, stop: {end_time_str})
                    |> filter(fn: (r) => r._measurement == "{sensor_type}")
                    |> filter(fn: (r) => r.device_id == "{device_id}")
            '''
            
            # Execute query
            tables = self.query_api.query(query, org=config.INFLUXDB_ORG)
            
            # Process results
            data = []
            for table in tables:
                for record in table.records:
                    item = {
                        "timestamp": record.get_time().isoformat(),
                        "device_id": record.values.get("device_id"),
                        "sensor_type": sensor_type,
                        "value": record.get_value()
                    }
                    
                    # Add other fields
                    for key, value in record.values.items():
                        if key not in ("_time", "_value", "_field", "_measurement", "device_id"):
                            item[key] = value
                    
                    data.append(item)
                    
            return data
        except Exception as e:
            logger.error(f"Error retrieving sensor data from InfluxDB: {e}")
            return []
    
    def get_valve_states(self, sector_id, start_time, end_time):
        """Retrieve valve state changes for a specific sector within a time range"""
        if not self._influxdb_available:
            return []
            
        try:
            # Format time ranges for InfluxDB Flux query
            if isinstance(start_time, datetime.datetime):
                start_time_str = start_time.strftime('%Y-%m-%dT%H:%M:%SZ')
            else:
                start_time_str = start_time
                
            if isinstance(end_time, datetime.datetime):
                end_time_str = end_time.strftime('%Y-%m-%dT%H:%M:%SZ')
            else:
                end_time_str = end_time
            
            # Create Flux query
            query = f'''
                from(bucket: "{config.INFLUXDB_BUCKET}")
                    |> range(start: {start_time_str}, stop: {end_time_str})
                    |> filter(fn: (r) => r._measurement == "valve_state")
                    |> filter(fn: (r) => r.sector_id == "{sector_id}")
            '''
            
            # Execute query
            tables = self.query_api.query(query, org=config.INFLUXDB_ORG)
            
            # Process results
            data = []
            for table in tables:
                for record in table.records:
                    item = {
                        "timestamp": record.get_time().isoformat(),
                        "sector_id": record.values.get("sector_id"),
                        "state": record.get_value()
                    }
                    
                    # Add other fields
                    for key, value in record.values.items():
                        if key not in ("_time", "_value", "_field", "_measurement", "sector_id"):
                            item[key] = value
                    
                    data.append(item)
                    
            return data
        except Exception as e:
            logger.error(f"Error retrieving valve states from InfluxDB: {e}")
            return []
    
    def close(self):
        """Close InfluxDB client connection"""
        if self._influxdb_available:
            try:
                self.client.close()
                logger.info("InfluxDB connection closed")
            except Exception as e:
                logger.error(f"Error closing InfluxDB connection: {e}")


class TimescaleDBStorage(TimeSeriesStorage):
    """TimescaleDB implementation of time series data storage"""
    
    def __init__(self):
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            
            self.conn = psycopg2.connect(
                host=config.TIMESCALEDB_HOST,
                port=config.TIMESCALEDB_PORT,
                user=config.TIMESCALEDB_USER,
                password=config.TIMESCALEDB_PASSWORD,
                dbname=config.TIMESCALEDB_DATABASE
            )
            
            self.conn.autocommit = False
            self.cursor_factory = RealDictCursor
            
            self._initialize_db()
            logger.info(f"Connected to TimescaleDB at {config.TIMESCALEDB_HOST}:{config.TIMESCALEDB_PORT}")
            self._timescaledb_available = True
        except ImportError:
            logger.error("psycopg2 not installed. Install using 'pip install psycopg2-binary'")
            self._timescaledb_available = False
        except Exception as e:
            logger.error(f"Failed to connect to TimescaleDB: {e}")
            self._timescaledb_available = False
    
    def _initialize_db(self):
        """Initialize the TimescaleDB with required tables and hypertables"""
        if not self._timescaledb_available:
            return
            
        try:
            cursor = self.conn.cursor()
            
            # Create extension if it doesn't exist (requires superuser)
            try:
                cursor.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
            except Exception as e:
                logger.warning(f"Could not create TimescaleDB extension (may require superuser): {e}")
            
            # Create sensor readings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sensor_readings (
                    time TIMESTAMPTZ NOT NULL,
                    device_id TEXT NOT NULL,
                    sensor_type TEXT NOT NULL,
                    value DOUBLE PRECISION NOT NULL,
                    unit TEXT,
                    metadata JSONB
                );
            """)
            
            # Create valve states table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS valve_states (
                    time TIMESTAMPTZ NOT NULL,
                    sector_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    metadata JSONB
                );
            """)
            
            # Create hypertables if not already created
            try:
                cursor.execute("SELECT create_hypertable('sensor_readings', 'time', if_not_exists => TRUE);")
                cursor.execute("SELECT create_hypertable('valve_states', 'time', if_not_exists => TRUE);")
            except Exception as e:
                logger.warning(f"Could not create hypertables (TimescaleDB may not be installed correctly): {e}")
            
            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_sensor_device_type_time 
                ON sensor_readings (device_id, sensor_type, time DESC);
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_valve_sector_time 
                ON valve_states (sector_id, time DESC);
            """)
            
            self.conn.commit()
            logger.info("TimescaleDB initialized")
        except Exception as e:
            self.conn.rollback()
            logger.error(f"TimescaleDB initialization error: {e}")
    
    def store_sensor_data(self, timestamp, device_id, sensor_type, value, unit, metadata=None):
        """Store a single sensor reading in TimescaleDB"""
        if not self._timescaledb_available:
            return False
            
        try:
            cursor = self.conn.cursor()
            
            # Handle timestamp
            if isinstance(timestamp, str):
                timestamp = timestamp  # TimescaleDB can handle ISO format strings
            elif isinstance(timestamp, datetime.datetime):
                timestamp = timestamp
            else:
                timestamp = datetime.datetime.now().isoformat()
            
            # Convert metadata to JSONB if provided
            if metadata:
                import json
                metadata_json = json.dumps(metadata)
            else:
                metadata_json = None
            
            cursor.execute(
                """INSERT INTO sensor_readings 
                   (time, device_id, sensor_type, value, unit, metadata) 
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (timestamp, str(device_id), sensor_type, value, unit, metadata_json)
            )
            
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error storing sensor data in TimescaleDB: {e}")
            return False
    
    def store_sensor_data_batch(self, readings):
        """Store multiple sensor readings in a batch"""
        if not self._timescaledb_available:
            return False
            
        try:
            cursor = self.conn.cursor()
            
            for reading in readings:
                # Handle timestamp
                timestamp = reading['timestamp']
                if isinstance(timestamp, str):
                    timestamp = timestamp  # TimescaleDB can handle ISO format strings
                elif not isinstance(timestamp, datetime.datetime):
                    timestamp = datetime.datetime.now().isoformat()
                
                # Convert metadata to JSONB if provided
                metadata_json = None
                if 'metadata' in reading and reading['metadata']:
                    metadata_json = json.dumps(reading['metadata'])
                
                cursor.execute(
                    """INSERT INTO sensor_readings 
                       (time, device_id, sensor_type, value, unit, metadata) 
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (timestamp, str(reading['device_id']), reading['sensor_type'], 
                     reading['value'], reading.get('unit'), metadata_json)
                )
            
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error storing batch sensor data in TimescaleDB: {e}")
            return False
            
    def store_valve_state(self, timestamp, sector_id, state, metadata=None):
        """Store a valve state change in TimescaleDB"""
        if not self._timescaledb_available:
            return False
            
        try:
            cursor = self.conn.cursor()
            
            # Handle timestamp
            if isinstance(timestamp, str):
                timestamp = timestamp  # TimescaleDB can handle ISO format strings
            elif isinstance(timestamp, datetime.datetime):
                timestamp = timestamp
            else:
                timestamp = datetime.datetime.now().isoformat()
            
            # Convert metadata to JSONB if provided
            if metadata:
                metadata_json = json.dumps(metadata)
            else:
                metadata_json = None
            
            cursor.execute(
                """INSERT INTO valve_states 
                   (time, sector_id, state, metadata) 
                   VALUES (%s, %s, %s, %s)""",
                (timestamp, sector_id, state, metadata_json)
            )
            
            self.conn.commit()
            return True
        except Exception as e:
            self.conn.rollback()
            logger.error(f"Error storing valve state in TimescaleDB: {e}")
            return False
    
    def get_sensor_data(self, device_id, sensor_type, start_time, end_time):
        """Retrieve sensor data for a specific device and sensor type within a time range"""
        if not self._timescaledb_available:
            return []
            
        try:
            cursor = self.conn.cursor(cursor_factory=self.cursor_factory)
            
            # Handle timestamp formats
            if isinstance(start_time, datetime.datetime):
                start_time = start_time.isoformat()
            if isinstance(end_time, datetime.datetime):
                end_time = end_time.isoformat()
            
            cursor.execute(
                """SELECT time as timestamp, device_id, sensor_type, value, unit, metadata 
                   FROM sensor_readings 
                   WHERE device_id = %s AND sensor_type = %s AND time BETWEEN %s AND %s 
                   ORDER BY time""",
                (str(device_id), sensor_type, start_time, end_time)
            )
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error retrieving sensor data from TimescaleDB: {e}")
            return []
    
    def get_valve_states(self, sector_id, start_time, end_time):
        """Retrieve valve state changes for a specific sector within a time range"""
        if not self._timescaledb_available:
            return []
            
        try:
            cursor = self.conn.cursor(cursor_factory=self.cursor_factory)
            
            # Handle timestamp formats
            if isinstance(start_time, datetime.datetime):
                start_time = start_time.isoformat()
            if isinstance(end_time, datetime.datetime):
                end_time = end_time.isoformat()
            
            cursor.execute(
                """SELECT time as timestamp, sector_id, state, metadata 
                   FROM valve_states 
                   WHERE sector_id = %s AND time BETWEEN %s AND %s 
                   ORDER BY time""",
                (sector_id, start_time, end_time)
            )
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error retrieving valve states from TimescaleDB: {e}")
            return []
    
    def close(self):
        """Close database connections"""
        if self._timescaledb_available:
            try:
                self.conn.close()
                logger.info("TimescaleDB connection closed")
            except Exception as e:
                logger.error(f"Error closing TimescaleDB connection: {e}")


def get_storage():
    """Factory function to get the appropriate storage implementation based on configuration"""
    storage_type = config.STORAGE_TYPE.lower()
    
    if storage_type == "influxdb":
        return InfluxDBStorage()
    elif storage_type == "timescaledb":
        return TimescaleDBStorage()
    else:  # Default to SQLite
        return SQLiteStorage()