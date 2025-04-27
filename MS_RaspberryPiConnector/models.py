class Sector:
    def __init__(self, sector_id, name, start_device_id, end_device_id):
        self.sector_id = sector_id
        self.name = name
        self.start_device_id = start_device_id
        self.end_device_id = end_device_id
        self.devices = []
        self.valve = Valve(sector_id)  # Each sector now has a valve
    
    def to_dict(self):
        return {
            "sector_id": self.sector_id,
            "name": self.name,
            "start_device_id": self.start_device_id,
            "end_device_id": self.end_device_id,
            "device_count": len(self.devices),
            "valve_state": self.valve.state  # Include valve state in sector information
        }
    
    def has_capacity(self):
        max_devices = self.end_device_id - self.start_device_id + 1
        return len(self.devices) < max_devices
    
    def get_available_ids(self):
        used_ids = {device.device_id for device in self.devices}
        available_ids = []
        for i in range(self.start_device_id, self.end_device_id + 1):
            if i not in used_ids:
                available_ids.append(i)
        return available_ids
    
    def get_next_available_id(self):
        available_ids = self.get_available_ids()
        return min(available_ids) if available_ids else None

class Valve:
    def __init__(self, sector_id, state="closed"):
        self.sector_id = sector_id
        self.state = state  # "open", "closed", "partially_open"
        self.last_action_timestamp = None
    
    def open(self):
        self.state = "open"
        self._update_timestamp()
        return True
    
    def close(self):
        self.state = "closed"
        self._update_timestamp()
        return True
    
    def set_partial(self, percentage):
        """Set valve to partially open with a percentage (0-100)"""
        if 0 <= percentage <= 100:
            self.state = f"partially_open_{percentage}%"
            self._update_timestamp()
            return True
        return False
    
    def _update_timestamp(self):
        """Update the timestamp of the last valve action"""
        from datetime import datetime
        self.last_action_timestamp = datetime.now().isoformat()
    
    def to_dict(self):
        return {
            "sector_id": self.sector_id,
            "state": self.state,
            "last_action_timestamp": self.last_action_timestamp
        }

class Device:
    def __init__(self, device_id, sector_id, name, status="active"):
        self.device_id = device_id
        self.sector_id = sector_id
        self.name = name
        self.status = status
        self.readings = {}
    
    def to_dict(self):
        return {
            "device_id": self.device_id,
            "sector_id": self.sector_id,
            "name": self.name,
            "status": self.status,
            "readings": self.readings
        }
    
    def update_reading(self, sensor_type, value):
        self.readings[sensor_type] = value