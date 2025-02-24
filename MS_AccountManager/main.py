import cherrypy
import json
import firebase_admin
from firebase_admin import credentials, auth
import os
import hashlib

# Setup paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FIREBASE_CRED_PATH = os.path.join(BASE_DIR, "firebase_credentials.json")
USER_CREDENTIALS_FILE = os.path.join(BASE_DIR, "user_credentials.json")

# Load Firebase Credentials
cred = credentials.Certificate(FIREBASE_CRED_PATH)
firebase_admin.initialize_app(cred)


class AccountManager:
    """Handles user authentication using Firebase"""

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self):
        """Default response"""
        return {"message": "Welcome to the Account Manager API"}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def users(self, email=None):
        """
        Handles GET requests:
        - `/users` -> returns all users.
        - `/users?email=email@example.com` -> returns only that user's hashed password.
        """
        users = self.load_user_credentials()

        if email:
            user = next((u for u in users if u["email"] == email), None)
            if user:
                return {"email": user["email"], "hashed_password": user["hashed_password"]}
            else:
                cherrypy.response.status = 404
                return {"error": "User not found"}

        return {"users": users}

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def register(self):
        """
        Handles POST request to `/register`
        - Registers a user with Firebase Authentication.
        - Hashes the password and stores it locally in `user_credentials.json`.
        """
        data = cherrypy.request.json
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            cherrypy.response.status = 400
            return {"error": "Email and password are required"}

        # Hash the password
        hashed_password = hashlib.sha256(password.encode()).hexdigest()

        try:
            # Create user in Firebase
            user = auth.create_user(email=email, password=password)

            # Store user credentials (email + hashed password)
            self.store_user_credentials(email, hashed_password)

            return {
                "message": "User registered successfully",
                "uid": user.uid,
                "hashed_password": hashed_password  # To verify it was stored
            }
        except Exception as e:
            cherrypy.response.status = 400
            return {"error": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def protected(self, token=None):
        """
        Verify Firebase Authentication token
        """
        if not token:
            cherrypy.response.status = 401
            return {"error": "Token required"}

        try:
            decoded_token = auth.verify_id_token(token)
            return {"message": "Access granted", "user": decoded_token["email"]}
        except Exception as e:
            cherrypy.response.status = 401
            return {"error": str(e)}

    # =========== User Storage Helpers ================
    def store_user_credentials(self, email, hashed_password):
        """Store user credentials in a JSON file"""
        users = self.load_user_credentials()
        users.append({"email": email, "hashed_password": hashed_password})

        with open(USER_CREDENTIALS_FILE, "w") as f:
            json.dump(users, f, indent=4)

    def load_user_credentials(self):
        """Load user credentials from the JSON file"""
        if not os.path.exists(USER_CREDENTIALS_FILE):
            return []

        with open(USER_CREDENTIALS_FILE, "r") as f:
            return json.load(f)


# ============= CherryPy Server Configuration ==============
if __name__ == "__main__":
    cherrypy.config.update({
        "server.socket_host": "0.0.0.0",
        "server.socket_port": int(os.getenv("PORT", 8081)),
    })
    cherrypy.quickstart(AccountManager(), "/")
