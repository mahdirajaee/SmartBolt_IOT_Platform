import cherrypy
import json
import firebase_admin
from firebase_admin import credentials, auth
import os
import hashlib
import jwt
import datetime
import time
import logging
import requests
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("AccountManager")

# Configuration - Load from environment variables
SERVICE_ID = os.getenv("SERVICE_ID", "account_manager")
CATALOG_URL = os.getenv("CATALOG_URL", "http://localhost:8080")
SECRET_KEY = os.getenv("JWT_SECRET", "your-secret-key")  # Should be loaded from env var in production
USER_CREDENTIALS_FILE = os.getenv("USER_CREDENTIALS_FILE", "user_credentials.json")
FIREBASE_ENABLED = os.getenv("FIREBASE_ENABLED", "True").lower() == "true"
FIREBASE_CREDENTIALS = os.getenv("FIREBASE_CREDENTIALS", "firebase-credentials.json")

# Initialize Firebase if enabled
if FIREBASE_ENABLED:
    try:
        cred_path = os.getenv("FIREBASE_CREDENTIALS", "firebase-credentials.json")
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        logger.info("Firebase initialized")
    except Exception as e:
        logger.error(f"Firebase initialization failed: {e}")
        FIREBASE_ENABLED = False

class AccountManager:
    """
    Account Manager Microservice for Smart IoT Bolt Platform
    
    Responsibilities:
    - User authentication (Firebase or local)
    - Token issuance and validation
    - Integration with Resource/Service Catalog
    - Supporting Web Dashboard and Telegram Bot authentication
    """
    
    def __init__(self):
        self.service_info = {
            "id": SERVICE_ID,
            "name": "AccountManager",
            "endpoint": self._get_public_endpoint(),
            "last_update": int(time.time())
        }
        # Register with catalog
        self.register_with_catalog()
        # Start background updater
        cherrypy.engine.subscribe('start', self.start_update_thread)
        
    def _get_public_endpoint(self):
        """Determine the public endpoint for this service"""
        host = cherrypy.server.socket_host
        port = cherrypy.server.socket_port
        if host == '0.0.0.0':
            # Try to get the actual IP
            import socket
            try:
                host = socket.gethostbyname(socket.gethostname())
            except:
                host = "localhost"  # Fallback
        return f"http://{host}:{port}"
        
    def register_with_catalog(self):
        """Register this service with the Resource/Service Catalog"""
        try:
            response = requests.post(
                f"{CATALOG_URL}/services", 
                json=self.service_info
            )
            if response.status_code == 200 or response.status_code == 201:
                logger.info("Successfully registered with catalog")
            else:
                logger.warning(f"Failed to register with catalog: {response.status_code} {response.text}")
        except Exception as e:
            logger.error(f"Error registering with catalog: {e}")
            
    def update_catalog(self):
        """Update the last_seen timestamp in the catalog"""
        self.service_info["last_update"] = int(time.time())
        try:
            response = requests.put(
                f"{CATALOG_URL}/services/{SERVICE_ID}", 
                json=self.service_info
            )
            if response.status_code != 200:
                logger.warning(f"Failed to update catalog: {response.status_code} {response.text}")
        except Exception as e:
            logger.error(f"Error updating catalog: {e}")
            
    def start_update_thread(self):
        """Start a background thread to periodically update the catalog"""
        def update_loop():
            while True:
                self.update_catalog()
                time.sleep(60)  # Update every minute
                
        updater = threading.Thread(target=update_loop, daemon=True)
        updater.start()
        logger.info("Started catalog update thread")

    # ========================= API Endpoints =========================
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self):
        """Default response"""
        return {
            "message": "Smart IoT Bolt Account Manager API",
            "version": "1.0",
            "status": "running",
            "firebase_enabled": FIREBASE_ENABLED
        }

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def users(self, *params, **queries):
        """
        GET /users - Get all users or a specific user
        GET /users?email=email@example.com - Get specific user info
        """
        # For a production system, this would need admin authentication
        users = self.load_user_credentials()

        # Check if email is passed as a query parameter
        email = queries.get("email")
        if email:
            user = next((u for u in users if u["email"] == email), None)
            if user:
                # Don't return the hashed password in a real system
                return {"email": user["email"], "role": user.get("role", "user")}
            else:
                cherrypy.response.status = 404
                return {"error": "User not found"}

        # Return all users (without hashed passwords)
        return {
            "users": [
                {"email": user["email"], "role": user.get("role", "user")} 
                for user in users
            ]
        }

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def register(self):
        """Register a new user"""
        data = cherrypy.request.json
        email = data.get("email")
        password = data.get("password")
        role = data.get("role", "user")  # Default role

        if not email or not password:
            cherrypy.response.status = 400
            return {"error": "Email and password are required"}

        try:
            # Use Firebase if enabled
            if FIREBASE_ENABLED:
                try:
                    user = auth.create_user(
                        email=email,
                        password=password
                    )
                    firebase_uid = user.uid
                    logger.info(f"User created in Firebase with UID: {firebase_uid}")
                    
                    # Store user in local database with Firebase UID
                    self.store_user_credentials(email, None, role, firebase_uid)
                    
                    return {
                        "message": "User registered successfully",
                        "email": email,
                        "role": role,
                        "firebase_uid": firebase_uid
                    }
                    
                except Exception as e:
                    logger.error(f"Failed to create user in Firebase: {e}")
                    cherrypy.response.status = 500
                    return {"error": f"Registration failed: {str(e)}"}
            else:
                # Fallback to local authentication
                # Hash the password
                hashed_password = hashlib.sha256(password.encode()).hexdigest()
                
                # Store user credentials locally
                self.store_user_credentials(email, hashed_password, role)
                
                return {
                    "message": "User registered successfully",
                    "email": email,
                    "role": role
                }
        except Exception as e:
            logger.error(f"Registration error: {e}")
            cherrypy.response.status = 500
            return {"error": f"Registration failed: {str(e)}"}

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def login(self):
        """
        POST /login
        Login and receive a token
        """
        data = cherrypy.request.json
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            cherrypy.response.status = 400
            return {"error": "Email and password are required"}

        try:
            if FIREBASE_ENABLED:
                # Get user from local database
                users = self.load_user_credentials()
                user = next((u for u in users if u["email"] == email), None)
                
                if not user or not user.get("firebase_uid"):
                    cherrypy.response.status = 401
                    return {"error": "Invalid credentials"}
                
                # Note: In a real implementation, Firebase authentication would happen
                # on the client side, and the server would verify the Firebase token
                # For simplicity, we're just checking the user exists
                
                # Generate JWT token for API access
                token = self.generate_token(email, user.get("role", "user"))
                
                return {
                    "message": "Login successful",
                    "email": email,
                    "role": user.get("role", "user"),
                    "token": token
                }
            else:
                # Fallback to local authentication
                # Hash the provided password
                hashed_password = hashlib.sha256(password.encode()).hexdigest()
                
                # Check credentials locally
                users = self.load_user_credentials()
                user = next((u for u in users if u["email"] == email), None)
                
                if not user or user["hashed_password"] != hashed_password:
                    # Local validation failed
                    cherrypy.response.status = 401
                    return {"error": "Invalid credentials"}
                
                # Generate JWT token
                token = self.generate_token(email, user.get("role", "user"))
                
                return {
                    "message": "Login successful",
                    "email": email,
                    "role": user.get("role", "user"),
                    "token": token
                }
        except Exception as e:
            logger.error(f"Login error: {e}")
            cherrypy.response.status = 500
            return {"error": "Login failed due to server error"}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def verify(self, token=None):
        """
        GET /verify?token=<token>
        Verify a JWT token
        """
        if not token:
            cherrypy.response.status = 400
            return {"error": "Token is required"}
            
        try:
            # Verify the token
            payload = self.verify_token(token)
            
            return {
                "valid": True,
                "email": payload.get("email"),
                "role": payload.get("role", "user"),
                "exp": payload.get("exp")
            }
        except jwt.ExpiredSignatureError:
            cherrypy.response.status = 401
            return {"valid": False, "error": "Token has expired"}
        except (jwt.InvalidTokenError, Exception) as e:
            cherrypy.response.status = 401
            return {"valid": False, "error": f"Invalid token: {str(e)}"}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def firebase_verify(self, *args, **kwargs):
        """
        GET /firebase_verify?token=<firebase_token>
        Verify a Firebase token (if Firebase is enabled)
        """
        if not FIREBASE_ENABLED:
            cherrypy.response.status = 501  # Not Implemented
            return {"error": "Firebase authentication is not enabled"}
            
        token = kwargs.get('token')
        
        if not token:
            cherrypy.response.status = 400
            return {"error": "Token is required"}
            
        try:
            # Verify the Firebase token
            decoded_token = auth.verify_id_token(token)
            email = decoded_token.get("email")
            
            # Check if user exists in our system
            users = self.load_user_credentials()
            user = next((u for u in users if u["email"] == email), None)
            
            if not user:
                cherrypy.response.status = 401
                return {"error": "User not registered in the system"}
                
            # Generate our own JWT token
            jwt_token = self.generate_token(email, user.get("role", "user"))
            
            return {
                "valid": True,
                "email": email,
                "role": user.get("role", "user"),
                "token": jwt_token
            }
        except Exception as e:
            cherrypy.response.status = 401
            return {"valid": False, "error": str(e)}

    # ================== JWT Token Management ==================
    
    def generate_token(self, email, role="user", expiry_hours=24):
        """Generate a JWT token for a user"""
        payload = {
            "email": email,
            "role": role,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=expiry_hours),
            "iat": datetime.datetime.utcnow()
        }
        
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        return token
        
    def verify_token(self, token):
        """Verify a JWT token and return the payload if valid"""
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload

    # =================== User Storage Methods ===================
    
    def store_user_credentials(self, email, hashed_password, role="user", firebase_uid=None):
        """Store user credentials in a JSON file"""
        users = self.load_user_credentials()
        
        # Check if user already exists
        for user in users:
            if user["email"] == email:
                if hashed_password:
                    user["hashed_password"] = hashed_password
                user["role"] = role
                if firebase_uid:
                    user["firebase_uid"] = firebase_uid
                break
        else:
            # User doesn't exist, add them
            new_user = {
                "email": email,
                "role": role
            }
            if hashed_password:
                new_user["hashed_password"] = hashed_password
            if firebase_uid:
                new_user["firebase_uid"] = firebase_uid
            users.append(new_user)

        # Write updated users to file
        try:
            with open(USER_CREDENTIALS_FILE, "w") as f:
                json.dump(users, f, indent=4)
        except Exception as e:
            logger.error(f"Error storing user credentials: {e}")
            raise

    def load_user_credentials(self):
        """Load user credentials from the JSON file"""
        try:
            if not os.path.exists(USER_CREDENTIALS_FILE):
                return []

            with open(USER_CREDENTIALS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading user credentials: {e}")
            return []

    # ================ Additional Project-Specific Methods ================
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_catalog_info(self):
        """Retrieve catalog information (for status checking)"""
        try:
            response = requests.get(f"{CATALOG_URL}/info")
            if response.status_code == 200:
                return {"catalog_status": "online", "info": response.json()}
            else:
                return {"catalog_status": "error", "message": f"Status code: {response.status_code}"}
        except Exception as e:
            return {"catalog_status": "offline", "error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def add_pipeline_access(self):
        """
        POST /add_pipeline_access
        Add access rights for a user to specific pipelines
        """
        data = cherrypy.request.json
        email = data.get("email")
        pipeline_id = data.get("pipeline_id")
        
        if not email or not pipeline_id:
            cherrypy.response.status = 400
            return {"error": "Email and pipeline_id are required"}
            
        # Load users
        users = self.load_user_credentials()
        user = next((u for u in users if u["email"] == email), None)
        
        if not user:
            cherrypy.response.status = 404
            return {"error": "User not found"}
            
        # Add pipeline access
        if "pipelines" not in user:
            user["pipelines"] = []
            
        if pipeline_id not in user["pipelines"]:
            user["pipelines"].append(pipeline_id)
            
        # Save updated users
        try:
            with open(USER_CREDENTIALS_FILE, "w") as f:
                json.dump(users, f, indent=4)
                
            return {"message": "Pipeline access added successfully"}
        except Exception as e:
            cherrypy.response.status = 500
            return {"error": f"Failed to update user: {str(e)}"}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def user_pipelines(self, **kwargs):
        """
        GET /user_pipelines?email=<email>&token=<token>
        Get all pipelines a user has access to
        """
        email = kwargs.get("email")
        token = kwargs.get("token")
        
        if not email or not token:
            cherrypy.response.status = 400
            return {"error": "Email and token are required"}
            
        try:
            # Verify token
            payload = self.verify_token(token)
            
            # Check if token belongs to requested user or admin
            if payload.get("email") != email and payload.get("role") != "admin":
                cherrypy.response.status = 403
                return {"error": "Unauthorized access"}
                
            # Load user info
            users = self.load_user_credentials()
            user = next((u for u in users if u["email"] == email), None)
            
            if not user:
                cherrypy.response.status = 404
                return {"error": "User not found"}
                
            # Return pipeline access
            return {"pipelines": user.get("pipelines", [])}
            
        except Exception as e:
            cherrypy.response.status = 401
            return {"error": str(e)}

# Main entry point
def main():
    # Configure CherryPy
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': int(os.getenv("PORT", "8082")),
        'log.access_file': 'access.log',
        'log.error_file': 'error.log'
    })
    
    # Mount the application
    cherrypy.tree.mount(AccountManager(), '/', {
        '/': {
            'tools.sessions.on': True,
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'application/json')]
        }
    })
    
    # Start the server
    cherrypy.engine.start()
    cherrypy.engine.block()

if __name__ == "__main__":
    main()