#!/usr/bin/env python3

import json
import logging
import signal
import sys
import time
import os
import secrets
import cherrypy
from datetime import datetime

import config
from registration import start_registration, update_status

if config.LOGGING_ENABLED:
    logging.basicConfig(
        filename=config.LOG_FILE,
        level=getattr(logging, config.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
else:
    logging.basicConfig(level=logging.WARNING)

logger = logging.getLogger('account_manager')

console = logging.StreamHandler()
console.setLevel(getattr(logging, config.LOG_LEVEL))
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)

class AccountManager:
    def __init__(self, db_path="users.json"):
        self.db_path = db_path
        self.users = self._load_users()
        
    def _load_users(self):
        try:
            if os.path.exists(self.db_path):
                with open(self.db_path, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Error loading users: {e}")
            return {}
            
    def _save_users(self):
        try:
            with open(self.db_path, 'w') as f:
                json.dump(self.users, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Error saving users: {e}")
            return False
    
    def authenticate(self, username, password):
        if username in self.users and self.users[username]['password'] == password:
            return True
        return False
        
    def register_user(self, username, password, email, role="user"):
        if username in self.users:
            return False
            
        self.users[username] = {
            "password": password,
            "email": email,
            "role": role,
            "created_at": datetime.now().isoformat()
        }
        
        return self._save_users()
        
    def update_user(self, username, data):
        if username not in self.users:
            return False
            
        for key, value in data.items():
            if key != 'password':  # Don't update password this way
                self.users[username][key] = value
                
        return self._save_users()
        
    def delete_user(self, username):
        if username not in self.users:
            return False
            
        del self.users[username]
        return self._save_users()
        
    def get_user(self, username):
        return self.users.get(username)
        
    def get_all_users(self):
        return self.users

class AccountManagerAPI:
    def __init__(self):
        self.account_manager = AccountManager()
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self):
        return {"status": "Account Manager API is running"}
        
    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def login(self):
        return self._process_login()
    
    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def auth_login(self):
        return self._process_login()
        
    def _process_login(self):
        data = cherrypy.request.json
        
        if not data or 'username' not in data or 'password' not in data:
            cherrypy.response.status = 400
            return {"success": False, "error": "Missing username or password"}
            
        if self.account_manager.authenticate(data['username'], data['password']):
            token = secrets.token_hex(16)
            user_id = data['username']
            role = "admin" if data['username'] == "admin" else "user"
            
            return {
                "success": True, 
                "user_id": user_id,
                "username": data['username'],
                "role": role,
                "token": token
            }
        else:
            cherrypy.response.status = 401
            return {"success": False, "error": "Invalid credentials"}
    
    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def register(self):
        data = cherrypy.request.json
        
        required_fields = ['username', 'password', 'email']
        for field in required_fields:
            if field not in data:
                cherrypy.response.status = 400
                return {"success": False, "error": f"Missing required field: {field}"}
                
        if self.account_manager.register_user(data['username'], data['password'], data['email']):
            return {"success": True, "username": data['username']}
        else:
            cherrypy.response.status = 409
            return {"success": False, "error": "Username already exists"}
    
    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def update_user(self, username):
        data = cherrypy.request.json
        
        if not username:
            cherrypy.response.status = 400
            return {"success": False, "error": "Username is required"}
            
        if self.account_manager.update_user(username, data):
            return {"success": True, "username": username}
        else:
            cherrypy.response.status = 404
            return {"success": False, "error": "User not found"}
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def delete_user(self, username):
        if not username:
            cherrypy.response.status = 400
            return {"success": False, "error": "Username is required"}
            
        if self.account_manager.delete_user(username):
            return {"success": True}
        else:
            cherrypy.response.status = 404
            return {"success": False, "error": "User not found"}
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_user(self, username):
        if not username:
            cherrypy.response.status = 400
            return {"success": False, "error": "Username is required"}
            
        user = self.account_manager.get_user(username)
        if user:
            return {"success": True, "user": user}
        else:
            cherrypy.response.status = 404
            return {"success": False, "error": "User not found"}
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_all_users(self):
        return {"success": True, "users": self.account_manager.get_all_users()}

def signal_handler(sig, frame):
    logger.info(f"Received signal {sig}, shutting down...")
    update_status("offline")
    
    try:
        if cherrypy.engine.state == cherrypy.engine.states.STARTED:
            cherrypy.engine.exit()
            logger.info("API server stopped")
    except:
        pass
        
    sys.exit(0)

def main():
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    import argparse
    parser = argparse.ArgumentParser(description='Account Manager')
    parser.add_argument('--port', type=int, default=8000, help='Port for the API server')
    args = parser.parse_args()
    
    print("Starting Account Manager service...")
    
    print("Registering with Resource Catalog...")
    success = start_registration(background=True)
    if success:
        print("Successfully registered with Resource Catalog")
    else:
        print("Warning: Failed to register with Resource Catalog, will retry in background")
    
    try:
        cherrypy.config.update({
            'server.socket_host': '0.0.0.0',
            'server.socket_port': args.port,
            'engine.autoreload.on': False,
            'log.screen': True
        })
        
        conf = {
            '/': {
                'tools.sessions.on': True,
                'tools.response_headers.on': True,
                'tools.response_headers.headers': [('Content-Type', 'application/json')],
                'tools.encode.on': True,
                'tools.encode.encoding': 'utf-8'
            }
        }
        
        # Create an API instance
        api = AccountManagerAPI()
        
        # Mount at root path
        cherrypy.tree.mount(api, '/', conf)
        
        # Mount at auth path
        cherrypy.tree.mount(api, '/auth', conf)
        cherrypy.engine.start()
        print(f"API server running at http://0.0.0.0:{args.port}")
        
        cherrypy.engine.block()
        
    except Exception as e:
        print(f"Failed to start API server: {e}")
        update_status("offline")
        sys.exit(1)

if __name__ == "__main__":
    main()