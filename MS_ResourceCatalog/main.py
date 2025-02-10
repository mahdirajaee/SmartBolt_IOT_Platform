import cherrypy
import json

class ResourceCatalog:
    def __init__(self):
        """Initialize the service catalog as an empty dictionary."""
        self.services = {}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self):
        """Returns a welcome message when accessing the root URL."""
        return {"message": "Resource Catalog API is running."}

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def register(self):
        """
        Registers a new microservice.
        Expected JSON input:
        {
            "name": "MS_Example",
            "ip": "192.168.1.100",
            "port": 8080
        }
        """
        data = cherrypy.request.json
        name = data.get("name")
        ip = data.get("ip")
        port = data.get("port")

        if not name or not ip or not port:
            cherrypy.response.status = 400
            return {"error": "Missing name, ip, or port fields."}

        self.services[name] = {"ip": ip, "port": port}
        return {"message": f"Service '{name}' registered successfully."}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def services(self, name=None):
        """
        Returns all registered services or a specific service by name.
        Example Usage:
        - `/services` → Returns all services.
        - `/services?name=MS_Example` → Returns details for "MS_Example".
        """
        if name:
            return self.services.get(name, {"error": "Service not found."})
        return self.services

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def health(self):
        """Simple health check endpoint to confirm the service is running."""
        return {"status": "OK"}

if __name__ == '__main__':
    cherrypy.config.update({'server.socket_host': '0.0.0.0', 'server.socket_port': 5000})
    cherrypy.quickstart(ResourceCatalog())
