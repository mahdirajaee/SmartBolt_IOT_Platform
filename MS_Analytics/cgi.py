#!/usr/bin/env python3
import os
import subprocess
import time
import sys
import signal
import socket

# Get the absolute path of the project directory
project_dir = os.path.dirname(os.path.abspath(__file__))

# Keep track of opened terminal windows
terminal_processes = []

# Function to check if a port is in use
def is_port_in_use(port, host='localhost'):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex((host, port)) == 0

# Function to find an available port starting from the preferred port
def find_available_port(preferred_port, max_attempts=10):
    port = preferred_port
    attempts = 0
    
    while attempts < max_attempts:
        if not is_port_in_use(port):
            return port
        port += 1
        attempts += 1
    
    raise RuntimeError(f"Could not find an available port after {max_attempts} attempts")

# Check and install required packages
def check_and_install_packages():
    print("\n🔍 Checking for required Python packages...")
    
    required_packages = {
        # Core dependencies
        "paho-mqtt": "paho-mqtt==2.1.0",  # MQTT client (correct version)
        "cherrypy": "cherrypy==18.8.0",    # Web framework (consistent version)
        "requests": "requests==2.31.0",    # HTTP requests
        "python-dotenv": "python-dotenv==1.0.0",  # Environment variable management
        
        # Database
        "influxdb-client": "influxdb-client==1.36.1",  # InfluxDB client
        
        # Telegram Bot
        "python-telegram-bot": "python-telegram-bot==20.4",
        
        # Authentication
        "pyjwt": "pyjwt==2.8.0",  # JWT for authentication
        
        # Analytics dependencies
        "numpy": "numpy==1.26.0",
        "pandas": "pandas==2.1.0",
        "statsmodels": "statsmodels==0.14.0",  # For ARIMA models
        
        # Additional utilities
        "urllib3": "urllib3==2.0.4",  # Required by requests
        "httpx": "httpx==0.25.0",     # Modern HTTP client (used by python-telegram-bot)
    }
    
    packages_to_install = []
    
    for package, install_name in required_packages.items():
        try:
            __import__(package.replace("-", "_"))
            print(f"✅ {package} is installed")
        except ImportError:
            print(f"❌ {package} is missing")
            packages_to_install.append(install_name)
    
    if packages_to_install:
        print("\n📦 Installing missing packages...")
        install_cmd = f"pip3 install {' '.join(packages_to_install)}"
        print(f"Running: {install_cmd}")
        
        try:
            subprocess.run(install_cmd, shell=True, check=True)
            print("✅ Packages installed successfully")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install packages: {e}")
            sys.exit(1)
    else:
        print("\n✅ All required packages are installed")

# Define a function to open a terminal with the command
def open_terminal_with_command(directory, command, title, env_vars=None):
    # Create full path to the directory
    full_path = os.path.join(project_dir, directory)
    
    # Prepare environment variables string if any
    env_vars_str = ""
    if env_vars:
        env_vars_str = " ".join([f"export {key}={value};" for key, value in env_vars.items()])
    
    # Create the AppleScript command to open a new terminal window
    # and execute the command in the specified directory
    applescript = f'''
    tell application "Terminal"
        do script "cd '{full_path}' && echo '=== Starting {title} ===' && {env_vars_str} {command}"
        set custom title of front window to "{title}"
    end tell
    '''
    
    # Execute the AppleScript command
    result = subprocess.run(['osascript', '-e', applescript], capture_output=True, text=True)
    if result.stderr:
        print(f"Warning when starting {title}: {result.stderr}")
    return result

# Define the services to run
services = [
    {
        "name": "Resource Catalog",
        "directory": "MS_ResourceCatalog",
        "command": "python3 ResourceCatalog.py",
        "delay": 5,  # Increased delay to ensure Resource Catalog is fully initialized
        "port": 8080,
        "env_vars": {
            "RESOURCE_CATALOG_PORT": "8080",
            "ENABLE_AUTH": "false",
            "DEBUG": "true"
        }
    },
    {
        "name": "Message Broker",
        "directory": "MessageBroker",
        "command": "python3 message_broker.py",
        "delay": 3,
        "port": 1883,
        "env_vars": {
            "MQTT_PORT": "1883",  # Ensure consistent port
            "CATALOG_URL": "http://localhost:8080"
        }
    },
    {
        "name": "TimeSeriesDB Connector",
        "directory": "MS_TimeSeriesDBConnector",
        "command": "python3 TimeSeriesDBConnector.py",
        "delay": 1,
        "port": 8081,
        "env_vars": {
            "CATALOG_URL": "http://localhost:8080",
            "SERVICE_PORT": "8081",
            "MQTT_BROKER": "localhost",
            "MQTT_PORT": "1883",
            "INFLUXDB_URL": "http://localhost:8086",
            "INFLUXDB_TOKEN": "mydevtoken123",  # Default for development, replace with your token
            "INFLUXDB_ORG": "smart_iot",
            "INFLUXDB_BUCKET": "sensor_data"
        }
    },
    {
        "name": "Control Center",
        "directory": "MS_ControlCenter",
        "command": "python3 ControlCenter.py",
        "delay": 1,
        "port": 8083,
        "env_vars": {
            "CATALOG_URL": "http://localhost:8080",
            "PORT": "8083",
            "HOST": "0.0.0.0"
        }
    },
    {
        "name": "Account Manager",
        "directory": "MS_AccountManager",
        "command": "python3 account_manager.py",
        "delay": 1,
        "port": 8086,
        "env_vars": {
            "CATALOG_URL": "http://localhost:8080",
            "PORT": "8086",
            "JWT_SECRET": "smart_iot_bolt_secret_key"
        }
    },
    {
        "name": "Raspberry Pi Connector",
        "directory": "MS_RaspberryPiConnector",
        "command": "python3 RaspberryPiConnector.py",
        "delay": 1,
        "port": 8090,
        "env_vars": {
            "CATALOG_URL": "http://localhost:8080",
            "PORT": "8090"
        }
    },
    {
        "name": "Telegram Bot",
        "directory": "MS_TelegramBot",
        "command": "python3 telegram_bot.py",
        "delay": 1,
        "port": 8085,
        "env_vars": {
            "RESOURCE_CATALOG_URL": "http://localhost:8080",
            "SERVICE_PORT": "8085",
            "SERVICE_HOST": "localhost",
            "PTB_HTTPX_DISABLE_PROXIES": "True"
        }
    },
    {
        "name": "Analytics Service",
        "directory": "MS_Analytics",
        "command": "python3 ms_analytics.py",
        "delay": 1,
        "port": 8082,
        "env_vars": {
            "CATALOG_URL": "http://localhost:8080",
            "PORT": "8082",
            "HOST": "0.0.0.0"
        }
    }
]

# Function to check and setup InfluxDB
def setup_influxdb():
    print("\n📊 Checking InfluxDB setup...")
    
    try:
        # Check if influxd is installed
        result = subprocess.run(['which', 'influxd'], capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ InfluxDB is not installed. Please install it from https://portal.influxdata.com/downloads/")
            print("   You can also use Homebrew: brew install influxdb")
            return False
        
        # Check if InfluxDB is already running
        result = subprocess.run(['pgrep', 'influxd'], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ InfluxDB is already running")
            return True
        
        # Try to start InfluxDB
        print("🚀 Starting InfluxDB...")
        
        # Open a new terminal for running InfluxDB
        applescript = f'''
        tell application "Terminal"
            do script "echo '=== Starting InfluxDB ===' && influxd"
            set custom title of front window to "InfluxDB"
        end tell
        '''
        
        # Execute the AppleScript command
        result = subprocess.run(['osascript', '-e', applescript], capture_output=True, text=True)
        if result.stderr:
            print(f"⚠️ Warning when starting InfluxDB: {result.stderr}")
            return False
        
        print("✅ InfluxDB started in a new terminal window")
        print("⚠️ Important: For first-time setup, please visit http://localhost:8086 to create:")
        print("   1. An initial user")
        print("   2. An organization (recommended name: 'smart_iot')")
        print("   3. A bucket for sensor data (recommended name: 'sensor_data')")
        print("   4. Generate an API token and set it as INFLUXDB_TOKEN environment variable")
        
        # Wait for InfluxDB to start
        print("⏳ Waiting for InfluxDB to start...")
        time.sleep(5)
        return True
    
    except Exception as e:
        print(f"❌ Error setting up InfluxDB: {e}")
        return False

def main():
    print("\n🚀 Smart IoT Platform Service Launcher 🚀")
    print("=========================================")
    
    # Check and install required packages
    check_and_install_packages()
    
    # Setup InfluxDB
    setup_influxdb()
    
    # Check for ports in use and adjust if needed
    for service in services:
        port = service.get("port")
        if port:
            if is_port_in_use(port):
                try:
                    new_port = find_available_port(port)
                    print(f"⚠️  Port {port} for {service['name']} is in use. Using port {new_port} instead.")
                    service["env_vars"][service.get("port_env_name", "PORT")] = str(new_port)
                    service["port"] = new_port
                except RuntimeError as e:
                    print(f"❌ Error: {e}")
                    print(f"Cannot start {service['name']}. Please free up some ports and try again.")
                    sys.exit(1)
    
    print("\n🔄 Starting all microservices...")
    
    try:
        for service in services:
            print(f"🚀 Starting {service['name']}...")
            
            # Add current environment variables to the service environment
            env_vars = os.environ.copy()
            if service.get("env_vars"):
                env_vars.update(service["env_vars"])
            
            # Launch the service
            result = open_terminal_with_command(
                service['directory'],
                service['command'],
                service['name'],
                service.get("env_vars")
            )
            
            terminal_processes.append(result)
            
            # Wait for the service to initialize
            print(f"⏳ Waiting {service['delay']} seconds for {service['name']} to initialize...")
            time.sleep(service['delay'])
        
        print("\n✅ All services started successfully in separate terminals.")
        print("\n📊 Service summary:")
        
        for service in services:
            port_info = f" on port {service['port']}" if "port" in service else ""
            print(f"  • {service['name']}{port_info}")
        
        print("\n🖥️  WebDashboard: The dashboard is static HTML and can be accessed by opening:")
        print(f"   file://{os.path.join(project_dir, 'MS_WebDashboard/index.html')}")
        print(f"   file://{os.path.join(project_dir, 'MS_WebDashboard/dashboard.html')}")
        
        print("\n⚠️  Note: Some services might encounter errors if other required services aren't")
        print("   running properly. Check the terminal windows for specific error messages.")
        
        print("\n💡 Press Ctrl+C to stop all services...")
        
        # Keep running until interrupted
        while True:
            time.sleep(1)
    
    except KeyboardInterrupt:
        print("\n\n🛑 Stopping services...")
        sys.exit(0)

if __name__ == "__main__":
    main() 