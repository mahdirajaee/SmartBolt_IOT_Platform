#!/usr/bin/env python3

import requests
import json
import logging
import threading
import time
import socket
import config

logger = logging.getLogger('registration')

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        logger.error(f"Error getting local IP: {e}")
        return "localhost"

def register_with_catalog():
    try:
        # Check if Resource Catalog is reachable first
        try:
            health_check = requests.get(config.RESOURCE_CATALOG_URL, timeout=2)
            if health_check.status_code >= 400:
                logger.error(f"Resource Catalog appears to be offline or not responding properly: Status code {health_check.status_code}")
                return False
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Resource Catalog at {config.RESOURCE_CATALOG_URL} is not reachable: {str(e)}")
            return False
        except requests.exceptions.Timeout as e:
            logger.error(f"Resource Catalog at {config.RESOURCE_CATALOG_URL} timed out: {str(e)}")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Resource Catalog at {config.RESOURCE_CATALOG_URL} request failed: {str(e)}")
            return False
            
        # Prepare service registration details
        local_ip = get_local_ip()
        port = config.API_PORT
        
        service_data = {
            "service_id": config.SERVICE_ID,
            "name": config.SERVICE_NAME,
            "description": config.SERVICE_DESCRIPTION,
            "service_type": config.SERVICE_TYPE,
            "endpoints": {
                "api": f"http://{local_ip}:{port}/api",
                "rules": f"http://{local_ip}:{port}/api/rules",
                "status": f"http://{local_ip}:{port}/api/status"
            },
            "required_inputs": {
                "sensor_data": "Real-time temperature and pressure readings"
            },
            "provided_outputs": {
                "valve_control": "Commands to operate valves based on sensor data",
                "alerts": "Notifications for anomalies and automatic actions"
            },
            "status": "online"
        }
        
        # Send registration request to Resource Catalog
        catalog_url = f"{config.RESOURCE_CATALOG_URL}/register_service"
        logger.info(f"Registering with Resource Catalog at {catalog_url}")
        
        response = requests.post(
            catalog_url,
            json=service_data,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        
        if response.status_code == 200:
            try:
                data = response.json()
                if data.get("status") == "success":
                    logger.info("Registration successful")
                    return True
                else:
                    logger.error(f"Registration failed: {data.get('message', 'Unknown error')}")
            except ValueError as e:
                logger.error(f"Failed to parse JSON response from Resource Catalog: {e}")
        else:
            logger.error(f"Registration failed with status code {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error during registration: {str(e)}")
    except Exception as e:
        logger.error(f"Error during registration: {str(e)}")
        
    return False

def discover_services():
    try:
        # Query the Resource Catalog for the message broker
        catalog_url = f"{config.RESOURCE_CATALOG_URL}/service?service_type=message_broker"
        
        response = requests.get(
            catalog_url,
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                service_data = data.get("data")
                logger.info(f"Discovered Message Broker service: {service_data}")
                return service_data
            else:
                logger.error(f"Service discovery failed: {data.get('message', 'Unknown error')}")
        else:
            logger.error(f"Service discovery failed with status code {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error during service discovery: {e}")
    except Exception as e:
        logger.error(f"Error during service discovery: {e}")
        
    return None

def registration_loop():
    while True:
        register_with_catalog()
        time.sleep(config.REGISTRATION_INTERVAL)

def start_registration_thread():
    registration_thread = threading.Thread(target=registration_loop, daemon=True)
    registration_thread.start()
    return registration_thread