import os
import sys
import time
import json
import uuid
import hashlib
import threading
import requests
import random
import socket
import jwt
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add the current directory to the path so Python finds our cgi.py module first
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Import cherrypy after path modification so it can find our cgi module
import cherrypy

load_dotenv()  # Load environment variables from .env file

class AccountManager:
    exposed = True
    
    def __init__(self):
        self.service_id = "account_manager"
        self.catalog_url = os.environ.get('CATALOG_URL', 'http://localhost:8080')
        self.port = int(os.environ.get('PORT', 8086))
        self.secret_key = os.environ.get('JWT_SECRET', 'smart_iot_bolt_secret_key')
        self.service_base_url = None
        self.catalog_available = False
        
        # Local user storage
        self.users = {}
        self.load_users()
        
        # Set the base URL for this service
        self.set_base_url(self.port)
        
        # Start a thread to periodically try to register with the catalog
        threading.Thread(target=self.update_registration_periodically, daemon=True).start()
    
    def load_users(self):
        """Load users from file if it exists"""
        try:
            if os.path.exists('users.json'):
                with open('users.json', 'r') as f:
                    self.users = json.load(f)
                print("Loaded users from file")
        except Exception as e:
            print(f"Error loading users: {e}")
    
    def save_users(self):
        """Save users to file"""
        try:
            with open('users.json', 'w') as f:
                json.dump(self.users, f, indent=2)
            print("Saved users to file")
        except Exception as e:
            print(f"Error saving users: {e}")
    
    def set_base_url(self, port):
        """Set the base URL after the port is determined"""
        self.service_base_url = os.environ.get('BASE_URL', f'http://localhost:{port}')
        print(f"Service base URL set to: {self.service_base_url}")
    
    def register_to_catalog(self):
        """Try to register with the catalog, handling connection failures gracefully"""
        if not self.service_base_url:
            print("Base URL not set yet, skipping registration")
            return False
            
        service_info = {
            "name": self.service_id,
            "endpoint": self.service_base_url,
            "port": self.port,
            "additional_info": {
                "description": "Account management service for authentication and user management"
            }
        }
        
        try:
            response = requests.post(f"{self.catalog_url}/service", json=service_info, timeout=5)
            if response.status_code in (200, 201):
                print(f"Successfully registered to catalog with ID: {self.service_id}")
                self.catalog_available = True
                return True
            else:
                print(f"Failed to register to catalog: {response.text}")
                return False
        except requests.exceptions.ConnectionError:
            if not self.catalog_available:
                print(f"Catalog service not available at {self.catalog_url}. Will retry later...")
            return False
        except Exception as e:
            print(f"Error registering to catalog: {e}")
            return False
    
    def update_registration_periodically(self):
        """Periodically try to register with the catalog, with exponential backoff on failure"""
        retry_delay = 5  # Start with 5 seconds
        max_delay = 300  # Maximum 5 minutes delay
        
        while True:
            success = self.register_to_catalog()
            
            if success:
                # If successful, reset retry delay and wait a minute before next update
                retry_delay = 5
                time.sleep(60)
            else:
                # If failed, use exponential backoff
                jitter = random.uniform(0, 0.1 * retry_delay)
                sleep_time = retry_delay + jitter
                print(f"Will retry catalog registration in {sleep_time:.1f} seconds")
                time.sleep(sleep_time)
                # Increase delay for next failure, but cap it
                retry_delay = min(retry_delay * 2, max_delay)
    
    def get_user_from_catalog(self, username):
        """Get user data from local storage"""
        return self.users.get(username)
    
    def store_user_in_catalog(self, user_data):
        """Store user data in local storage"""
        username = user_data.get("username")
        if not username:
            return False
        
        self.users[username] = user_data
        self.save_users()
        return True
    
    def update_user_in_catalog(self, username, user_data):
        """Update user data in local storage"""
        if username not in self.users:
            return False
        
        self.users[username].update(user_data)
        self.save_users()
        return True
    
    def hash_password(self, password, salt=None):
        if salt is None:
            salt = os.urandom(16).hex()
        
        pw_hash = hashlib.sha256((password + salt).encode()).hexdigest()
        return pw_hash, salt
    
    def generate_token(self, username, role):
        expiry = datetime.utcnow() + timedelta(hours=24)
        payload = {
            "sub": username,
            "role": role,
            "exp": expiry,
            "iat": datetime.utcnow(),
            "jti": str(uuid.uuid4())
        }
        
        token = jwt.encode(payload, self.secret_key, algorithm="HS256")
        return token
    
    def validate_token(self, token):
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=["HS256"])
            return payload
        except jwt.ExpiredSignatureError:
            return {"error": "Token has expired"}
        except jwt.InvalidTokenError:
            return {"error": "Invalid token"}
    
    @cherrypy.tools.json_out()
    def GET(self):
        return {
            "status": "Account Manager service is running",
            "catalog_connection": "available" if self.catalog_available else "unavailable"
        }
    
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def POST(self, action=None):
        if action == "login":
            data = cherrypy.request.json
            username = data.get("username")
            password = data.get("password")
            
            if not username or not password:
                cherrypy.response.status = 400
                return {"error": "Username and password are required"}
            
            user = self.get_user_from_catalog(username)
            
            if not user:
                # If no user found, allow a default admin login for initial setup
                if username == "admin" and password == "admin":
                    # Create the admin user if it doesn't exist
                    pw_hash, salt = self.hash_password("admin")
                    admin_user = {
                        "username": "admin",
                        "password_hash": pw_hash,
                        "salt": salt,
                        "role": "admin",
                        "created_at": time.time()
                    }
                    self.store_user_in_catalog(admin_user)
                    
                    return {
                        "token": self.generate_token("admin", "admin"),
                        "username": "admin",
                        "role": "admin"
                    }
                
                cherrypy.response.status = 401
                return {"error": "Invalid username or password"}
            
            pw_hash, salt = self.hash_password(password, user.get("salt"))
            
            if pw_hash != user.get("password_hash"):
                cherrypy.response.status = 401
                return {"error": "Invalid username or password"}
            
            token = self.generate_token(username, user.get("role", "user"))
            
            return {"token": token, "username": username, "role": user.get("role", "user")}
        
        elif action == "register":
            data = cherrypy.request.json
            username = data.get("username")
            password = data.get("password")
            role = data.get("role", "user")
            
            if not username or not password:
                cherrypy.response.status = 400
                return {"error": "Username and password are required"}
            
            existing_user = self.get_user_from_catalog(username)
            
            if existing_user:
                cherrypy.response.status = 409
                return {"error": "Username already exists"}
            
            pw_hash, salt = self.hash_password(password)
            
            user_data = {
                "username": username,
                "password_hash": pw_hash,
                "salt": salt,
                "role": role,
                "created_at": time.time()
            }
            
            if self.store_user_in_catalog(user_data):
                token = self.generate_token(username, role)
                return {"token": token, "username": username, "role": role}
            else:
                cherrypy.response.status = 500
                return {"error": "Failed to register user"}
        
        elif action == "validate":
            data = cherrypy.request.json
            token = data.get("token")
            
            if not token:
                cherrypy.response.status = 400
                return {"error": "Token is required"}
            
            validation_result = self.validate_token(token)
            
            if "error" in validation_result:
                cherrypy.response.status = 401
                return validation_result
            
            return {
                "valid": True,
                "username": validation_result.get("sub"),
                "role": validation_result.get("role")
            }
        
        else:
            cherrypy.response.status = 400
            return {"error": "Invalid action"}

def find_free_port(start_port, max_attempts=10):
    """Find a free port starting from start_port"""
    for port_offset in range(max_attempts):
        port = start_port + port_offset
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind(('0.0.0.0', port))
            sock.close()
            return port
        except OSError:
            continue
    
    # If we get here, we couldn't find a free port
    raise RuntimeError(f"Could not find a free port after {max_attempts} attempts starting from {start_port}")

if __name__ == "__main__":
    # Check for our compatibility module
    try:
        import cgi
        print("Using compatibility cgi module:", cgi.__file__)
    except ImportError:
        print("WARNING: cgi module not found - CherryPy may not work properly")
    
    # Find an available port
    preferred_port = int(os.environ.get('PORT', 8086))
    try:
        port = find_free_port(preferred_port)
        if port != preferred_port:
            print(f"Port {preferred_port} is in use. Using port {port} instead.")
        else:
            print(f"Using preferred port {port}")
    except RuntimeError as e:
        print(f"Error: {e}")
        print("Please specify a different port using the PORT environment variable")
        sys.exit(1)
    
    # Configure CherryPy
    conf = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.sessions.on': True,
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'application/json')]
        }
    }
    
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': port
    })
    
    # Create and mount the application
    app = AccountManager()
    app.set_base_url(port)  # Set the base URL based on the actual port used
    
    cherrypy.tree.mount(app, '/account', conf)
    cherrypy.tree.mount(app, '/account/login', conf)
    cherrypy.tree.mount(app, '/account/register', conf)
    cherrypy.tree.mount(app, '/account/validate', conf)
    
    print(f"Account Manager service running on port {port}")
    
    # Start CherryPy engine
    cherrypy.engine.start()
    cherrypy.engine.block()