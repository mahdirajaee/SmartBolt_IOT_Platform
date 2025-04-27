#!/usr/bin/env python3

import time
import random
import json
import logging
import requests
from datetime import datetime
import config
from storage import StorageManager

if config.USE_MQTT:
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("MQTT enabled but paho-mqtt not installed. Run: pip install paho-mqtt")
        config.USE_MQTT = False

if config.LOGGING_ENABLED:
    logging.basicConfig(
        filename=config.LOG_FILE,
        level=getattr(logging, config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger('sensor_simulator')
else:
    logger = logging.getLogger('sensor_simulator')
    logger.addHandler(logging.NullHandler())

class SensorSimulator:
    def __init__(self):
        self.last_reading_time = None
        self.storage = StorageManager()
        
        if config.USE_MQTT:
            self.mqtt_client = mqtt.Client(config.MQTT_CLIENT_ID)
            if config.MQTT_USERNAME and config.MQTT_PASSWORD:
                self.mqtt_client.username_pw_set(config.MQTT_USERNAME, config.MQTT_PASSWORD)
            
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
            
            try:
                self.mqtt_client.connect(config.MQTT_BROKER, config.MQTT_PORT)
                self.mqtt_client.loop_start()
                logger.info(f"Connected to MQTT broker at {config.MQTT_BROKER}:{config.MQTT_PORT}")
            except Exception as e:
                logger.error(f"Failed to connect to MQTT broker: {e}")
                config.USE_MQTT = False
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("MQTT connection established")
        else:
            logger.error(f"MQTT connection failed with code {rc}")
    
    def _on_mqtt_disconnect(self, client, userdata, rc):
        logger.warning(f"MQTT connection lost with code {rc}")
        
    def generate_temperature(self):
        if config.RANDOM_VARIATION:
            variation = random.uniform(-config.TEMP_VARIATION, config.TEMP_VARIATION)
            temperature = config.TEMP_BASE_VALUE + variation
        else:
            temperature = config.TEMP_BASE_VALUE
            
        temperature = max(config.TEMP_MIN, min(config.TEMP_MAX, temperature))
        return int(temperature)
    
    def generate_pressure(self):
        if config.RANDOM_VARIATION:
            variation = random.uniform(-config.PRESSURE_VARIATION, config.PRESSURE_VARIATION)
            pressure = config.PRESSURE_BASE_VALUE + variation
        else:
            pressure = config.PRESSURE_BASE_VALUE
            
        pressure = max(config.PRESSURE_MIN, min(config.PRESSURE_MAX, pressure))
        return int(pressure)
    
    def get_sensor_readings(self, device_id=None):
        timestamp = datetime.now().isoformat()
        temperature = self.generate_temperature()
        pressure = self.generate_pressure()
        
        device_info = {}
        sector_info = {}
        
        if device_id:
            device = self.storage.get_device(device_id)
            if device:
                sector_id = device.sector_id
                sector = self.storage.get_sector(sector_id)
                
                device_info = {
                    "device_id": device_id,
                    "sector_id": sector_id,
                    "name": device.name
                }
                
                # Include valve information for the sector
                if sector:
                    sector_info = {
                        "sector_id": sector_id,
                        "name": sector.name,
                        "valve_state": sector.valve.state
                    }
        
        data = {
            "timestamp": timestamp,
            "device_id": device_id if device_id else "raspberrypi_simulator",
            "device_info": device_info,
            "sector_info": sector_info,  # Include sector and valve information
            "readings": {
                "temperature": {
                    "value": temperature,
                    "unit": "celsius"
                },
                "pressure": {
                    "value": pressure,
                    "unit": "hPa"
                }
            }
        }
        
        self.last_reading_time = timestamp
        logger.debug(f"Generated readings: Temp={temperature}°C, Pressure={pressure}hPa")
        return data
    
    def send_data_http(self, data):
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.API_KEY}"
        }
        
        try:
            response = requests.post(
                config.SERVER_URL,
                headers=headers,
                data=json.dumps(data),
                timeout=10
            )
            
            if response.status_code == 200:
                # Simplified success message without HTTP details
                print("✓ Data sent successfully")
                logger.info(f"Data sent successfully via HTTP: {response.status_code}")
                return True
            else:
                logger.error(f"Failed to send data via HTTP. Status code: {response.status_code}, Response: {response.text}")
                print(f"✗ Failed to send data: {response.status_code}")
                return False
                
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP request error: {e}")
            print(f"✗ HTTP request error: {str(e)[:50]}...")
            return False
    
    def send_data_mqtt(self, data):
        try:
            result = self.mqtt_client.publish(
                config.MQTT_TOPIC,
                json.dumps(data),
                qos=1
            )
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info("Data sent successfully via MQTT")
                return True
            else:
                logger.error(f"Failed to send data via MQTT. Error code: {result.rc}")
                return False
                
        except Exception as e:
            logger.error(f"MQTT publish error: {e}")
            return False
    
    def update_device_readings(self, device_id, temperature, pressure):
        try:
            self.storage.update_device_reading(device_id, "temperature", temperature)
            self.storage.update_device_reading(device_id, "pressure", pressure)
            return True
        except Exception as e:
            logger.error(f"Failed to update device readings: {e}")
            return False
    
    def run_single_device(self, device_id):
        device = self.storage.get_device(device_id)
        if not device:
            logger.error(f"Device {device_id} not found")
            return False
            
        logger.info(f"Starting sensor simulator for device {device_id} ({device.name}) in sector {device.sector_id}")
        print(f"\n SMART BOLT SENSOR SIMULATOR")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f" Device: {device_id} ({device.name})")
        print(f" Interval: {config.SIMULATION_INTERVAL} seconds")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        try:
            while True:
                sensor_data = self.get_sensor_readings(device_id)
                
                temp = sensor_data["readings"]["temperature"]["value"]
                press = sensor_data["readings"]["pressure"]["value"]
                
                # Get sector and valve information
                sector = self.storage.get_sector(device.sector_id)
                valve_state = sector.valve.state if sector else "unknown"
                
                print(f"\n  {datetime.now().strftime('%H:%M:%S')}")
                print(f" Device: {device_id} ({device.name}) - Sector {device.sector_id}")
                print(f"  Temperature: {temp}°C |  Pressure: {press}hPa |  Valve: {valve_state}")
                
                self.update_device_readings(device_id, temp, press)
                
                if config.USE_MQTT:
                    self.send_data_mqtt(sensor_data)
                else:
                    self.send_data_http(sensor_data)
                
                time.sleep(config.SIMULATION_INTERVAL)
                
        except KeyboardInterrupt:
            logger.info(f"Simulator stopped for device {device_id}")
            print("\n Simulator stopped")
            if config.USE_MQTT and hasattr(self, 'mqtt_client'):
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
    
    def run_all_devices(self):
        devices = self.storage.get_all_devices()
        if not devices:
            logger.warning("No devices found in storage")
            print("No devices found. Please add devices first.")
            return
        
        logger.info(f"Starting sensor simulator for {len(devices)} devices")
        print(f"\n SMART BOLT SENSOR SIMULATOR")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f" Devices: {len(devices)} active")
        print(f" Interval: {config.SIMULATION_INTERVAL} seconds")
        print(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        
        try:
            while True:
                print(f"\n  {datetime.now().strftime('%H:%M:%S')}")
                
                # Display valve status for each sector
                sectors = self.storage.get_all_sectors()
                print(" SECTOR VALVE STATES:")
                for sector in sectors:
                    print(f"  Sector {sector.sector_id} ({sector.name}): Valve {sector.valve.state}")
                print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
                
                for device in devices:
                    sensor_data = self.get_sensor_readings(device.device_id)
                    
                    temp = sensor_data["readings"]["temperature"]["value"]
                    press = sensor_data["readings"]["pressure"]["value"]
                    
                    self.update_device_readings(device.device_id, temp, press)
                    
                    sector_id = device.sector_id
                    sector = self.storage.get_sector(sector_id)
                    valve_state = sector.valve.state if sector else "unknown"
                    
                    print(f" Device: {device.device_id} ({device.name}) - Sector {device.sector_id}")
                    print(f"    Temperature: {temp}°C |  Pressure: {press}hPa |  Valve: {valve_state}")
                    
                    if config.USE_MQTT:
                        self.send_data_mqtt(sensor_data)
                    else:
                        self.send_data_http(sensor_data)
                
                time.sleep(config.SIMULATION_INTERVAL)
                
        except KeyboardInterrupt:
            logger.info("Simulator stopped")
            print("\n Simulator stopped")
            if config.USE_MQTT and hasattr(self, 'mqtt_client'):
                self.mqtt_client.loop_stop()
                self.mqtt_client.disconnect()
    
    def run(self, device_id=None):
        if device_id:
            self.run_single_device(device_id)
        else:
            self.run_all_devices()

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Raspberry Pi Sensor Simulator')
    parser.add_argument('--device', type=int, help='Device ID to simulate (optional)')
    args = parser.parse_args()
    
    simulator = SensorSimulator()
    simulator.run(args.device)