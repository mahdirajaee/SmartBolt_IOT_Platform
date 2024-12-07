from simulation.sensor_simulator import SensorSimulator
from config import *

if __name__ == "__main__":
    try:
        # Initialize the sensor simulator
        simulator = SensorSimulator(DEVICE_ID, BROKER_ADDRESS, BROKER_PORT)
        simulator.start()

        # Start simulating sensor readings
        simulator.simulate_sensors()
    except KeyboardInterrupt:
        # Gracefully stop the simulator
        simulator.stop()
