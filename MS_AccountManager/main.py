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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("AccountManager")

SERVICE_ID = os.getenv("SERVICE_ID", "account_manager")
CATALOG_URL = os.getenv("CATALOG_URL", "http://localhost:8080")
SECRET_KEY = os.getenv("JWT_SECRET", "your-secret-key")
USER_CREDENTIALS_FILE = os.getenv("USER_CREDENTIALS_FILE", "user_credentials.json")
FIREBASE_ENABLED = os.getenv("FIREBASE_ENABLED", "False").lower() == "true"

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
    def __init__(self):
        self.service_info = {
            "id": SERVICE_ID,
            "name": "AccountManager",
            "endpoint": self._get_public_endpoint(),
            "last_update": int(time.time())
        }
        self.register_with_catalog()
        cherrypy.engine.subscribe('start', self.start_update_thread)
        
    def _get_public_endpoint(self):
        host = cherrypy.server.socket_host
        port = cherrypy.server.socket_port
        if host == '0.0.0.0':
            import socket
            try:
                host = socket.gethostbyname(socket.gethostname())
            except:
                host = "localhost"
        return f"http://{host}:{port}"
        
    def register_with_catalog(self):
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
        def update_loop():
            while True:
                self.update_catalog()
                time.sleep(60)
                
        updater = threading.Thread(target=update_loop, daemon=True)
        updater.start()
        logger.info("Started catalog update thread")

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self):
        return {
            "message": "Smart IoT Bolt Account Manager API",
            "version": "1.0",
            "status": "running",
            "firebase_enabled": FIREBASE_ENABLED
        }

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def users(self, *params, **queries):
        users = self.load_user_credentials()
        email = queries.get("email")
        if email:
            user = next((u for u in users if u["email"] == email), None)
            if user:
                return {"email": user["email"], "role": user.get("role", "user")}
            else:
                cherrypy.response.status = 404
                return {"error": "User not found"}
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
        data = cherrypy.request.json
        email = data.get("email")
        password = data.get("password")
        role = data.get("role", "user")

        if not email or not password:
            cherrypy.response.status = 400
            return {"error": "Email and password are required"}

        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        try:
            self.store_user_credentials(email, hashed_password, role)
            firebase_uid = None
            if FIREBASE_ENABLED:
                try:
                    user = auth.create_user(
                        email=email,
                        password=password
                    )
                    firebase_uid = user.uid
                    logger.info(f"User created in Firebase with UID: {firebase_uid}")
                    self.store_user_credentials(email, hashed_password, role, firebase_uid)
                except Exception as e:
                    logger.warning(f"Failed to create user in Firebase: {e}")
            return {
                "message": "User registered successfully",
                "email": email,
                "role": role,
                "firebase_uid": firebase_uid
            }
        except Exception as e:
            logger.error(f"Registration error: {e}")
            cherrypy.response.status = 500
            return {"error": f"Registration failed: {str(e)}"}

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def login(self):
        data = cherrypy.request.json
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            cherrypy.response.status = 400
            return {"error": "Email and password are required"}

        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        users = self.load_user_credentials()
        user = next((u for u in users if u["email"] == email), None)
        
        if not user or user["hashed_password"] != hashed_password:
            cherrypy.response.status = 401
            return {"error": "Invalid credentials"}

        if FIREBASE_ENABLED and user.get("firebase_uid"):
            try:
                logger.info(f"Firebase validation would be performed for user {email}")
            except Exception as e:
                logger.warning(f"Firebase validation would have failed: {e}")

        token = self.generate_token(email, user.get("role", "user"))

        return {
            "message": "Login successful",
            "email": email,
            "role": user.get("role", "user"),
            "token": token
        }

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def verify(self, token=None):
        if not token:
            cherrypy.response.status = 400
            return {"error": "Token is required"}
            
        try:
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
        if not FIREBASE_ENABLED:
            cherrypy.response.status = 501
            return {"error": "Firebase authentication is not enabled"}
            
        token = kwargs.get('token')
        
        if not token:
            cherrypy.response.status = 400
            return {"error": "Token is required"}
            
        try:
            decoded_token = auth.verify_id_token(token)
            email = decoded_token.get("email")
            users = self.load_user_credentials()
            user = next((u for u in users if u["email"] == email), None)
            
            if not user:
                cherrypy.response.status = 401
                return {"error": "User not registered in the system"}
                
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

    def generate_token(self, email, role="user", expiry_hours=24):
        payload = {
            "email": email,
            "role": role,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=expiry_hours),
            "iat": datetime.datetime.utcnow()
        }
        
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        return token
        
    def verify_token(self, token):
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload

    def store_user_credentials(self, email, hashed_password, role="user", firebase_uid=None):
        users = self.load_user_credentials()
        
        for user in users:
            if user["email"] == email:
                user["hashed_password"] = hashed_password
                user["role"] = role
                if firebase_uid:
                    user["firebase_uid"] = firebase_uid
                break
        else:
            new_user = {
                "email": email, 
                "hashed_password": hashed_password,
                "role": role
            }
            if firebase_uid:
                new_user["firebase_uid"] = firebase_uid
            users.append(new_user)

        try:
            with open(USER_CREDENTIALS_FILE, "w") as f:
                json.dump(users, f, indent=4)
        except Exception as e:
            logger.error(f"Error storing user credentials: {e}")
            raise

    def load_user_credentials(self):
        try:
            if not os.path.exists(USER_CREDENTIALS_FILE):
                return []

            with open(USER_CREDENTIALS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading user credentials: {e}")
            return []

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_catalog_info(self):
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
        data = cherrypy.request.json
        email = data.get("email")
        pipeline_id = data.get("pipeline_id")
        
        if not email or not pipeline_id:
            cherrypy.response.status = 400
            return {"error": "Email and pipeline_id are required"}
            
        users = self.load_user_credentials()
        user = next((u for u in users if u["email"] == email), None)
        
        if not user:
            cherrypy.response.status = 404
            return {"error": "User not found"}
            
        if "pipelines" not in user:
            user["pipelines"] = []
            
        if pipeline_id not in user["pipelines"]:
            user["pipelines"].append(pipeline_id)
            
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
        email = kwargs.get("email")
        token = kwargs.get("token")
        
        if not email or not token:
            cherrypy.response.status = 400
            return {"error": "Email and token are required"}
            
        try:
            payload = self.verify_token(token)
            
            if payload.get("email") != email and payload.get("role") != "admin":
                cherrypy.response.status = 403
                return {"error": "Unauthorized access"}
                
            users = self.load_user_credentials()
            user = next((u for u in users if u["email"] == email), None)
            
            if not user:
                cherrypy.response.status = 404
                return {"error": "User not found"}
                
            return {"pipelines": user.get("pipelines", [])}
            
        except Exception as e:
            cherrypy.response.status = 401
            return {"error": str(e)}

def main():
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': int(os.getenv("PORT", "8082")),
        'log.access_file': 'access.log',
        'log.error_file': 'error.log'
    })
    
    cherrypy.tree.mount(AccountManager(), '/', {
        '/': {
            'tools.sessions.on': True,
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'application/json')]
        }
    })
    
    cherrypy.engine.start()
    cherrypy.engine.block()

if __name__ == "__main__":
    main()