import random
import numpy as np

def get_temperature(pipeline_id=None, device_id=None):
    """
    Simulates a temperature sensor using Gaussian distribution for realistic values.
    Normal operating range: 50-80°C
    Critical threshold: >85°C
    
    Args:
        pipeline_id: The pipeline identifier
        device_id: The device identifier
    
    Returns:
        float: Temperature reading in Celsius
    """
    # Base temperature range for normal operation
    base_temp = 65.0
    # Use Gaussian distribution for more realistic values
    temp = np.random.normal(base_temp, 5.0)
    
    # Occasionally simulate temperature spikes (1% chance)
    if random.random() < 0.01:
        temp += random.uniform(15, 25)
    
    return round(temp, 2)