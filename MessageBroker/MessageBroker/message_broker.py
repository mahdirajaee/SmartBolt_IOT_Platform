import os
import signal
import subprocess
import time
import logging
import requests
import threading
import socket
import shutil
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('MessageBroker')

class MessageBroker:
    def __init__(self):
        self.mqtt_port = int(os.getenv('MQTT_PORT', '1883'))
        self.mqtt_host = os.getenv('MQTT_HOST', '0.0.0.0')
        self.catalog_url = os.getenv('CATALOG_URL', 'http://localhost:8080')
        self.mosquitto_path = os.getenv('MOSQUITTO_PATH', None)
        self.service_id = "message_broker"
        self.topics = [
            "/sensor/temperature/{sector_id}/{device_id}",
            "/sensor/pressure/{sector_id}/{device_id}",
            "/actuator/valve/{sector_id}/{device_id}"
        ]
        self.process = None
        self.running = False

    def check_mosquitto_installed(self):
        try:
            mosquitto_cmd = self.mosquitto_path or 'mosquitto'
            mosquitto_path = shutil.which(mosquitto_cmd)
            if mosquitto_path:
                logger.info(f"Found Mosquitto at: {mosquitto_path}")
                return mosquitto_path
            else:
                logger.error("Mosquitto executable not found in PATH")
                return None
        except Exception as e:
            logger.error(f"Error checking Mosquitto installation: {str(e)}")
            return None

    def check_port_available(self):
        """
        Check if the configured MQTT port is available.
        If the port from .env is in use, try to find an alternative port.
        Returns True if the original port is available or if an alternative was found.
        """
        try:
            # Get the original port from .env for reference
            original_port = self.mqtt_port
            
            # Check if the configured port is available
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            result = s.connect_ex((self.mqtt_host, self.mqtt_port))
            s.close()
            
            if result == 0:
                logger.warning(f"Port {self.mqtt_port} from .env is already in use")
                
                # Define potential alternative ports
                # First try +1, +2, etc. from the original port
                alt_ports = []
                # Add ports close to the original port first (up to 10 higher)
                for i in range(1, 11):
                    alt_ports.append(original_port + i)
                # Then add some standard MQTT ports if they aren't already in the list
                for std_port in [1883, 1884, 1885, 1886, 8883]:
                    if std_port != original_port and std_port not in alt_ports:
                        alt_ports.append(std_port)
                
                # Try each alternative port
                for alt_port in alt_ports:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(1)
                    result = s.connect_ex((self.mqtt_host, alt_port))
                    s.close()
                    if result != 0:
                        logger.info(f"Found available alternative port: {alt_port}")
                        logger.info(f"Switching from configured port {original_port} to available port {alt_port}")
                        self.mqtt_port = alt_port
                        
                        # Update mosquitto.conf if it exists
                        try:
                            if os.path.exists('mosquitto.conf'):
                                with open('mosquitto.conf', 'r') as f:
                                    lines = f.readlines()
                                
                                with open('mosquitto.conf', 'w') as f:
                                    for line in lines:
                                        if line.startswith('listener'):
                                            f.write(f"listener {self.mqtt_port} {self.mqtt_host}\n")
                                        else:
                                            f.write(line)
                                logger.info(f"Updated mosquitto.conf with new port {self.mqtt_port}")
                        except Exception as e:
                            logger.error(f"Error updating mosquitto.conf: {str(e)}")
                        
                        # Update .env file for future runs
                        self.update_env_file(original_port, self.mqtt_port)
                        
                        return True
                
                logger.error("Could not find any available alternative port")
                return False
            
            logger.info(f"Using port {self.mqtt_port} from .env file")
            return True
        except Exception as e:
            logger.error(f"Error checking port availability: {str(e)}")
            return False

    def create_config(self):
        try:
            config_path = 'mosquitto.conf'
            with open(config_path, 'w') as f:
                f.write(f"listener {self.mqtt_port} {self.mqtt_host}\n")
                f.write("allow_anonymous true\n")
                f.write("persistence true\n")
                f.write("persistence_location ./mosquitto_data/\n")
                f.write("log_dest file mosquitto.log\n")
                f.write("log_type all\n")
            os.makedirs('./mosquitto_data', exist_ok=True)
            logger.info(f"Created Mosquitto configuration at {os.path.abspath(config_path)}")
            return config_path
        except Exception as e:
            logger.error(f"Error creating configuration file: {str(e)}")
            return None

    def register_with_catalog(self):
        try:
            # Register as a standard service with proper format
            service_info = {
                "name": self.service_id,
                "endpoint": f"mqtt://{self.mqtt_host}:{self.mqtt_port}",
                "port": self.mqtt_port,
                "last_seen": time.time(),
                "status": "active",
                "additional_info": {
                    "service_type": "mqtt_broker",
                    "topics": self.topics,
                    "address": self.mqtt_host,
                    "broker": self.mqtt_host
                }
            }
            
            # Register using the /service endpoint as expected by other services
            response = requests.post(
                f"{self.catalog_url}/service",
                json=service_info
            )
            if response.status_code in (200, 201):
                logger.info(f"Successfully registered with catalog")

                # Register a specific broker endpoint for backward compatibility
                broker_info = {
                    "broker": self.mqtt_host,
                    "address": self.mqtt_host,
                    "port": self.mqtt_port,
                    "topics": self.topics
                }
                
                # Create a custom broker endpoint in the catalog
                try:
                    broker_response = requests.post(
                        f"{self.catalog_url}/broker",
                        json=broker_info
                    )
                    if broker_response.status_code in (200, 201, 404):
                        # If 404, the endpoint might not exist yet, which is ok
                        logger.info("Registered broker information at /broker endpoint")
                except Exception as e:
                    logger.warning(f"Could not create broker endpoint (will continue): {str(e)}")
                
                return True
            else:
                logger.error(f"Failed to register with catalog: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error registering with catalog: {str(e)}")
            return False

    def send_heartbeat(self):
        while self.running:
            try:
                # Update service status
                service_info = {
                    "status": "active",
                    "last_seen": time.time()
                }
                response = requests.put(
                    f"{self.catalog_url}/service/{self.service_id}",
                    json=service_info
                )
                if response.status_code != 200:
                    logger.warning(f"Heartbeat update failed: {response.status_code}")
                    
                    # Try to re-register if update fails
                    if response.status_code == 404:
                        logger.info("Service not found in catalog, re-registering...")
                        self.register_with_catalog()
                
            except Exception as e:
                logger.error(f"Error sending heartbeat: {str(e)}")
            time.sleep(60)

    def start(self):
        mosquitto_path = self.check_mosquitto_installed()
        if not mosquitto_path:
            logger.error("Cannot start broker: Mosquitto is not installed or not in PATH")
            logger.info("You can install Mosquitto or set MOSQUITTO_PATH in your .env file")
            return False
            
        # Try to use the port from .env, with fallback to alternative ports if necessary
        logger.info(f"Checking availability of MQTT port {self.mqtt_port} from .env")
        if not self.check_port_available():
            logger.error(f"Cannot start broker: No available ports found")
            return False
            
        try:
            config_path = self.create_config()
            if not config_path:
                return False
                
            logger.info(f"Starting Mosquitto broker on {self.mqtt_host}:{self.mqtt_port}")
            self.process = subprocess.Popen(
                [mosquitto_path, '-c', config_path, '-v'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            time.sleep(2)
            if self.process.poll() is None:
                logger.info("Mosquitto broker started successfully")
                self.running = True
                threading.Thread(target=self._monitor_output, daemon=True).start()
                try:
                    self.register_with_catalog()
                    self.heartbeat_thread = threading.Thread(target=self.send_heartbeat)
                    self.heartbeat_thread.daemon = True
                    self.heartbeat_thread.start()
                except Exception as e:
                    logger.warning(f"Could not register with catalog (will continue): {str(e)}")
                return True
            else:
                stdout, stderr = self.process.communicate()
                logger.error(f"Failed to start Mosquitto. Exit code: {self.process.returncode}")
                if stdout:
                    logger.error(f"Stdout: {stdout}")
                if stderr:
                    logger.error(f"Stderr: {stderr}")
                return False
        except Exception as e:
            logger.error(f"Error starting broker: {str(e)}")
            return False

    def _monitor_output(self):
        try:
            for line in self.process.stdout:
                logger.info(f"Mosquitto: {line.strip()}")
            for line in self.process.stderr:
                logger.error(f"Mosquitto Error: {line.strip()}")
        except Exception as e:
            logger.error(f"Error monitoring Mosquitto output: {str(e)}")

    def stop(self):
        if self.process and self.process.poll() is None:
            logger.info("Stopping Mosquitto broker")
            self.running = False
            try:
                service_info = {
                    "status": "stopping"
                }
                requests.put(
                    f"{self.catalog_url}/service/{self.service_id}",
                    json=service_info
                )
            except Exception as e:
                logger.error(f"Error updating status: {str(e)}")
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
                logger.info("Mosquitto broker stopped")
            except subprocess.TimeoutExpired:
                logger.warning("Broker did not stop gracefully, forcing kill")
                self.process.kill()
            self.process = None
            return True
        return False

    def run(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        if self.start():
            logger.info("Message Broker is running. Press CTRL+C to stop.")
            while self.process and self.process.poll() is None:
                time.sleep(1)
            if self.process:
                exit_code = self.process.returncode
                logger.info(f"Broker process exited with code {exit_code}")
                return exit_code
            return 0
        else:
            return 1

    def signal_handler(self, sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        self.stop()

    def update_env_file(self, original_port, new_port):
        """
        Update the .env file with the new port when a fallback port is used.
        This helps ensure that subsequent runs use the working port.
        """
        try:
            env_file = os.path.join(os.getcwd(), '.env')
            if not os.path.exists(env_file):
                logger.warning("No .env file found to update")
                return False
                
            # Read the current .env file
            with open(env_file, 'r') as f:
                lines = f.readlines()
                
            # Check if we need to update or add the MQTT_PORT
            port_updated = False
            new_lines = []
            
            for line in lines:
                if line.strip().startswith('MQTT_PORT='):
                    new_lines.append(f'MQTT_PORT={new_port}\n')
                    port_updated = True
                else:
                    new_lines.append(line)
            
            # If MQTT_PORT wasn't in the file, add it
            if not port_updated:
                new_lines.append(f'MQTT_PORT={new_port}\n')
                
            # Write the updated .env file
            with open(env_file, 'w') as f:
                f.writelines(new_lines)
                
            logger.info(f"Updated .env file: MQTT_PORT changed from {original_port} to {new_port}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating .env file: {str(e)}")
            return False

if __name__ == "__main__":
    broker = MessageBroker()
    exit_code = broker.run()
    exit(exit_code)