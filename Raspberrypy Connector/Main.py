from Simulation.sensor_simulator import SensorSimulator
from Config import *

if __name__ == "__main__":
    try:
        # Initialize the sensor simulator
        simulator = SensorSimulator(DEVICE_ID, BROKER_ADDRESS, BROKER_PORT)
        simulator.start()
        
        TOPIC = "sensor/data"  # Define your MQTT topic


        # Start simulating sensor readings
        simulator.simulate_sensors()
    except KeyboardInterrupt:
        # Gracefully stop the simulator
        simulator.stop()
