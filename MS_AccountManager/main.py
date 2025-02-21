import cherrypy
import json
import firebase_admin
from firebase_admin import credentials, auth
import os


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FIREBASE_CRED_PATH = os.path.join(BASE_DIR, "firebase_credentials.json")

# Load Firebase Credentials 
cred = credentials.Certificate(FIREBASE_CRED_PATH)
firebase_admin.initialize_app(cred)

#this class will handle the user authentication using Firebase
class AccountManager:
    """Handles user authentication using Firebase"""

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def register(self):
        """Registers a new user using Firebase Authentication"""
        data = cherrypy.request.json
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            cherrypy.response.status = 400
            return {"error": "Email and password are required"}

        try:
            user = auth.create_user(email=email, password=password)
            return {"message": "User registered successfully", "uid": user.uid}
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
    #retrieve the all users
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def allusers(self):
        """Retrieve all users"""
        users = auth.list_users()
        return {"users": [user.email for user in users.users]}

if __name__ == "__main__":
    cherrypy.config.update({
        "server.socket_host": "0.0.0.0",
        "server.socket_port": int(os.getenv("PORT", 8081)),
    })
    cherrypy.quickstart(AccountManager(), "/")
