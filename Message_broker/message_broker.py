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

# Load environment variables at the module level
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('MessageBroker')

class MessageBroker:
    def __init__(self):
        # Get configuration from environment or set defaults
        self.mqtt_port = int(os.getenv('MQTT_PORT', '1884'))  # Changed default to 1884
        self.mqtt_host = os.getenv('MQTT_HOST', '0.0.0.0')
        self.catalog_url = os.getenv('CATALOG_URL', 'http://localhost:8080')
        
        # Custom mosquitto path (if provided)
        self.mosquitto_path = os.getenv('MOSQUITTO_PATH', None)
        
        # Service ID for registration
        self.service_id = "message_broker"
        
        # Topic structure as defined in documentation
        self.topics = [
            "/sensor/temperature/{sector_id}/{device_id}",
            "/sensor/pressure/{sector_id}/{device_id}",
            "/actuator/valve/{sector_id}/{device_id}"
        ]
        
        # Mosquitto process reference
        self.process = None
        self.running = False
    
    def check_mosquitto_installed(self):
        """Check if Mosquitto is installed and available"""
        try:
            # Try to find mosquitto in PATH
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
        """Check if the MQTT port is available"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1)
            result = s.connect_ex((self.mqtt_host, self.mqtt_port))
            s.close()
            
            if result == 0:
                logger.error(f"Port {self.mqtt_port} is already in use")
                # Try alternative ports if the configured one is not available
                for alt_port in [1884, 1885, 1886, 8883]:
                    if alt_port != self.mqtt_port:
                        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        s.settimeout(1)
                        result = s.connect_ex((self.mqtt_host, alt_port))
                        s.close()
                        if result != 0:
                            logger.info(f"Found available alternative port: {alt_port}")
                            self.mqtt_port = alt_port
                            return True
                return False
            return True
        except Exception as e:
            logger.error(f"Error checking port availability: {str(e)}")
            return False
    
    def create_config(self):
        """Create a basic Mosquitto configuration file"""
        try:
            config_path = 'mosquitto.conf'
            with open(config_path, 'w') as f:
                f.write(f"listener {self.mqtt_port} {self.mqtt_host}\n")
                f.write("allow_anonymous true\n")  # For simplicity in development
                f.write("persistence true\n")
                f.write("persistence_location ./mosquitto_data/\n")
                f.write("log_dest file mosquitto.log\n")
                f.write("log_type all\n")  # Enable all logs for debugging
            
            # Create persistence directory if it doesn't exist
            os.makedirs('./mosquitto_data', exist_ok=True)
            
            logger.info(f"Created Mosquitto configuration at {os.path.abspath(config_path)}")
            return config_path
        except Exception as e:
            logger.error(f"Error creating configuration file: {str(e)}")
            return None
    
    def register_with_catalog(self):
        """Register the broker with the resource catalog"""
        try:
            service_info = {
                "service_id": self.service_id,
                "service_type": "mqtt_broker",
                "endpoint": f"mqtt://{self.mqtt_host}:{self.mqtt_port}",
                "topics": self.topics,
                "status": "active",
                "last_update": int(time.time())
            }
            
            response = requests.post(
                f"{self.catalog_url}/services",
                json=service_info
            )
            
            if response.status_code in (200, 201):
                logger.info(f"Successfully registered with catalog")
                return True
            else:
                logger.error(f"Failed to register with catalog: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error registering with catalog: {str(e)}")
            return False
    
    def send_heartbeat(self):
        """Send periodic heartbeats to the resource catalog"""
        while self.running:
            try:
                service_info = {
                    "service_id": self.service_id,
                    "status": "active",
                    "last_update": int(time.time())
                }
                
                response = requests.put(
                    f"{self.catalog_url}/services/{self.service_id}",
                    json=service_info
                )
                
                if response.status_code != 200:
                    logger.warning(f"Heartbeat update failed: {response.status_code}")
            except Exception as e:
                logger.error(f"Error sending heartbeat: {str(e)}")
            
            # Sleep for 60 seconds before next heartbeat
            time.sleep(60)
    
    def start(self):
        """Start the MQTT broker"""
        # Check if Mosquitto is installed
        mosquitto_path = self.check_mosquitto_installed()
        if not mosquitto_path:
            logger.error("Cannot start broker: Mosquitto is not installed or not in PATH")
            logger.info("You can install Mosquitto or set MOSQUITTO_PATH in your .env file")
            return False
        
        # Check if port is available
        if not self.check_port_available():
            logger.error(f"Cannot start broker: Port {self.mqtt_port} is already in use")
            return False
        
        try:
            # Create configuration file
            config_path = self.create_config()
            if not config_path:
                return False
            
            # Start Mosquitto process
            logger.info(f"Starting Mosquitto broker on {self.mqtt_host}:{self.mqtt_port}")
            
            self.process = subprocess.Popen(
                [mosquitto_path, '-c', config_path, '-v'],  # Added -v for verbose output
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,  # Use text mode for easier reading of output
                bufsize=1  # Line-buffered
            )
            
            # Wait briefly for broker to start
            time.sleep(2)
            
            # Check if process is still running
            if self.process.poll() is None:
                logger.info("Mosquitto broker started successfully")
                self.running = True
                
                # Start output monitoring in a separate thread
                threading.Thread(target=self._monitor_output, daemon=True).start()
                
                # Register with catalog (skip for now if the catalog is not ready)
                try:
                    self.register_with_catalog()
                    # Start heartbeat thread
                    self.heartbeat_thread = threading.Thread(target=self.send_heartbeat)
                    self.heartbeat_thread.daemon = True
                    self.heartbeat_thread.start()
                except Exception as e:
                    logger.warning(f"Could not register with catalog (will continue): {str(e)}")
                
                return True
            else:
                # Process exited immediately
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
        """Monitor and log the output of the Mosquitto process"""
        try:
            for line in self.process.stdout:
                logger.info(f"Mosquitto: {line.strip()}")
            for line in self.process.stderr:
                logger.error(f"Mosquitto Error: {line.strip()}")
        except Exception as e:
            logger.error(f"Error monitoring Mosquitto output: {str(e)}")
    
    def stop(self):
        """Stop the MQTT broker"""
        if self.process and self.process.poll() is None:
            logger.info("Stopping Mosquitto broker")
            self.running = False
            
            # Update status in catalog
            try:
                service_info = {
                    "service_id": self.service_id,
                    "status": "stopping",
                    "last_update": int(time.time())
                }
                
                requests.put(
                    f"{self.catalog_url}/services/{self.service_id}",
                    json=service_info
                )
            except Exception as e:
                logger.error(f"Error updating status: {str(e)}")
            
            # Terminate process
            self.process.terminate()
            
            try:
                # Wait for process to terminate
                self.process.wait(timeout=5)
                logger.info("Mosquitto broker stopped")
            except subprocess.TimeoutExpired:
                logger.warning("Broker did not stop gracefully, forcing kill")
                self.process.kill()
            
            self.process = None
            return True
        
        return False
    
    def run(self):
        """Run the broker and keep it running"""
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        if self.start():
            logger.info("Message Broker is running. Press CTRL+C to stop.")
            
            # Keep running until process exits
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
        """Handle termination signals"""
        logger.info(f"Received signal {sig}, shutting down...")
        self.stop()

if __name__ == "__main__":
    broker = MessageBroker()
    exit_code = broker.run()
    exit(exit_code)