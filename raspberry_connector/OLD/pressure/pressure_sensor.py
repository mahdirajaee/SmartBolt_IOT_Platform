import random
import numpy as np

def get_pressure(pipeline_id=None, device_id=None):
    """
    Simulates a pressure sensor using Gaussian distribution for realistic values.
    Normal operating range: 5-10 bar
    Critical threshold: >12 bar
    
    Args:
        pipeline_id: The pipeline identifier
        device_id: The device identifier
    
    Returns:
        float: Pressure reading in bar
    """
    # Base pressure range for normal operation
    base_pressure = 7.5
    # Use Gaussian distribution for more realistic values
    pressure = np.random.normal(base_pressure, 1.0)
    
    # Occasionally simulate pressure spikes (1% chance)
    if random.random() < 0.01:
        pressure += random.uniform(3, 5)
    
    return round(pressure, 2)