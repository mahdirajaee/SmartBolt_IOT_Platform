import cherrypy
import json
import logging
from storage import StorageManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SectorAPI:
    exposed = True
    
    def __init__(self):
        self.storage = StorageManager()
    
    @cherrypy.tools.json_out()
    def GET(self, sector_id=None):
        if sector_id is None:
            sectors = self.storage.get_all_sectors()
            return [sector.to_dict() for sector in sectors]
        else:
            sector = self.storage.get_sector(sector_id)
            if not sector:
                cherrypy.response.status = 404
                return {"error": f"Sector {sector_id} not found"}
            return sector.to_dict()
    
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def POST(self):
        data = cherrypy.request.json
        
        if not data:
            cherrypy.response.status = 400
            return {"error": "No data provided"}
            
        name = data.get('name')
        start_device_id = data.get('start_device_id')
        end_device_id = data.get('end_device_id')
        
        if not name or not start_device_id or not end_device_id:
            cherrypy.response.status = 400
            return {"error": "Missing required fields"}
            
        try:
            start_device_id = int(start_device_id)
            end_device_id = int(end_device_id)
            
            if start_device_id >= end_device_id:
                cherrypy.response.status = 400
                return {"error": "start_device_id must be less than end_device_id"}
                
            sector = self.storage.create_sector(name, start_device_id, end_device_id)
            cherrypy.response.status = 201
            return sector.to_dict()
        except ValueError as e:
            cherrypy.response.status = 400
            return {"error": str(e)}
    
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def PUT(self, sector_id):
        data = cherrypy.request.json
        
        if not data:
            cherrypy.response.status = 400
            return {"error": "No data provided"}
            
        name = data.get('name')
        start_device_id = data.get('start_device_id')
        end_device_id = data.get('end_device_id')
        
        try:
            if start_device_id is not None:
                start_device_id = int(start_device_id)
            if end_device_id is not None:
                end_device_id = int(end_device_id)
                
            if start_device_id is not None and end_device_id is not None and start_device_id >= end_device_id:
                cherrypy.response.status = 400
                return {"error": "start_device_id must be less than end_device_id"}
                
            sector = self.storage.update_sector(sector_id, name, start_device_id, end_device_id)
            return sector.to_dict()
        except ValueError as e:
            cherrypy.response.status = 400
            return {"error": str(e)}
    
    @cherrypy.tools.json_out()
    def DELETE(self, sector_id):
        try:
            self.storage.delete_sector(sector_id)
            return {"message": f"Sector {sector_id} deleted"}
        except ValueError as e:
            cherrypy.response.status = 400
            return {"error": str(e)}

class SectorDevicesAPI:
    exposed = True
    
    def __init__(self):
        self.storage = StorageManager()
    
    @cherrypy.tools.json_out()
    def GET(self, sector_id):
        try:
            devices = self.storage.get_devices_by_sector(sector_id)
            return [device.to_dict() for device in devices]
        except ValueError as e:
            cherrypy.response.status = 400
            return {"error": str(e)}

class DeviceAPI:
    exposed = True
    
    def __init__(self):
        self.storage = StorageManager()
    
    @cherrypy.tools.json_out()
    def GET(self, device_id=None):
        if device_id is None:
            devices = self.storage.get_all_devices()
            return [device.to_dict() for device in devices]
        else:
            device_id = int(device_id)
            device = self.storage.get_device(device_id)
            if not device:
                cherrypy.response.status = 404
                return {"error": f"Device {device_id} not found"}
            return device.to_dict()
    
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def POST(self):
        data = cherrypy.request.json
        
        if not data:
            cherrypy.response.status = 400
            return {"error": "No data provided"}
            
        sector_id = data.get('sector_id')
        device_id = data.get('device_id')
        name = data.get('name')
        status = data.get('status', 'active')
        
        if not sector_id:
            cherrypy.response.status = 400
            return {"error": "sector_id is required"}
            
        try:
            if device_id is not None:
                device_id = int(device_id)
                
            device = self.storage.create_device(sector_id, device_id, name, status)
            cherrypy.response.status = 201
            return device.to_dict()
        except ValueError as e:
            cherrypy.response.status = 400
            return {"error": str(e)}
    
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def PUT(self, device_id):
        data = cherrypy.request.json
        
        if not data:
            cherrypy.response.status = 400
            return {"error": "No data provided"}
            
        name = data.get('name')
        status = data.get('status')
        
        try:
            device_id = int(device_id)
            device = self.storage.update_device(device_id, name, status)
            return device.to_dict()
        except ValueError as e:
            cherrypy.response.status = 400
            return {"error": str(e)}
    
    @cherrypy.tools.json_out()
    def DELETE(self, device_id):
        try:
            device_id = int(device_id)
            self.storage.delete_device(device_id)
            return {"message": f"Device {device_id} deleted"}
        except ValueError as e:
            cherrypy.response.status = 400
            return {"error": str(e)}

class DeviceReadingsAPI:
    exposed = True
    
    def __init__(self):
        self.storage = StorageManager()
    
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def POST(self, device_id):
        data = cherrypy.request.json
        
        if not data:
            cherrypy.response.status = 400
            return {"error": "No data provided"}
            
        sensor_type = data.get('sensor_type')
        value = data.get('value')
        
        if not sensor_type or value is None:
            cherrypy.response.status = 400
            return {"error": "sensor_type and value are required"}
            
        try:
            device_id = int(device_id)
            device = self.storage.update_device_reading(device_id, sensor_type, value)
            return device.to_dict()
        except ValueError as e:
            cherrypy.response.status = 400
            return {"error": str(e)}

class SensorAPI:
    exposed = True
    
    def __init__(self):
        self.storage = StorageManager()
    
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def POST(self):
        data = cherrypy.request.json
        
        if not data:
            cherrypy.response.status = 400
            return {"error": "No data provided"}
            
        device_id = data.get('device_id')
        readings = data.get('readings', {})
        
        if not device_id or not readings:
            cherrypy.response.status = 400
            return {"error": "device_id and readings are required"}
        
        try:
            temperature = readings.get('temperature', {}).get('value')
            pressure = readings.get('pressure', {}).get('value')
            
            if isinstance(device_id, str) and device_id != "raspberrypi_simulator":
                try:
                    device_id = int(device_id)
                except ValueError:
                    pass
            
            if isinstance(device_id, int):
                device = self.storage.get_device(device_id)
                if not device:
                    cherrypy.response.status = 404
                    return {"error": f"Device {device_id} not found"}
                
                if temperature is not None:
                    self.storage.update_device_reading(device_id, "temperature", temperature)
                    
                if pressure is not None:
                    self.storage.update_device_reading(device_id, "pressure", pressure)
                    
                return {"status": "success", "message": f"Readings updated for device {device_id}"}
            else:
                return {"status": "success", "message": "Readings received from simulator"}
                
        except Exception as e:
            cherrypy.response.status = 500
            logger.error(f"Error processing sensor data: {e}")
            return {"error": str(e)}

class ValveAPI:
    exposed = True
    
    def __init__(self):
        self.storage = StorageManager()
    
    @cherrypy.tools.json_out()
    def GET(self, sector_id=None):
        """Get valve state for a sector or all sectors"""
        if sector_id is None:
            # Return all valve states
            return self.storage.get_all_valve_states()
        else:
            try:
                valve = self.storage.get_valve(sector_id)
                if not valve:
                    cherrypy.response.status = 404
                    return {"error": f"Valve for sector {sector_id} not found"}
                return valve.to_dict()
            except ValueError as e:
                cherrypy.response.status = 400
                return {"error": str(e)}
    
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def POST(self, sector_id):
        """Set valve state for a sector"""
        data = cherrypy.request.json
        
        if not data:
            cherrypy.response.status = 400
            return {"error": "No data provided"}
        
        action = data.get('action')
        if not action:
            cherrypy.response.status = 400
            return {"error": "Action is required (open, close, or partial)"}
        
        try:
            result = False
            
            if action.lower() == 'open':
                result = self.storage.open_valve(sector_id)
                message = f"Valve for sector {sector_id} opened"
            elif action.lower() == 'close':
                result = self.storage.close_valve(sector_id)
                message = f"Valve for sector {sector_id} closed"
            elif action.lower() == 'partial':
                percentage = data.get('percentage')
                if percentage is None:
                    cherrypy.response.status = 400
                    return {"error": "Percentage is required for partial valve opening"}
                
                try:
                    percentage = int(percentage)
                except ValueError:
                    cherrypy.response.status = 400
                    return {"error": "Percentage must be a number between 0 and 100"}
                
                result = self.storage.set_valve_partial(sector_id, percentage)
                message = f"Valve for sector {sector_id} set to {percentage}%"
            else:
                cherrypy.response.status = 400
                return {"error": "Invalid action. Use 'open', 'close', or 'partial'"}
                
            if result:
                valve = self.storage.get_valve(sector_id)
                return {
                    "status": "success", 
                    "message": message,
                    "valve": valve.to_dict()
                }
            else:
                cherrypy.response.status = 500
                return {"error": "Failed to set valve state"}
                
        except ValueError as e:
            cherrypy.response.status = 400
            return {"error": str(e)}

def error_page_default(status, message, traceback, version):
    response = {"status": status, "message": message}
    logger.error(f"Error: {status} - {message}")
    return json.dumps(response)

def start_api():
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 5000,
        'environment': 'production',
        'log.screen': True
    })
    
    cherrypy.config.update({'error_page.default': error_page_default})
    
    api_conf = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'application/json')],
            'tools.encode.on': True,
            'tools.encode.encoding': 'utf-8',
            'tools.json_in.on': True,
            'tools.json_out.on': True
        }
    }
    
    root = Root()
    root.api = API()
    root.api.sectors = SectorAPI()
    root.api.devices = DeviceAPI()
    root.api.sensor_data = SensorAPI()
    root.api.valves = ValveAPI()  # Register the valve API
    
    cherrypy.tree.mount(SectorDevicesAPI(), '/api/sectors/{sector_id}/devices', api_conf)
    cherrypy.tree.mount(DeviceReadingsAPI(), '/api/devices/{device_id}/readings', api_conf)
    cherrypy.tree.mount(ValveAPI(), '/api/sectors/{sector_id}/valve', api_conf)  # Mount sector valve endpoints
    cherrypy.tree.mount(root, '/', api_conf)
    
    cherrypy.engine.start()
    cherrypy.engine.block()

class API:
    pass

class Root:
    pass

if __name__ == '__main__':
    start_api()