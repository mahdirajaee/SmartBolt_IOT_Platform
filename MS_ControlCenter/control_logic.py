#!/usr/bin/env python3

import logging
import threading
import json
import time
from datetime import datetime
import requests

import config
from rule_engine import RuleEngine
from mqtt_handler import MQTTHandler

logger = logging.getLogger('control_logic')

class ControlLogic:
    def __init__(self):
        self.rule_engine = RuleEngine()
        self.mqtt_handler = MQTTHandler(
            sensor_callback=self.process_sensor_data,
            valve_status_callback=self.process_valve_status
        )
        self.valve_states = {}
        self.sensor_data_cache = {}
        
    def start(self):
        logger.info("Starting Control Logic")
        mqtt_success = self.mqtt_handler.start()
        if mqtt_success:
            logger.info("MQTT handler connected successfully")
            return True
        else:
            logger.error("Failed to connect to MQTT broker, control logic will run with limited functionality")
            return False
        
    def stop(self):
        logger.info("Stopping Control Logic")
        return self.mqtt_handler.stop()
        
    def process_sensor_data(self, data):
        try:
            device_id = data.get('device_id', 'unknown')
            readings = data.get('readings', {})
            timestamp = data.get('timestamp', datetime.now().isoformat())
            
            sector_id = data.get('sector_id', 'A')  # Default to sector A if not specified
            
            temperature = readings.get('temperature', {}).get('value')
            pressure = readings.get('pressure', {}).get('value')
            
            if temperature is None and pressure is None:
                logger.warning("Sensor data missing temperature and pressure readings")
                return
                
            sensor_values = {}
            if temperature is not None:
                sensor_values['temperature'] = temperature
            if pressure is not None:
                sensor_values['pressure'] = pressure
                
            # Cache the sensor data
            self.sensor_data_cache[device_id] = {
                'sector_id': sector_id,
                'timestamp': timestamp,
                'values': sensor_values
            }
            
            logger.debug(f"Processing sensor data: Device {device_id}, Temp: {temperature}, Pressure: {pressure}")
            
            # Evaluate rules based on sensor data
            triggered_rules = self.rule_engine.evaluate_rules(device_id, sensor_values)
            
            # Process any triggered rules
            self.handle_triggered_rules(triggered_rules)
                
        except Exception as e:
            logger.error(f"Error processing sensor data: {e}")
            
    def process_valve_status(self, data):
        try:
            sector_id = data.get('sector_id', 'unknown')
            valve_state = data.get('valve_state', 'unknown')
            timestamp = data.get('timestamp', datetime.now().isoformat())
            
            logger.info(f"Received valve status update: Sector {sector_id}, State: {valve_state}")
            
            self.valve_states[sector_id] = {
                'state': valve_state,
                'last_updated': timestamp
            }
                
        except Exception as e:
            logger.error(f"Error processing valve status: {e}")
            
    def handle_triggered_rules(self, triggered_rules):
        for rule_data in triggered_rules:
            rule_id = rule_data['rule_id']
            action = rule_data['action']
            device_id = rule_data['device_id']
            sensor_data = rule_data['sensor_data']
            
            # Get the sector ID from the cached data
            sector_id = self.sensor_data_cache.get(device_id, {}).get('sector_id', 'A')
            
            logger.info(f"Handling triggered rule {rule_id} for device {device_id} in sector {sector_id}")
            
            # Execute action based on the rule
            if action == 'close_valve':
                self.close_valve(sector_id, rule_id, sensor_data)
            elif action == 'open_valve':
                self.open_valve(sector_id, rule_id)
            else:
                logger.warning(f"Unknown action {action} for rule {rule_id}")
                
    def close_valve(self, sector_id, rule_id, sensor_data):
        logger.info(f"Closing valve for sector {sector_id} due to rule {rule_id}")
        
        # Check if the valve is already closed
        current_state = self.valve_states.get(sector_id, {}).get('state')
        if current_state == 'closed':
            logger.info(f"Valve for sector {sector_id} is already closed")
            return True
            
        # Send command to close valve
        success = self.mqtt_handler.publish_valve_command(sector_id, "close")
        
        # Send alert about valve closure
        reason = self.generate_alert_message(rule_id, sensor_data)
        self.mqtt_handler.publish_alert(
            f"Valve in sector {sector_id} was closed: {reason}",
            severity="warning"
        )
        
        return success
        
    def open_valve(self, sector_id, rule_id):
        logger.info(f"Opening valve for sector {sector_id} due to rule {rule_id}")
        
        # Check if the valve is already open
        current_state = self.valve_states.get(sector_id, {}).get('state')
        if current_state == 'open':
            logger.info(f"Valve for sector {sector_id} is already open")
            return True
            
        # Send command to open valve
        success = self.mqtt_handler.publish_valve_command(sector_id, "open")
        
        # Send alert about valve opening
        self.mqtt_handler.publish_alert(
            f"Valve in sector {sector_id} was opened by rule {rule_id}",
            severity="info"
        )
        
        return success
        
    def generate_alert_message(self, rule_id, sensor_data):
        if rule_id == 'high_temperature':
            return f"Temperature too high: {sensor_data.get('temperature', '?')}°C (threshold: {config.TEMPERATURE_THRESHOLD}°C)"
        elif rule_id == 'high_pressure':
            return f"Pressure too high: {sensor_data.get('pressure', '?')} hPa (threshold: {config.PRESSURE_THRESHOLD} hPa)"
        else:
            return f"Rule {rule_id} triggered"
            
    def get_status(self):
        return {
            'valve_states': self.valve_states,
            'sensor_data': self.sensor_data_cache,
            'rules': self.rule_engine.get_rules()
        }
        
    def add_rule(self, rule_config):
        return self.rule_engine.add_rule(rule_config)
        
    def remove_rule(self, rule_id):
        return self.rule_engine.remove_rule(rule_id)
        
    def get_rules(self):
        return self.rule_engine.get_rules()