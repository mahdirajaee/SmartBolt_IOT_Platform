import cherrypy
import requests
import os
import json

# Load environment variables or default values
RESOURCE_CATALOG_URL = os.getenv("RESOURCE_CATALOG_URL", "http://localhost:5000")
MICROSERVICE_NAME = "MS_ControlCenter"
MICROSERVICE_HOST = os.getenv("CONTROL_CENTER_HOST", "localhost")
MICROSERVICE_PORT = int(os.getenv("CONTROL_CENTER_PORT", 5002))

class ControlCenter:
    def __init__(self):
        self.services = {}  # To store available services

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self):
        return {"message": "Control Center is running."}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def get_services(self):
        """Fetches all registered services from the Resource Catalog."""
        try:
            response = requests.get(f"{RESOURCE_CATALOG_URL}/services")
            if response.status_code == 200:
                self.services = response.json()
                return {"status": "success", "services": self.services}
            else:
                return {"status": "error", "message": "Failed to retrieve services"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def restart_service(self, service_name):
        """Simulates restarting a service."""
        if service_name in self.services:
            # Here, we would send a request or command to restart the service.
            # In a real setup, we might use Docker, Kubernetes, or system commands.
            return {"status": "success", "message": f"{service_name} restarted."}
        return {"status": "error", "message": "Service not found"}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def trigger_action(self, service_name, action):
        """Triggers a specific action in a microservice."""
        if service_name in self.services:
            service_url = self.services[service_name].get("url", "")
            try:
                response = requests.post(f"{service_url}/action", json={"action": action})
                return response.json()
            except Exception as e:
                return {"status": "error", "message": str(e)}
        return {"status": "error", "message": "Service not found"}

def register_with_resource_catalog():
    """Registers the Control Center with the Resource Catalog."""
    registration_data = {
        "name": MICROSERVICE_NAME,
        "url": f"http://{MICROSERVICE_HOST}:{MICROSERVICE_PORT}"
    }
    try:
        response = requests.post(f"{RESOURCE_CATALOG_URL}/register", json=registration_data)
        if response.status_code == 200:
            print("Successfully registered with Resource Catalog.")
        else:
            print("Failed to register with Resource Catalog.")
    except Exception as e:
        print(f"Error registering with Resource Catalog: {e}")

if __name__ == "__main__":
    # Register with Resource Catalog on startup
    register_with_resource_catalog()

    cherrypy.config.update({
        "server.socket_host": MICROSERVICE_HOST,
        "server.socket_port": MICROSERVICE_PORT
    })
    cherrypy.quickstart(ControlCenter())
