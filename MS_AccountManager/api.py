#!/usr/bin/env python3

"""
API for the Smart Bolt Account Manager

This API provides endpoints for user authentication, registration
and user management for the Smart Bolt IoT Platform.
"""

import json
import logging
import secrets
import datetime
import cherrypy
import config
from datetime import datetime

# Set up logging
logger = logging.getLogger('account_manager_api')
if config.LOGGING_ENABLED:
    logger.setLevel(getattr(logging, config.LOG_LEVEL))
    handler = logging.FileHandler(config.LOG_FILE)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
else:
    logger.addHandler(logging.NullHandler())

class AccountManager:
    def __init__(self, db_path=None):
        import os
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), "users.json")
        self.db_path = db_path
        self.users = self._load_users()
        
    def _load_users(self):
        import os
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
            if key != 'password':  
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
        return {
            "name": "Smart Bolt Account Manager API",
            "version": "1.0",
            "endpoints": {
                "login": "/login",
                "register": "/register",
                "update_user": "/update_user",
                "delete_user": "/delete_user",
                "get_user": "/get_user?username=<username>",
                "get_all_users": "/get_all_users"
            }
        }
        
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
        
        role = data.get('role', 'user')
        
        if self.account_manager.register_user(data['username'], data['password'], data['email'], role):
            return {"success": True, "username": data['username']}
        else:
            cherrypy.response.status = 400
            return {"success": False, "error": "Username already exists"}
    
    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def update_user(self):
        data = cherrypy.request.json
        
        if 'username' not in data:
            cherrypy.response.status = 400
            return {"success": False, "error": "Missing username"}
        
        username = data.pop('username')
        
        if self.account_manager.update_user(username, data):
            return {"success": True, "username": username}
        else:
            cherrypy.response.status = 404
            return {"success": False, "error": "User not found"}
    
    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def delete_user(self):
        data = cherrypy.request.json
        
        if 'username' not in data:
            cherrypy.response.status = 400
            return {"success": False, "error": "Missing username"}
        
        if self.account_manager.delete_user(data['username']):
            return {"success": True}
        else:
            cherrypy.response.status = 404
            return {"success": False, "error": "User not found"}
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_user(self, username=None):
        if not username:
            cherrypy.response.status = 400
            return {"success": False, "error": "Missing username"}
        
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

def start_api(host='0.0.0.0', port=config.API_PORT):
    """Start the API server"""
    
    cherrypy.config.update({
        'server.socket_host': host,
        'server.socket_port': port,
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
    
    cherrypy.quickstart(AccountManagerAPI(), '/', conf)

if __name__ == '__main__':
    print(f"Starting Account Manager API on http://0.0.0.0:{config.API_PORT}")
    start_api()