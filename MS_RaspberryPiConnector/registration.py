#!/usr/bin/env python3

import requests
import logging
import json
import threading
import time
import socket
import config

logger = logging.getLogger('registration')

def get_local_ip():
    """Get the local IP address of this machine"""
    try:
        # Create a socket connection to an external server to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Connect to Google DNS
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        logger.error(f"Error getting local IP: {e}")
        return "127.0.0.1"  # Return localhost if unable to determine IP

def register_with_catalog():
    """Register this Raspberry Pi connector with the Resource Catalog"""
    try:
        # Prepare device registration details
        local_ip = get_local_ip()
        port = 5000  # The port on which the API is running
        
        device_data = {
            "device_id": config.DEVICE_ID,
            "name": config.DEVICE_NAME,
            "description": config.DEVICE_DESCRIPTION,
            "device_type": config.DEVICE_TYPE,
            "endpoints": {
                "api": f"http://{local_ip}:{port}/api",
                "sensor_data": f"http://{local_ip}:{port}/api/sensor-data"
            },
            "sensors": ["temperature", "pressure"],
            "status": "online"
        }
        
        # Send registration request to Resource Catalog
        catalog_url = f"{config.RESOURCE_CATALOG_URL}/register_device"
        logger.info(f"Registering with Resource Catalog at {catalog_url}")
        
        response = requests.post(
            catalog_url,
            json=device_data,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "success":
                logger.info("Registration successful")
                return True
            else:
                logger.error(f"Registration failed: {data.get('message', 'Unknown error')}")
        else:
            logger.error(f"Registration failed with status code {response.status_code}: {response.text}")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error during registration: {e}")
    except Exception as e:
        logger.error(f"Error during registration: {e}")
        
    return False

def update_status(status="online"):
    """Update the status of this device in the Resource Catalog"""
    try:
        status_data = {
            "device_id": config.DEVICE_ID,
            "status": status
        }
        
        # Send status update request to Resource Catalog
        catalog_url = f"{config.RESOURCE_CATALOG_URL}/update_device_status"
        
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
    
    if background:
        # Start background thread for periodic re-registration (heartbeat)
        registration_thread = threading.Thread(
            target=registration_worker,
            daemon=True
        )
        registration_thread.start()
        logger.info("Registration service started in background")
    
    return success