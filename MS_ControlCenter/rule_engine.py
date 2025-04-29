#!/usr/bin/env python3

import logging
import config
import json
from datetime import datetime

logger = logging.getLogger('rule_engine')

class Rule:
    def __init__(self, rule_id, description, condition, action):
        self.id = rule_id
        self.description = description
        self.condition = condition
        self.action = action
        self.last_triggered = None
        self.cooldown = 60

    def evaluate(self, sensor_data):
        temperature = sensor_data.get('temperature', 0)
        pressure = sensor_data.get('pressure', 0)
        
        result = eval(self.condition, 
                     {"temperature": temperature, 
                      "pressure": pressure,
                      "TEMPERATURE_THRESHOLD": config.TEMPERATURE_THRESHOLD,
                      "PRESSURE_THRESHOLD": config.PRESSURE_THRESHOLD})
        
        if result:
            current_time = datetime.now()
            
            if (self.last_triggered is None or 
                (current_time - self.last_triggered).total_seconds() > self.cooldown):
                self.last_triggered = current_time
                return True
            
        return False


class RuleEngine:
    def __init__(self):
        self.rules = []
        self.load_default_rules()
        
    def load_default_rules(self):
        for rule_config in config.DEFAULT_RULES:
            rule = Rule(
                rule_id=rule_config['id'],
                description=rule_config['description'],
                condition=rule_config['condition'],
                action=rule_config['action']
            )
            self.rules.append(rule)
        logger.info(f"Loaded {len(self.rules)} default rules")
    
    def add_rule(self, rule_config):
        rule = Rule(
            rule_id=rule_config['id'],
            description=rule_config['description'],
            condition=rule_config['condition'],
            action=rule_config['action']
        )
        self.rules.append(rule)
        logger.info(f"Added new rule: {rule.id}")
        return rule.id
        
    def remove_rule(self, rule_id):
        initial_count = len(self.rules)
        self.rules = [rule for rule in self.rules if rule.id != rule_id]
        if len(self.rules) < initial_count:
            logger.info(f"Removed rule: {rule_id}")
            return True
        return False
    
    def get_rules(self):
        return [
            {
                "id": rule.id,
                "description": rule.description,
                "condition": rule.condition,
                "action": rule.action,
                "last_triggered": rule.last_triggered.isoformat() if rule.last_triggered else None
            }
            for rule in self.rules
        ]
    
    def evaluate_rules(self, device_id, sensor_data):
        triggered_rules = []
        
        for rule in self.rules:
            if rule.evaluate(sensor_data):
                logger.info(f"Rule triggered: {rule.id} for device {device_id}")
                triggered_rules.append({
                    "rule_id": rule.id,
                    "action": rule.action,
                    "device_id": device_id,
                    "sensor_data": sensor_data
                })
                
        return triggered_rules