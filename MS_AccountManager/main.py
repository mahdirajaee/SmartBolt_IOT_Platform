import cherrypy
import json
import firebase_admin
from firebase_admin import credentials, auth
import os
import hashlib

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
    def GET(self, *path, **queries):
        """
        Handles GET requests.
        - If `/users` is accessed, it returns stored user credentials (email + hashed passwords).
        - If `/users/{email}` is accessed, it returns only that user's hashed password.
        """
        if not path:
            return {"error": "Invalid request. Please specify a resource."}

        if path[0] == "users":
            users = self.load_user_credentials()

            if len(path) == 1:
                # Return all users
                return {"users": users}

            elif len(path) == 2:
                # Return specific user by email
                email = path[1]
                user = next((u for u in users if u["email"] == email), None)

                if user:
                    return {"email": user["email"], "hashed_password": user["hashed_password"]}
                else:
                    cherrypy.response.status = 404
                    return {"error": "User not found"}

        cherrypy.response.status = 400
        return {"error": "Invalid endpoint"}

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def POST(self, *path, **queries):
        """
        Handles POST requests.
        - If `/register` is accessed, it registers a user (email, password).
        - Hashes the password and stores it in `user_credentials.json`.
        """
        if not path or path[0] != "register":
            cherrypy.response.status = 400
            return {"error": "Invalid request"}

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
    
    #this method will verify the token and return the user email
    def protected(self, token=None):
        """Verify Firebase Authentication token"""
        if not token:
            cherrypy.response.status = 401
            return {"error": "Token required"}

        try:
            decoded_token = auth.verify_id_token(token)
            return {"message": "Access granted", "user": decoded_token["email"]}
        except Exception as e:
            cherrypy.response.status = 401
            return {"error": str(e)}

if __name__ == "__main__":
    cherrypy.config.update({
        "server.socket_host": "0.0.0.0",
        "server.socket_port": int(os.getenv("PORT", 8081)),
    })
    cherrypy.quickstart(AccountManager(), "/")
