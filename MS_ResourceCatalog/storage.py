import json
import os
import time
from tinydb import TinyDB, Query
from models import Device, Service

# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "catalog_db.json")

class StorageManager:
    """Handles persistence of device and service data"""
    
    def __init__(self, db_path=None):
        # Use the provided db_path or default to ResourceCatalog directory
        if db_path is None or not os.path.isabs(db_path):
            db_path = DEFAULT_DB_PATH
            
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else '.', exist_ok=True)
        self.db = TinyDB(db_path)
        self.devices = self.db.table('devices')
        self.services = self.db.table('services')
    
    # Device operations
    def get_all_devices(self):
        """Retrieve all registered devices"""
        return [Device.from_dict(device) for device in self.devices.all()]
    
    def get_device(self, device_id):
        """Get a specific device by ID"""
        Device_query = Query()
        result = self.devices.get(Device_query.device_id == device_id)
        return Device.from_dict(result) if result else None
    
    def add_device(self, device):
        """Add or update a device in the database"""
        Device_query = Query()
        device_dict = device.to_dict()
        
        # Check if device exists and update, or insert new
        if self.devices.contains(Device_query.device_id == device.device_id):
            self.devices.update(device_dict, Device_query.device_id == device.device_id)
        else:
            self.devices.insert(device_dict)
        return device
    
    def update_device_status(self, device_id, status, last_update=None):
        """Update a device's status and last update time"""
        Device_query = Query()
        last_update = last_update or time.time()
        
        if self.devices.contains(Device_query.device_id == device_id):
            self.devices.update({
                'status': status,
                'last_update': last_update
            }, Device_query.device_id == device_id)
            return True
        return False
    
    def delete_device(self, device_id):
        """Remove a device from the database"""
        Device_query = Query()
        return self.devices.remove(Device_query.device_id == device_id)
    
    # Service operations
    def get_all_services(self):
        """Retrieve all registered services"""
        return [Service.from_dict(service) for service in self.services.all()]
    
    def get_service(self, service_id):
        """Get a specific service by ID"""
        Service_query = Query()
        result = self.services.get(Service_query.service_id == service_id)
        return Service.from_dict(result) if result else None
    
    def add_service(self, service):
        """Add or update a service in the database"""
        Service_query = Query()
        service_dict = service.to_dict()
        
        # Check if service exists and update, or insert new
        if self.services.contains(Service_query.service_id == service.service_id):
            self.services.update(service_dict, Service_query.service_id == service.service_id)
        else:
            self.services.insert(service_dict)
        return service
    
    def update_service_status(self, service_id, status, last_update=None):
        """Update a service's status and last update time"""
        Service_query = Query()
        last_update = last_update or time.time()
        
        if self.services.contains(Service_query.service_id == service_id):
            self.services.update({
                'status': status,
                'last_update': last_update
            }, Service_query.service_id == service_id)
            return True
        return False
    
    def delete_service(self, service_id):
        """Remove a service from the database"""
        Service_query = Query()
        return self.services.remove(Service_query.service_id == service_id)
    
    # Advanced queries
    def get_devices_by_type(self, device_type):
        """Get all devices of a specific type"""
        Device_query = Query()
        results = self.devices.search(Device_query.device_type == device_type)
        return [Device.from_dict(device) for device in results]
    
    def get_services_by_type(self, service_type):
        """Get all services of a specific type"""
        Service_query = Query()
        results = self.services.search(Service_query.service_type == service_type)
        return [Service.from_dict(service) for service in results]
    
    def get_online_devices(self):
        """Get all online devices"""
        Device_query = Query()
        results = self.devices.search(Device_query.status == 'online')
        return [Device.from_dict(device) for device in results]
    
    def cleanup_stale_entries(self, timeout_seconds=300):
        """Mark devices/services as offline if they haven't updated within timeout"""
        current_time = time.time()
        timeout_threshold = current_time - timeout_seconds
        
        # Query for stale devices
        Device_query = Query()
        stale_devices = self.devices.search(
            (Device_query.status == 'online') & 
            (Device_query.last_update < timeout_threshold)
        )
        
        # Update stale devices to offline
        for device in stale_devices:
            self.update_device_status(device['device_id'], 'offline')
        
        # Query for stale services
        Service_query = Query()
        stale_services = self.services.search(
            (Service_query.status == 'online') & 
            (Service_query.last_update < timeout_threshold)
        )
        
        # Update stale services to offline
        for service in stale_services:
            self.update_service_status(service['service_id'], 'offline')
            
        return len(stale_devices) + len(stale_services)