import json
import os
import logging
from models import Sector, Device, Valve

class StorageManager:
    def __init__(self, data_file="pipeline_data.json"):
        self.data_file = data_file
        self.sectors = {}
        self.devices = {}
        self.load_data()
    
    def load_data(self):
        try:
            if os.path.exists(self.data_file):
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                
                for sector_data in data.get('sectors', []):
                    sector = Sector(
                        sector_data['sector_id'],
                        sector_data['name'],
                        sector_data['start_device_id'],
                        sector_data['end_device_id']
                    )
                    
                    # Load valve state if available
                    if 'valve_state' in sector_data:
                        sector.valve.state = sector_data['valve_state']
                    
                    self.sectors[sector.sector_id] = sector
                
                for device_data in data.get('devices', []):
                    device = Device(
                        device_data['device_id'],
                        device_data['sector_id'],
                        device_data['name'],
                        device_data.get('status', 'active')
                    )
                    device.readings = device_data.get('readings', {})
                    
                    self.devices[device.device_id] = device
                    
                    if device.sector_id in self.sectors:
                        self.sectors[device.sector_id].devices.append(device)
            else:
                self._initialize_default_data()
                
        except Exception as e:
            logging.error(f"Error loading data: {e}")
            self._initialize_default_data()
    
    def _initialize_default_data(self):
        sector_a = Sector("A", "Sector A", 1, 10)
        self.sectors[sector_a.sector_id] = sector_a
        
        device1 = Device(1, "A", "Device 001")
        device10 = Device(10, "A", "Device 010")
        
        self.devices[device1.device_id] = device1
        self.devices[device10.device_id] = device10
        
        sector_a.devices.append(device1)
        sector_a.devices.append(device10)
        
        self.save_data()
    
    def save_data(self):
        data = {
            'sectors': [sector.to_dict() for sector in self.sectors.values()],
            'devices': [device.to_dict() for device in self.devices.values()]
        }
        
        with open(self.data_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def get_all_sectors(self):
        return list(self.sectors.values())
    
    def get_sector(self, sector_id):
        return self.sectors.get(sector_id)
    
    def create_sector(self, name, start_device_id, end_device_id):
        existing_ids = [s.sector_id for s in self.sectors.values()]
        if existing_ids:
            next_id = chr(max(ord(id_char) for id_char in existing_ids) + 1)
        else:
            next_id = 'A'
            
        for sector in self.sectors.values():
            if (start_device_id <= sector.end_device_id and end_device_id >= sector.start_device_id):
                raise ValueError(f"Device ID range overlaps with existing sector {sector.sector_id}")
        
        new_sector = Sector(next_id, name, start_device_id, end_device_id)
        self.sectors[next_id] = new_sector
        self.save_data()
        return new_sector
    
    def update_sector(self, sector_id, name=None, start_device_id=None, end_device_id=None):
        if sector_id not in self.sectors:
            raise ValueError(f"Sector {sector_id} not found")
            
        sector = self.sectors[sector_id]
        
        if name is not None:
            sector.name = name
            
        if start_device_id is not None and end_device_id is not None:
            for device in sector.devices:
                if device.device_id < start_device_id or device.device_id > end_device_id:
                    raise ValueError(f"Device {device.device_id} would be outside new sector range")
                    
            sector.start_device_id = start_device_id
            sector.end_device_id = end_device_id
        
        self.save_data()
        return sector
    
    def delete_sector(self, sector_id):
        if sector_id not in self.sectors:
            raise ValueError(f"Sector {sector_id} not found")
            
        if self.sectors[sector_id].devices:
            raise ValueError(f"Cannot delete sector {sector_id} with devices. Remove devices first.")
            
        del self.sectors[sector_id]
        self.save_data()
        return True
    
    def get_all_devices(self):
        return list(self.devices.values())
    
    def get_devices_by_sector(self, sector_id):
        if sector_id not in self.sectors:
            raise ValueError(f"Sector {sector_id} not found")
            
        return self.sectors[sector_id].devices
    
    def get_device(self, device_id):
        return self.devices.get(device_id)
    
    def create_device(self, sector_id, device_id=None, name=None, status="active"):
        if sector_id not in self.sectors:
            raise ValueError(f"Sector {sector_id} not found")
            
        sector = self.sectors[sector_id]
        
        if not sector.has_capacity():
            raise ValueError(f"Sector {sector_id} is at full capacity")
        
        if device_id is None:
            device_id = sector.get_next_available_id()
            if device_id is None:
                raise ValueError(f"No available device IDs in sector {sector_id}")
        else:
            if device_id < sector.start_device_id or device_id > sector.end_device_id:
                raise ValueError(f"Device ID {device_id} is outside sector {sector_id} range")
                
            if device_id in self.devices:
                raise ValueError(f"Device ID {device_id} already exists")
        
        if name is None:
            device_id_str = str(device_id).zfill(3)
            name = f"Device {device_id_str}"
        
        new_device = Device(device_id, sector_id, name, status)
        self.devices[device_id] = new_device
        sector.devices.append(new_device)
        
        self.save_data()
        return new_device
    
    def update_device(self, device_id, name=None, status=None):
        if device_id not in self.devices:
            raise ValueError(f"Device {device_id} not found")
            
        device = self.devices[device_id]
        
        if name is not None:
            device.name = name
            
        if status is not None:
            device.status = status
        
        self.save_data()
        return device
    
    def delete_device(self, device_id):
        if device_id not in self.devices:
            raise ValueError(f"Device {device_id} not found")
            
        device = self.devices[device_id]
        
        sector = self.sectors.get(device.sector_id)
        if sector:
            sector.devices = [d for d in sector.devices if d.device_id != device_id]
        
        del self.devices[device_id]
        self.save_data()
        return True
    
    def update_device_reading(self, device_id, sensor_type, value):
        if device_id not in self.devices:
            raise ValueError(f"Device {device_id} not found")
            
        device = self.devices[device_id]
        device.update_reading(sensor_type, value)
        self.save_data()
        return device
    
    # Valve management methods
    def get_valve(self, sector_id):
        """Get the valve for a specific sector"""
        if sector_id not in self.sectors:
            raise ValueError(f"Sector {sector_id} not found")
        
        return self.sectors[sector_id].valve
    
    def open_valve(self, sector_id):
        """Open the valve for a specific sector"""
        if sector_id not in self.sectors:
            raise ValueError(f"Sector {sector_id} not found")
        
        result = self.sectors[sector_id].valve.open()
        self.save_data()
        return result
    
    def close_valve(self, sector_id):
        """Close the valve for a specific sector"""
        if sector_id not in self.sectors:
            raise ValueError(f"Sector {sector_id} not found")
        
        result = self.sectors[sector_id].valve.close()
        self.save_data()
        return result
    
    def set_valve_partial(self, sector_id, percentage):
        """Set the valve to partially open for a specific sector"""
        if sector_id not in self.sectors:
            raise ValueError(f"Sector {sector_id} not found")
        
        if not 0 <= percentage <= 100:
            raise ValueError(f"Percentage must be between 0 and 100")
        
        result = self.sectors[sector_id].valve.set_partial(percentage)
        self.save_data()
        return result
    
    def get_all_valve_states(self):
        """Get the state of all valves in all sectors"""
        valve_states = {}
        for sector_id, sector in self.sectors.items():
            valve_states[sector_id] = {
                "sector_name": sector.name,
                "valve_state": sector.valve.state,
                "last_action": sector.valve.last_action_timestamp
            }
        return valve_states