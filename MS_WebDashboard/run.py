#!/usr/bin/env python3

import os
import sys
import time
import requests
import logging
from app import app, server
import config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('web_dashboard')

def register_with_catalog():
    try:
        service_data = {
            "id": config.SERVICE_ID,
            "name": config.SERVICE_NAME,
            "description": config.SERVICE_DESCRIPTION,
            "type": config.SERVICE_TYPE,
            "endpoints": [
                {
                    "type": "http",
                    "url": f"http://localhost:{config.PORT}"
                }
            ],
            "status": "online"
        }
        
        response = requests.post(
            f"{config.RESOURCE_CATALOG_URL}/services",
            json=service_data
        )
        
        if response.status_code in (200, 201):
            logger.info("Successfully registered with Resource Catalog")
            return True
        else:
            logger.error(f"Failed to register with Resource Catalog: {response.status_code} {response.text}")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Error connecting to Resource Catalog: {e}")
        return False

def registration_loop():
    while True:
        register_with_catalog()
        time.sleep(config.REGISTRATION_INTERVAL)

if __name__ == "__main__":
    try:
        import threading
        registration_thread = threading.Thread(target=registration_loop, daemon=True)
        registration_thread.start()
        
        print(f"Starting Web Dashboard on port {config.PORT}...")
        app.run_server(debug=config.DEBUG, host='0.0.0.0', port=config.PORT)
    except KeyboardInterrupt:
        print("Shutting down Web Dashboard...")
        sys.exit(0) 