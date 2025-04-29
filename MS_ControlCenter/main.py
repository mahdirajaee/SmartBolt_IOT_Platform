#!/usr/bin/env python3

import os
import sys
import json
import logging
import argparse
import threading
import time
from datetime import datetime
import traceback

import cherrypy
import config
import registration
from control_logic import ControlLogic

# Set up logging
logging.basicConfig(
    filename=config.LOG_FILE,
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('controlcenter')

# Add console handler to display logs in terminal
console = logging.StreamHandler()
console.setLevel(getattr(logging, config.LOG_LEVEL))
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)

# Global control_logic instance
control_logic = ControlLogic()

class ControlCenterAPI:
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self):
        return {
            "service": config.SERVICE_NAME,
            "version": "1.0.0",
            "status": "running",
            "endpoints": [
                "/api/health",
                "/api/rules",
                "/api/status",
                "/api/valve/{sector_id}"
            ]
        }
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def health(self):
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat()
        }
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def status(self):
        return {
            "status": "success",
            "data": control_logic.get_status(),
            "timestamp": datetime.now().isoformat()
        }
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def rules(self):
        return {
            "status": "success",
            "data": {
                "rules": control_logic.get_rules()
            }
        }
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def add_rule(self):
        try:
            data = cherrypy.request.json
            
            required_fields = ['id', 'description', 'condition', 'action']
            for field in required_fields:
                if field not in data:
                    cherrypy.response.status = 400
                    return {
                        "status": "error",
                        "message": f"Missing required field: {field}"
                    }
                    
            rule_id = control_logic.add_rule(data)
            return {
                "status": "success",
                "message": f"Rule '{rule_id}' added successfully"
            }
        except Exception as e:
            logger.error(f"Error adding rule: {e}")
            cherrypy.response.status = 500
            return {
                "status": "error",
                "message": str(e)
            }
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def delete_rule(self, rule_id):
        try:
            if control_logic.remove_rule(rule_id):
                return {
                    "status": "success",
                    "message": f"Rule '{rule_id}' removed successfully"
                }
            else:
                cherrypy.response.status = 404
                return {
                    "status": "error",
                    "message": f"Rule '{rule_id}' not found"
                }
        except Exception as e:
            logger.error(f"Error removing rule: {e}")
            cherrypy.response.status = 500
            return {
                "status": "error",
                "message": str(e)
            }

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def valve(self, sector_id=None):
        if cherrypy.request.method == 'POST':
            try:
                data = cherrypy.request.json
                action = data.get('action', None)
                
                if action not in ['open', 'close']:
                    cherrypy.response.status = 400
                    return {
                        "status": "error",
                        "message": f"Invalid action: {action}. Must be 'open' or 'close'."
                    }
                
                if action == 'open':
                    success = control_logic.open_valve(sector_id, "manual")
                else:
                    success = control_logic.close_valve(sector_id, "manual", {})
                
                if success:
                    return {
                        "status": "success",
                        "message": f"Valve in sector {sector_id} commanded to {action}"
                    }
                else:
                    cherrypy.response.status = 500
                    return {
                        "status": "error",
                        "message": f"Failed to {action} valve in sector {sector_id}"
                    }
            except Exception as e:
                logger.error(f"Error controlling valve: {e}")
                cherrypy.response.status = 500
                return {
                    "status": "error",
                    "message": str(e)
                }
        else:
            cherrypy.response.status = 405
            return {
                "status": "error",
                "message": "Method not allowed"
            }

def start_control_center():
    logger.info("Starting Control Center")
    
    try:
        # Start registration with Resource Catalog
        registration.start_registration_thread()
        logger.info("Registration thread started")
        
        # Start the control logic
        success = control_logic.start()
        if success:
            logger.info("Control Logic started successfully")
        else:
            logger.error("Failed to start Control Logic - MQTT connection may have failed")
        
        # Configure and start CherryPy server
        api_config = {
            '/': {
                'tools.sessions.on': True,
                'tools.response_headers.on': True,
                'tools.response_headers.headers': [('Content-Type', 'application/json')],
                'tools.encode.on': True,
                'tools.encode.encoding': 'utf-8',
            }
        }
        
        cherrypy.config.update({
            'server.socket_host': '0.0.0.0',
            'server.socket_port': config.API_PORT,
            'engine.autoreload.on': False,
            'log.access_file': '',
            'log.error_file': '',
            'log.screen': True  # Enable screen logging
        })
        
        # Mount the API
        cherrypy.tree.mount(ControlCenterAPI(), '/api', api_config)
        
        # Start the server
        cherrypy.engine.signals.subscribe()  # Subscribe to all signals
        cherrypy.engine.start()
        logger.info(f"CherryPy server started on port {config.API_PORT}")
        
        print(f"Control Center is running on port {config.API_PORT}")
        print("Press Ctrl+C to stop the service")
        
        # Keep the main thread running
        try:
            cherrypy.engine.block()
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, shutting down...")
            stop_control_center()
        
    except Exception as e:
        logger.error(f"Error starting Control Center: {e}")
        logger.error(traceback.format_exc())
        sys.exit(1)
        
def stop_control_center():
    logger.info("Stopping Control Center")
    control_logic.stop()
    cherrypy.engine.exit()
    logger.info("Control Center stopped")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart Bolt Control Center")
    parser.add_argument("--port", type=int, help="API port", default=config.API_PORT)
    args = parser.parse_args()
    
    if args.port:
        config.API_PORT = args.port
        
    try:
        start_control_center()
    except KeyboardInterrupt:
        stop_control_center()