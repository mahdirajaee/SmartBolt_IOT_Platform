#!/usr/bin/env python3

"""
Data Visualization Tool for Smart Bolt Time Series Data

This script helps visualize the sensor data and valve states stored in InfluxDB.
It creates simple plots of temperature, pressure, and valve state changes.
"""

import sys
import argparse
import datetime
from datetime import timedelta
import json
import config
import matplotlib.pyplot as plt
from matplotlib.dates import DateFormatter
import numpy as np

try:
    from influxdb import InfluxDBClient
except ImportError:
    print("InfluxDB Python client not installed. Please run: pip install influxdb")
    sys.exit(1)

try:
    import matplotlib.pyplot as plt
except ImportError:
    print("Matplotlib not installed. Please run: pip install matplotlib")
    sys.exit(1)

def connect_to_influxdb():
    """Connect to the InfluxDB server"""
    try:
        client = InfluxDBClient(
            host=config.INFLUXDB_HOST, 
            port=config.INFLUXDB_PORT,
            username=config.INFLUXDB_USER,
            password=config.INFLUXDB_PASSWORD,
            database=config.INFLUXDB_DATABASE
        )
        
        # Test connection
        if client.ping():
            print(f"Connected to InfluxDB at {config.INFLUXDB_HOST}:{config.INFLUXDB_PORT}")
            return client
        else:
            print("Failed to ping InfluxDB server")
            return None
    except Exception as e:
        print(f"Error connecting to InfluxDB: {e}")
        return None

def get_sensor_data(client, sensor_type, device_id=None, hours=24):
    """Retrieve sensor data from InfluxDB"""
    if not client:
        return None
        
    try:
        # Calculate time range
        end_time = datetime.datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        # Build the query
        if device_id:
            query = f"""
                SELECT * FROM "{sensor_type}" 
                WHERE time >= '{start_time.isoformat()}Z' AND time <= '{end_time.isoformat()}Z'
                AND "device_id" = '{device_id}'
            """
        else:
            query = f"""
                SELECT * FROM "{sensor_type}" 
                WHERE time >= '{start_time.isoformat()}Z' AND time <= '{end_time.isoformat()}Z'
            """
            
        result = client.query(query)
        
        if not result:
            print(f"No {sensor_type} data found for the specified time range")
            return []
            
        # Convert to list of dictionaries
        points = list(result.get_points())
        return points
    except Exception as e:
        print(f"Error retrieving {sensor_type} data: {e}")
        return []

def get_valve_states(client, sector_id=None, hours=24):
    """Retrieve valve state changes from InfluxDB"""
    if not client:
        return None
        
    try:
        # Calculate time range
        end_time = datetime.datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        # Build the query
        if sector_id:
            query = f"""
                SELECT * FROM "valve_state" 
                WHERE time >= '{start_time.isoformat()}Z' AND time <= '{end_time.isoformat()}Z'
                AND "sector_id" = '{sector_id}'
            """
        else:
            query = f"""
                SELECT * FROM "valve_state" 
                WHERE time >= '{start_time.isoformat()}Z' AND time <= '{end_time.isoformat()}Z'
            """
            
        result = client.query(query)
        
        if not result:
            print("No valve state data found for the specified time range")
            return []
            
        # Convert to list of dictionaries
        points = list(result.get_points())
        return points
    except Exception as e:
        print(f"Error retrieving valve state data: {e}")
        return []

def plot_temperature_data(data, device_id=None, save_path=None):
    """Plot temperature data"""
    if not data:
        print("No temperature data to plot")
        return
        
    times = [datetime.datetime.strptime(point['time'], '%Y-%m-%dT%H:%M:%S.%fZ') 
             for point in data]
    values = [point['value'] for point in data]
    
    plt.figure(figsize=(12, 6))
    plt.plot(times, values, 'r-', marker='o', markersize=4)
    plt.title(f'Temperature Readings {f"for Device {device_id}" if device_id else ""}')
    plt.xlabel('Time')
    plt.ylabel('Temperature (°C)')
    plt.grid(True)
    
    # Format the time axis
    date_format = DateFormatter('%H:%M')
    plt.gca().xaxis.set_major_formatter(date_format)
    plt.gcf().autofmt_xdate()
    
    # Add some statistics
    avg_temp = sum(values) / len(values) if values else 0
    plt.axhline(y=avg_temp, color='b', linestyle='--', label=f'Avg: {avg_temp:.1f}°C')
    plt.legend()
    
    if save_path:
        plt.savefig(save_path)
        print(f"Temperature plot saved to {save_path}")
    else:
        plt.tight_layout()
        plt.show()

def plot_pressure_data(data, device_id=None, save_path=None):
    """Plot pressure data"""
    if not data:
        print("No pressure data to plot")
        return
        
    times = [datetime.datetime.strptime(point['time'], '%Y-%m-%dT%H:%M:%S.%fZ')
             for point in data]
    values = [point['value'] for point in data]
    
    plt.figure(figsize=(12, 6))
    plt.plot(times, values, 'b-', marker='o', markersize=4)
    plt.title(f'Pressure Readings {f"for Device {device_id}" if device_id else ""}')
    plt.xlabel('Time')
    plt.ylabel('Pressure (hPa)')
    plt.grid(True)
    
    # Format the time axis
    date_format = DateFormatter('%H:%M')
    plt.gca().xaxis.set_major_formatter(date_format)
    plt.gcf().autofmt_xdate()
    
    # Add some statistics
    avg_pressure = sum(values) / len(values) if values else 0
    plt.axhline(y=avg_pressure, color='g', linestyle='--', label=f'Avg: {avg_pressure:.1f} hPa')
    plt.legend()
    
    if save_path:
        plt.savefig(save_path)
        print(f"Pressure plot saved to {save_path}")
    else:
        plt.tight_layout()
        plt.show()

def plot_valve_states(data, sector_id=None, save_path=None):
    """Plot valve state changes"""
    if not data:
        print("No valve state data to plot")
        return
        
    times = [datetime.datetime.strptime(point['time'], '%Y-%m-%dT%H:%M:%S.%fZ') 
             for point in data]
    states = [point['state'] for point in data]
    
    # Map valve states to numeric values for plotting
    state_map = {'closed': 0, 'open': 1}
    # For partially open states, extract percentage
    numeric_states = []
    for state in states:
        if state == 'closed':
            numeric_states.append(0)
        elif state == 'open':
            numeric_states.append(1)
        elif 'partially_open' in state:
            try:
                # Extract percentage
                pct = float(state.split('_')[-1].replace('%', '')) / 100
                numeric_states.append(pct)
            except (ValueError, IndexError):
                numeric_states.append(0.5)  # Default to 50% if parsing fails
        else:
            numeric_states.append(0.5)  # Default for unknown states
    
    plt.figure(figsize=(12, 6))
    plt.step(times, numeric_states, 'g-', where='post')
    plt.fill_between(times, numeric_states, step="post", alpha=0.2)
    plt.title(f'Valve State Changes {f"for Sector {sector_id}" if sector_id else ""}')
    plt.xlabel('Time')
    plt.ylabel('Valve State')
    plt.yticks([0, 0.25, 0.5, 0.75, 1], ['Closed', '25%', '50%', '75%', 'Open'])
    plt.ylim(-0.1, 1.1)  # Add some padding
    plt.grid(True)
    
    # Format the time axis
    date_format = DateFormatter('%H:%M')
    plt.gca().xaxis.set_major_formatter(date_format)
    plt.gcf().autofmt_xdate()
    
    if save_path:
        plt.savefig(save_path)
        print(f"Valve state plot saved to {save_path}")
    else:
        plt.tight_layout()
        plt.show()

def main():
    parser = argparse.ArgumentParser(description='Visualize Smart Bolt time series data')
    parser.add_argument('--type', choices=['temperature', 'pressure', 'valve', 'all'], 
                      help='Type of data to visualize', default='all')
    parser.add_argument('--device', help='Filter by device ID')
    parser.add_argument('--sector', help='Filter by sector ID (for valve states)')
    parser.add_argument('--hours', type=int, default=24, help='Time range in hours')
    parser.add_argument('--save', help='Save plots to files instead of displaying them')
    
    args = parser.parse_args()
    
    print("\n====== Smart Bolt - Data Visualization ======\n")
    
    # Connect to InfluxDB
    client = connect_to_influxdb()
    if not client:
        print("Could not connect to InfluxDB. Please check your configuration and make sure InfluxDB is running.")
        sys.exit(1)
    
    # Visualize the data based on the type argument
    if args.type in ('temperature', 'all'):
        print(f"Fetching temperature data for the past {args.hours} hours...")
        temp_data = get_sensor_data(client, 'temperature', args.device, args.hours)
        if temp_data:
            print(f"Found {len(temp_data)} temperature readings")
            save_path = f"temperature_{args.device}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png" if args.save else None
            plot_temperature_data(temp_data, args.device, save_path)
        else:
            print("No temperature data found")
    
    if args.type in ('pressure', 'all'):
        print(f"Fetching pressure data for the past {args.hours} hours...")
        pressure_data = get_sensor_data(client, 'pressure', args.device, args.hours)
        if pressure_data:
            print(f"Found {len(pressure_data)} pressure readings")
            save_path = f"pressure_{args.device}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png" if args.save else None
            plot_pressure_data(pressure_data, args.device, save_path)
        else:
            print("No pressure data found")
    
    if args.type in ('valve', 'all'):
        print(f"Fetching valve state data for the past {args.hours} hours...")
        valve_data = get_valve_states(client, args.sector, args.hours)
        if valve_data:
            print(f"Found {len(valve_data)} valve state changes")
            save_path = f"valve_state_{args.sector}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png" if args.save else None
            plot_valve_states(valve_data, args.sector, save_path)
        else:
            print("No valve state data found")
    
    print("\n====== Visualization Complete ======\n")

if __name__ == "__main__":
    main()