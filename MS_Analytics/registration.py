#!/usr/bin/env python3

import requests
import logging
import json
import threading
import time
import socket
import config

# Set up logging
logger = logging.getLogger('registration')

def get_local_ip():
    """Get the local IP address of this machine"""
    try:
        # Create a socket and connect to an external server
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        logger.error(f"Error getting local IP: {e}")
        return "localhost"

def register_with_catalog():
    """Register this Analytics service with the Resource Catalog"""
    try:
        # Check if Resource Catalog is reachable first
        try:
            health_check = requests.get(config.RESOURCE_CATALOG_URL, timeout=2)
            if health_check.status_code >= 400:
                logger.error(f"Resource Catalog appears to be offline or not responding properly: Status code {health_check.status_code}, Response: {health_check.text}")
                return False
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Resource Catalog at {config.RESOURCE_CATALOG_URL} is not reachable: Connection Error: {str(e)}")
            return False
        except requests.exceptions.Timeout as e:
            logger.error(f"Resource Catalog at {config.RESOURCE_CATALOG_URL} timed out: {str(e)}")
            return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Resource Catalog at {config.RESOURCE_CATALOG_URL} request failed: {str(e)}")
            return False
            
        # Prepare service registration details
        local_ip = get_local_ip()
        port = config.API_PORT  # Use port from config file
        
        service_data = {
            "service_id": config.SERVICE_ID,
            "name": config.SERVICE_NAME,
            "description": config.SERVICE_DESCRIPTION,
            "service_type": config.SERVICE_TYPE,
            "endpoints": {
                "api": f"http://{local_ip}:{port}/api",
                "alerts": f"http://{local_ip}:{port}/api/alerts"
            },
            "required_inputs": {
                "sensor_data": "Historical temperature and pressure data"
            },
            "provided_outputs": {
                "predictions": "Forecasted temperature and pressure values",
                "alerts": "Hazard notifications based on predictions"
            },
            "status": "online"
        }
        
        # Send registration request to Resource Catalog
        catalog_url = f"{config.RESOURCE_CATALOG_URL}/register_service"
        logger.info(f"Registering with Resource Catalog at {catalog_url}")
        logger.debug(f"Sending registration data: {json.dumps(service_data)}")
        
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
                logger.error(f"Raw response content: {response.text}")
        else:
            logger.error(f"Registration failed with status code {response.status_code}")
            logger.error(f"Response content: {response.text}")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error during registration: {str(e)}")
    except Exception as e:
        logger.error(f"Error during registration: {str(e)}", exc_info=True)
        
    return False

def update_status(status="online"):
    """Update the status of this service in the Resource Catalog"""
    try:
        status_data = {
            "service_id": config.SERVICE_ID,
            "status": status
        }
        
        # Send status update request to Resource Catalog
        catalog_url = f"{config.RESOURCE_CATALOG_URL}/update_service_status"
        
        response = requests.post(
            catalog_url,
            json=status_data,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        
        if response.status_code == 200:
            logger.debug(f"Status update to '{status}' successful")
            return True
        else:
            logger.warning(f"Status update failed with status code {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error during status update: {e}")
    except Exception as e:
        logger.error(f"Error during status update: {e}")
        
    return False

def discover_services():
    """Discover other services from the Resource Catalog"""
    try:
        # Query the Resource Catalog for the timeseries_db_connector
        catalog_url = f"{config.RESOURCE_CATALOG_URL}/service?service_id=timeseries_db_connector"
        
        response = requests.get(
            catalog_url,
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                service_data = data.get("data")
                logger.info(f"Discovered Time Series DB service: {service_data}")
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

def registration_worker():
    """Background worker that periodically re-registers with the Resource Catalog"""
    while True:
        try:
            register_with_catalog()
        except Exception as e:
            logger.error(f"Error in registration worker: {e}")
        
        # Sleep for the configured interval before re-registering
        time.sleep(config.REGISTRATION_INTERVAL)

def start_registration(background=True):
    """Start the registration process with the Resource Catalog"""
    # First registration attempt
    success = register_with_catalog()
    
    # Discover other services
    service_data = discover_services()
    if service_data and service_data.get("endpoints"):
        endpoints = service_data.get("endpoints")
        
        # Configure MQTT settings if available
        if "mqtt" in endpoints:
            mqtt_url = endpoints["mqtt"]
            # Parse MQTT URL (e.g., mqtt://localhost:1883)
            parts = mqtt_url.split("://")[1].split(":")
            config.MQTT_HOST = parts[0]
            config.MQTT_PORT = int(parts[1])
            logger.info(f"Configured MQTT settings: {config.MQTT_HOST}:{config.MQTT_PORT}")
            
        # Configure Time Series DB API URL if available
        if "api" in endpoints:
            config.TIMESERIES_DB_API_URL = endpoints["api"]
            logger.info(f"Configured Time Series DB API URL: {config.TIMESERIES_DB_API_URL}")
        else:
            logger.error("Failed to discover Time Series DB API URL from Resource Catalog")
    
    if background:
        # Start background thread for periodic re-registration (heartbeat)
        registration_thread = threading.Thread(
            target=registration_worker,
            daemon=True
        )
        registration_thread.start()
        logger.info("Registration service started in background")
    
    return success