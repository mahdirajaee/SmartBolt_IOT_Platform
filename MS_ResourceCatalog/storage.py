import json
import os
import time
from tinydb import TinyDB, Query
from models import Device, Service

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "catalog_db.json")

class StorageManager:
    def __init__(self, db_path=None):
        if db_path is None or not os.path.isabs(db_path):
            db_path = DEFAULT_DB_PATH
            
        os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else '.', exist_ok=True)
        self.db_path = db_path
        self.db = {}
        self.load_db()
    
    def load_db(self):
        try:
            if os.path.exists(self.db_path) and os.path.getsize(self.db_path) > 0:
                with open(self.db_path, 'r') as file:
                    self.db = json.load(file)
            else:
                self.db = {"devices": {}, "services": {}}
        except (json.JSONDecodeError, FileNotFoundError):
            self.db = {"devices": {}, "services": {}}
        
    def save_db(self):
        with open(self.db_path, 'w') as file:
            json.dump(self.db, file, indent=2)
    
    def get_all_devices(self):
        return [Device.from_dict(device) for device in self.db.get("devices", {}).values()]
    
    def get_device(self, device_id):
        device = self.db.get("devices", {}).get(device_id)
        return Device.from_dict(device) if device else None
    
    def add_device(self, device):
        device_dict = device.to_dict()
        if "devices" not in self.db:
            self.db["devices"] = {}
        
        self.db["devices"][device.device_id] = device_dict
        self.save_db()
        return device
    
    def update_device_status(self, device_id, status, last_update=None):
        last_update = last_update or time.time()
        
        if device_id in self.db.get("devices", {}):
            self.db["devices"][device_id]["status"] = status
            self.db["devices"][device_id]["last_update"] = last_update
            self.db["devices"][device_id]["last_update_formatted"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_update))
            self.save_db()
            return True
        return False
    
    def delete_device(self, device_id):
        if device_id in self.db.get("devices", {}):
            del self.db["devices"][device_id]
            self.save_db()
            return True
        return False
    
    def get_all_services(self):
        return [Service.from_dict(service) for service in self.db.get("services", {}).values()]
    
    def get_service(self, service_id):
        service = self.db.get("services", {}).get(service_id)
        return Service.from_dict(service) if service else None
    
    def add_service(self, service):
        service_dict = service.to_dict()
        if "services" not in self.db:
            self.db["services"] = {}
            
        self.db["services"][service.service_id] = service_dict
        self.save_db()
        return service
    
    def update_service_status(self, service_id, status, last_update=None):
        last_update = last_update or time.time()
        
        if service_id in self.db.get("services", {}):
            self.db["services"][service_id]["status"] = status
            self.db["services"][service_id]["last_update"] = last_update
            self.db["services"][service_id]["last_update_formatted"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(last_update))
            self.save_db()
            return True
        return False
    
    def delete_service(self, service_id):
        if service_id in self.db.get("services", {}):
            del self.db["services"][service_id]
            self.save_db()
            return True
        return False
    
    def get_devices_by_type(self, device_type):
        devices = []
        for device in self.db.get("devices", {}).values():
            if device.get("device_type") == device_type:
                devices.append(Device.from_dict(device))
        return devices
    
    def get_services_by_type(self, service_type):
        services = []
        for service in self.db.get("services", {}).values():
            if service.get("service_type") == service_type:
                services.append(Service.from_dict(service))
        return services
    
    def get_online_devices(self):
        devices = []
        for device in self.db.get("devices", {}).values():
            if device.get("status") == "online":
                devices.append(Device.from_dict(device))
        return devices
    
    def cleanup_stale_entries(self, timeout_seconds=300):
        current_time = time.time()
        timeout_threshold = current_time - timeout_seconds
        stale_count = 0
        
        for device_id, device in list(self.db.get("devices", {}).items()):
            if device.get("status") == "online" and device.get("last_update", 0) < timeout_threshold:
                self.update_device_status(device_id, "offline")
                stale_count += 1
        
        for service_id, service in list(self.db.get("services", {}).items()):
            if service.get("status") == "online" and service.get("last_update", 0) < timeout_threshold:
                self.update_service_status(service_id, "offline")
                stale_count += 1
                
        return stale_count