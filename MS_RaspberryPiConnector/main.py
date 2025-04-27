#!/usr/bin/env python3

import argparse
import logging
import signal
import threading
import time
from api import start_api
from sensor_simulator import SensorSimulator
from registration import start_registration, update_status
import config
from valve_control import get_valve_message_handler

logging.basicConfig(
    filename=config.LOG_FILE,
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('main')

def start_simulator(device_id=None, background=False):
    simulator = SensorSimulator()
    
    if background:
        simulator_thread = threading.Thread(
            target=simulator.run,
            args=(device_id,),
            daemon=True
        )
        simulator_thread.start()
        logger.info(f"Sensor simulator started in background for device_id={device_id}")
        return simulator_thread
    else:
        logger.info(f"Starting sensor simulator for device_id={device_id}")
        simulator.run(device_id)
        return None

def start_valve_message_handler(background=True):
    if not config.VALVE_CONTROL_ENABLED:
        logger.info("Valve control via message broker is disabled in config")
        return None
        
    valve_handler = get_valve_message_handler()
    
    if background:
        success = valve_handler.start()
        if success:
            logger.info("Valve message handler started in background")
            print("Valve message handler started - ready to receive valve control commands")
        else:
            logger.error("Failed to start valve message handler")
            print("Warning: Failed to start valve message handler")
        return valve_handler
    else:
        logger.info("Starting valve message handler in foreground")
        try:
            valve_handler.start()
            print("Valve message handler started - ready to receive valve control commands")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            valve_handler.stop()
            logger.info("Valve message handler stopped")
        return None

def run_full_service(device_id=None):
    logger.info("Starting full service (API + simulator + valve handler)")
    print("Starting full service (API + simulator + valve handler)...")
    
    print("Registering with Resource Catalog...")
    registration_success = start_registration(background=True)
    if registration_success:
        print("Successfully registered with Resource Catalog")
    else:
        print("Warning: Failed to register with Resource Catalog, will retry in background")
    
    valve_handler = start_valve_message_handler(background=True)
    
    simulator_thread = start_simulator(device_id, background=True)
    
    print("Starting API server on port 5000...")
    try:
        start_api()
    except KeyboardInterrupt:
        logger.info("Received shutdown signal, stopping services...")
        print("\nShutting down services...")
        if valve_handler:
            valve_handler.stop()
        update_status("offline")

def main():
    parser = argparse.ArgumentParser(description='Smart Bolt Raspberry Pi Connector')
    parser.add_argument('--device', type=int, help='Specific device ID to simulate')
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    api_parser = subparsers.add_parser('api', help='Start the API server')
    
    simulator_parser = subparsers.add_parser('simulator', help='Start the sensor simulator')
    simulator_parser.add_argument('--device', type=int, help='Specific device ID to simulate')
    
    full_parser = subparsers.add_parser('full', help='Start both API server and sensor simulator')
    full_parser.add_argument('--device', type=int, help='Specific device ID to simulate')
    
    valve_parser = subparsers.add_parser('valve-handler', help='Start the valve message handler')
    
    args = parser.parse_args()
    
    device_id = None
    if hasattr(args, 'device') and args.device:
        device_id = args.device
    
    if args.command == 'api':
        logger.info("Starting API server")
        print("Starting API server on port 5000...")
        print("Registering with Resource Catalog...")
        registration_success = start_registration(background=True)
        if registration_success:
            print("Successfully registered with Resource Catalog")
        else:
            print("Warning: Failed to register with Resource Catalog, will retry in background")
        start_api()
        
    elif args.command == 'simulator':
        logger.info(f"Starting simulator for device_id={device_id}")
        print(f"Starting sensor simulator{f' for device {device_id}' if device_id else ''}...")
        start_simulator(device_id)
        
    elif args.command == 'valve-handler':
        logger.info("Starting valve message handler")
        print("Starting valve message handler for broker messages...")
        start_valve_message_handler(background=False)
        
    elif args.command == 'full':
        run_full_service(device_id)
        
    else:
        run_full_service(device_id)

if __name__ == "__main__":
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal, stopping services...")
        print("\nShutting down services...")
        valve_handler = get_valve_message_handler()
        if valve_handler and valve_handler.running:
            valve_handler.stop()
        update_status("offline")
        exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    main()