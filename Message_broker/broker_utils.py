#!/usr/bin/env python3
"""
Utility functions for the Smart IoT Bolt Message Broker.

This module provides helper functions for MQTT message processing,
data validation, and message transformation.
"""

import json
import time
from typing import Dict, Any, Optional, Union, Tuple


def validate_message_format(payload: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
    """
    Validate that a message payload is properly formatted JSON.
    
    Args:
        payload (str): The message payload to validate
        
    Returns:
        Tuple[bool, Optional[Dict[str, Any]]]: Success status and parsed message if successful
    """
    try:
        message = json.loads(payload)
        return True, message
    except json.JSONDecodeError:
        return False, None


def create_sensor_message(device_id: str, sensor_type: str, value: float, 
                          timestamp: Optional[float] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
    """
    Create a standardized sensor message in JSON format.
    
    Args:
        device_id (str): The unique identifier for the sensor device
        sensor_type (str): The type of sensor (e.g., 'temperature', 'pressure')
        value (float): The sensor reading value
        timestamp (float, optional): The timestamp for the reading. Defaults to current time.
        metadata (Dict[str, Any], optional): Additional metadata for the reading.
        
    Returns:
        str: JSON formatted sensor message
    """
    if timestamp is None:
        timestamp = time.time()
    
    if metadata is None:
        metadata = {}
    
    message = {
        "device_id": device_id,
        "sensor_type": sensor_type,
        "value": value,
        "timestamp": timestamp,
        "metadata": metadata
    }
    
    return json.dumps(message)


def create_actuator_message(device_id: str, actuator_type: str, command: str,
                            timestamp: Optional[float] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
    """
    Create a standardized actuator command message in JSON format.
    
    Args:
        device_id (str): The unique identifier for the actuator device
        actuator_type (str): The type of actuator (e.g., 'valve', 'switch')
        command (str): The command to send to the actuator (e.g., 'open', 'close')
        timestamp (float, optional): The timestamp for the command. Defaults to current time.
        metadata (Dict[str, Any], optional): Additional metadata for the command.
        
    Returns:
        str: JSON formatted actuator command message
    """
    if timestamp is None:
        timestamp = time.time()
    
    if metadata is None:
        metadata = {}
    
    message = {
        "device_id": device_id,
        "actuator_type": actuator_type,
        "command": command,
        "timestamp": timestamp,
        "metadata": metadata
    }
    
    return json.dumps(message)


def parse_topic(topic: str) -> Dict[str, str]:
    """
    Parse an MQTT topic into component parts.
    
    Example: "/sensor/temperature" -> {"category": "sensor", "type": "temperature"}
    
    Args:
        topic (str): The MQTT topic to parse
        
    Returns:
        Dict[str, str]: Dictionary of topic components
    """
    parts = topic.strip('/').split('/')
    result = {}
    
    if len(parts) >= 1:
        result["category"] = parts[0]
    
    if len(parts) >= 2:
        result["type"] = parts[1]
    
    if len(parts) >= 3:
        result["device_id"] = parts[2]
    
    return result


def topic_matches(subscription: str, topic: str) -> bool:
    """
    Check if a topic matches a subscription pattern, handling wildcards.
    
    Args:
        subscription (str): The subscription pattern (can include wildcards)
        topic (str): The actual topic to check
        
    Returns:
        bool: True if the topic matches the subscription pattern
    """
    # Split into parts
    sub_parts = subscription.split('/')
    topic_parts = topic.split('/')
    
    # Different length, only possible match if subscription ends with #
    if len(sub_parts) != len(topic_parts):
        if len(sub_parts) > 0 and sub_parts[-1] == '#':
            # Remove # and check if topic starts with the subscription
            return topic.startswith('/'.join(sub_parts[:-1]))
        return False
    
    # Check each part
    for sp, tp in zip(sub_parts, topic_parts):
        if sp != '+' and sp != '#' and sp != tp:
            return False
    
    return True


def log_message_stats(message: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract statistics from a message for logging purposes.
    
    Args:
        message (Dict[str, Any]): The parsed message
        
    Returns:
        Dict[str, Any]: Message statistics
    """
    stats = {
        "timestamp": message.get("timestamp", time.time()),
        "device_id": message.get("device_id", "unknown"),
    }
    
    if "value" in message:
        stats["value"] = message["value"]
    
    if "command" in message:
        stats["command"] = message["command"]
    
    return stats