#!/usr/bin/env python3
"""
Common utilities for the Smart IoT Bolt system
"""
import os
import json
import logging
import requests
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

# Default resource catalog URL
RESOURCE_CATALOG_URL = os.environ.get("RESOURCE_CATALOG_URL", "http://localhost:8001")

def register_service(name, service_type, base_url, description=""):
    """Register a service with the Resource Catalog"""
    try:
        data = {
            "name": name,
            "type": service_type,
            "base_url": base_url,
            "description": description,
            "timestamp": datetime.now().isoformat()
        }
        
        response = requests.post(
            f"{RESOURCE_CATALOG_URL}/register",
            json=data,
            timeout=5
        )
        
        if response.status_code == 200:
            logger.info(f"Service {name} registered successfully")
            return True
        else:
            logger.error(f"Failed to register service {name}: {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error registering service {name}: {e}")
        return False

def discover_service(service_type):
    """Discover a service by type from the Resource Catalog"""
    try:
        response = requests.get(
            f"{RESOURCE_CATALOG_URL}/discover/{service_type}",
            timeout=5
        )
        
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to discover service {service_type}: {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"Error discovering service {service_type}: {e}")
        return None 