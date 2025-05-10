
import requests
import logging
import json
import threading
import time
import socket
import config


logger = logging.getLogger('registration')
if config.LOGGING_ENABLED:
    logger.setLevel(getattr(logging, config.LOG_LEVEL))
    handler = logging.FileHandler(config.LOG_FILE)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
else:
    logger.addHandler(logging.NullHandler())

def get_local_ip():
    """Get the local IP address of this machine"""
    try:
        
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Connect to Google DNS
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception as e:
        logger.error(f"Error getting local IP: {e}")
        return "127.0.0.1"  

def register_with_catalog():
    """Register this Account Manager service with the Resource Catalog"""
    try:
        
        local_ip = get_local_ip()
        
        service_data = {
            "service_id": config.SERVICE_ID,
            "name": config.SERVICE_NAME,
            "description": config.SERVICE_DESCRIPTION,
            "service_type": config.SERVICE_TYPE,
            "endpoints": {
                "http": f"http://{local_ip}:{config.API_PORT}/",
                "auth": f"http://{local_ip}:{config.API_PORT}/auth"
            },
            "required_inputs": {
                "login": "Username and password for authentication",
                "register": "User registration information"
            },
            "provided_outputs": {
                "authentication": "User authentication and authorization services",
                "user_management": "User account management services"
            },
            "status": "online"
        }
        
        
        catalog_url = f"{config.RESOURCE_CATALOG_URL}/register_service"
        logger.info(f"Registering with Resource Catalog at {catalog_url}")
        
        response = requests.post(
            catalog_url,
            json=service_data,
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
    """Update the status of this service in the Resource Catalog"""
    try:
        status_data = {
            "service_id": config.SERVICE_ID,
            "status": status
        }
        
        
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

def registration_worker():
    """Background worker that periodically re-registers with the Resource Catalog"""
    while True:
        try:
            register_with_catalog()
        except Exception as e:
            logger.error(f"Error in registration worker: {e}")
        
        
        time.sleep(config.REGISTRATION_INTERVAL)

def start_registration(background=True):
    """Start the registration process with the Resource Catalog"""
    
    success = register_with_catalog()
    
    if background:
        
        registration_thread = threading.Thread(
            target=registration_worker,
            daemon=True
        )
        registration_thread.start()
        logger.info("Registration service started in background")
    
    return success