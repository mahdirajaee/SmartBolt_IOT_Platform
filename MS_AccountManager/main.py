import cherrypy
import json
import jwt
import datetime
import bcrypt
import os

SECRET_KEY = "your_secret_key"

users_db = {}  # In-memory user storage (replace with database in production)


class AccountManager:
    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def register(self):
        """Register a new user"""
        data = cherrypy.request.json
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            cherrypy.response.status = 400
            return {"error": "Username and password are required"}

        if username in users_db:
            cherrypy.response.status = 409
            return {"error": "User already exists"}

        hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
        users_db[username] = hashed_password

        return {"message": "User registered successfully"}

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def login(self):
        """Authenticate user and return a JWT token"""
        data = cherrypy.request.json
        username = data.get("username")
        password = data.get("password")

        if username not in users_db:
            cherrypy.response.status = 401
            return {"error": "Invalid username or password"}

        if not bcrypt.checkpw(password.encode(), users_db[username]):
            cherrypy.response.status = 401
            return {"error": "Invalid username or password"}

        token = jwt.encode(
            {"username": username, "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=1)},
            SECRET_KEY,
            algorithm="HS256",
        )
        return {"token": token}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def protected(self, token=None):
        """Protected route, accessible only with a valid JWT"""
        if not token:
            cherrypy.response.status = 401
            return {"error": "Token required"}

        try:
            decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            return {"message": "Access granted", "user": decoded["username"]}
        except jwt.ExpiredSignatureError:
            cherrypy.response.status = 401
            return {"error": "Token expired"}
        except jwt.InvalidTokenError:
            cherrypy.response.status = 401
            return {"error": "Invalid token"}


if __name__ == "__main__":
    cherrypy.config.update({"server.socket_host": "0.0.0.0", "server.socket_port": 8081})
    cherrypy.quickstart(AccountManager(), "/")
