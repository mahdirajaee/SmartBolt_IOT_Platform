import os
import json
import time
import requests
import threading
import sys
import socket

# Apply CGI patch for Python 3.13 compatibility
if sys.version_info >= (3, 13):
    import cgi_patch

import cherrypy
import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class AnalyticsMicroservice:
    def __init__(self):
        self.catalog_url = os.getenv("CATALOG_URL")
        self.service_id = "analytics_service"
        self.service_name = "Analytics Microservice"
        self.host = os.getenv("HOST")
        
        self.port = self.find_available_port(int(os.getenv("PORT")))
        self.base_url = f"http://{self.host}:{self.port}"
        
        self.ts_db_connector_url = None
        self.web_dashboard_url = None
        self.telegram_bot_url = None
        self.control_center_url = None
        
        self.threshold_temp_high = float(os.getenv("THRESHOLD_TEMP_HIGH"))
        self.threshold_temp_low = float(os.getenv("THRESHOLD_TEMP_LOW"))
        self.threshold_pressure_high = float(os.getenv("THRESHOLD_PRESSURE_HIGH"))
        self.threshold_pressure_low = float(os.getenv("THRESHOLD_PRESSURE_LOW"))
        
        self.prediction_window = int(os.getenv("PREDICTION_WINDOW"))  # number of data points ahead
        self.anomaly_check_interval = int(os.getenv("ANOMALY_CHECK_INTERVAL")) #second
        
        threading.Thread(target=self.register_with_catalog, daemon=True).start()
        threading.Thread(target=self.periodic_anomaly_check, daemon=True).start()

    def find_available_port(self, port):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind((self.host, port))
            sock.close()
            return port
        except socket.error:
            print(f"Port {port} is busy, trying another port...")
            for alternative_port in range(port + 1, port + 100):
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.bind((self.host, alternative_port))
                    sock.close()
                    print(f"Using alternative port: {alternative_port}")
                    return alternative_port
                except socket.error:
                    continue
            raise Exception("No available ports found")

    def register_with_catalog(self):
        while True:
            try:
                service_info = {
                    "name": self.service_id,
                    "endpoint": self.base_url,
                    "port": self.port,
                    "additional_info": {
                        "service_name": self.service_name,
                        "endpoints": {
                            "predictions": f"{self.base_url}/predictions",
                            "anomalies": f"{self.base_url}/anomalies",
                            "cascade_analysis": f"{self.base_url}/cascade_analysis"
                        }
                    }
                }
                
                response = requests.post(f"{self.catalog_url}/service", json=service_info)
                
                if response.status_code == 200 or response.status_code == 201:
                    self.discover_services()
                    time.sleep(60)  # Re-register every minute
                else:
                    time.sleep(5)  # Retry after 5 seconds
            except Exception as e:
                print(f"Error registering with catalog: {e}")
                time.sleep(5)  # Retry after 5 seconds

    def discover_services(self):
        try:
            response = requests.get(f"{self.catalog_url}/service")
            if response.status_code == 200:
                services_data = response.json().get("services", {})
                
                for service_id, service_info in services_data.items():
                    if service_id == "time_series_db_connector":
                        self.ts_db_connector_url = f"http://{service_info['endpoint'].split('://')[1]}"
                    elif service_id == "telegram_bot":
                        self.telegram_bot_url = f"http://{service_info['endpoint'].split('://')[1]}"
                    elif service_id == "control_center":
                        self.control_center_url = f"http://{service_info['endpoint'].split('://')[1]}"
                
                print(f"Discovered services: TimeSeriesDB={self.ts_db_connector_url}, TelegramBot={self.telegram_bot_url}, ControlCenter={self.control_center_url}")
        except Exception as e:
            print(f"Error discovering services: {e}")

    def get_sensor_data(self, sector_id, device_id, data_type, start_time, end_time):
        if not self.ts_db_connector_url:
            self.discover_services()
            if not self.ts_db_connector_url:
                return None
        
        try:
            params = {
                "sector_id": sector_id,
                "device_id": device_id,
                "data_type": data_type,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            }
            
            response = requests.get(f"{self.ts_db_connector_url}/data", params=params)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error getting sensor data: {response.status_code}, {response.text}")
                return None
        except Exception as e:
            print(f"Error in get_sensor_data: {e}")
            return None

    def get_devices_for_sector(self, sector_id):
        try:
            response = requests.get(f"{self.catalog_url}/sectors/{sector_id}/devices")
            
            if response.status_code == 200:
                devices = response.json()
                # Sort devices by their numeric ID to get sequential order
                devices.sort(key=lambda device: int(device["device_id"].replace("dev", "")))
                return devices
            else:
                print(f"Error getting devices: {response.status_code}, {response.text}")
                return []
        except Exception as e:
            print(f"Error in get_devices_for_sector: {e}")
            return []

    def get_all_sectors(self):
        try:
            response = requests.get(f"{self.catalog_url}/sectors")
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error getting sectors: {response.status_code}, {response.text}")
                return []
        except Exception as e:
            print(f"Error in get_all_sectors: {e}")
            return []

    def create_arima_prediction(self, data, prediction_window=12):
        if not data or len(data) < 10:  # Need sufficient historical data
            return []
        
        try:
            # Convert to pandas Series
            timestamps = [item['timestamp'] for item in data]
            values = [item['value'] for item in data]
            series = pd.Series(values, index=pd.DatetimeIndex(timestamps))
            
            # Fit ARIMA model
            model = ARIMA(series, order=(5,1,0))  # Parameters can be tuned
            model_fit = model.fit()
            
            # Predict future values
            forecast = model_fit.forecast(steps=prediction_window)
            
            # Create prediction data points with timestamps
            start_time = pd.DatetimeIndex(timestamps)[-1]
            predictions = []
            
            for i, value in enumerate(forecast):
                future_time = start_time + timedelta(minutes=(i+1)*10)  # Assuming 10-minute intervals
                predictions.append({
                    'timestamp': future_time.isoformat(),
                    'value': value,
                    'is_prediction': True
                })
            
            return predictions
        except Exception as e:
            print(f"Error in create_arima_prediction: {e}")
            return []

    def detect_anomalies(self, data, predictions, threshold_high, threshold_low):
        anomalies = []
        
        # Check historical data for anomalies
        for item in data:
            if item['value'] > threshold_high or item['value'] < threshold_low:
                anomalies.append({
                    'timestamp': item['timestamp'],
                    'value': item['value'],
                    'threshold_violated': 'high' if item['value'] > threshold_high else 'low'
                })
        
        # Check predictions for anomalies
        for item in predictions:
            if item['value'] > threshold_high or item['value'] < threshold_low:
                anomalies.append({
                    'timestamp': item['timestamp'],
                    'value': item['value'],
                    'threshold_violated': 'high' if item['value'] > threshold_high else 'low',
                    'is_prediction': True
                })
        
        return anomalies

    def analyze_cascade_problem(self, sector_id, data_type):
        # Get all devices in the sector
        devices = self.get_devices_for_sector(sector_id)
        if not devices:
            return {"status": "error", "message": f"No devices found for sector {sector_id}"}
        
        # Sort devices by their numeric ID to get sequential order along the pipeline
        devices.sort(key=lambda device: int(device["device_id"].replace("dev", "")))
        
        # Check for anomalies across multiple devices in sequence
        anomalies = []
        cascade_detected = False
        propagation_direction = None
        propagation_speed = None
        
        # Get data for each device and check for anomalies
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=1)  # Look at the last hour of data
        
        device_data = {}
        device_anomalies = {}
        
        # First pass: collect data and detect individual anomalies
        for device in devices:
            device_id = device["device_id"]
            data = self.get_sensor_data(sector_id, device_id, data_type, start_time, end_time)
            
            if data:
                device_data[device_id] = data
                
                # Check for anomalies in this device's data
                threshold_high = self.threshold_temp_high if data_type == "temperature" else self.threshold_pressure_high
                threshold_low = self.threshold_temp_low if data_type == "temperature" else self.threshold_pressure_low
                
                # Get the most recent data points
                recent_data = sorted(data, key=lambda x: x["timestamp"])[-30:]  # Last 30 points
                
                # Calculate mean and standard deviation
                values = [point["value"] for point in recent_data]
                mean_value = sum(values) / len(values)
                std_dev = (sum((x - mean_value) ** 2 for x in values) / len(values)) ** 0.5
                
                # Detect anomalies (values beyond 2 standard deviations or beyond thresholds)
                anomaly_points = []
                for point in recent_data:
                    if (point["value"] > threshold_high or 
                        point["value"] < threshold_low or
                        point["value"] > mean_value + 2 * std_dev or
                        point["value"] < mean_value - 2 * std_dev):
                        anomaly_points.append(point)
                
                device_anomalies[device_id] = anomaly_points
                
                if anomaly_points:
                    anomalies.append({
                        "device_id": device_id,
                        "anomalies": anomaly_points,
                        "timestamp": anomaly_points[-1]["timestamp"] if anomaly_points else None
                    })
        
        # Second pass: analyze propagation patterns
        if len(anomalies) >= 2:
            # Sort anomalies by device ID to maintain pipeline order
            sorted_anomalies = sorted(anomalies, key=lambda a: int(a["device_id"].replace("dev", "")))
            
            # Check if anomalies appear in sequence along the pipeline
            earliest_anomaly_times = {}
            for anomaly in sorted_anomalies:
                if anomaly["anomalies"]:
                    earliest_time = min(point["timestamp"] for point in anomaly["anomalies"])
                    earliest_anomaly_times[anomaly["device_id"]] = datetime.fromisoformat(earliest_time.replace('Z', '+00:00'))
            
            # Sort devices by anomaly detection time
            devices_by_time = sorted(earliest_anomaly_times.items(), key=lambda x: x[1])
            
            # Convert to ordered lists of IDs and timestamps
            sequential_devices = [item[0] for item in devices_by_time]
            sequential_times = [item[1] for item in devices_by_time]
            
            # Check if anomalies appear in sequential order along the pipeline
            device_ids = [d["device_id"] for d in devices]
            device_positions = {device_id: i for i, device_id in enumerate(device_ids)}
            
            sequential_positions = [device_positions[device_id] for device_id in sequential_devices]
            
            # If positions increase or decrease monotonically, we have a cascade
            if all(sequential_positions[i] < sequential_positions[i+1] for i in range(len(sequential_positions)-1)):
                cascade_detected = True
                propagation_direction = "forward"
                
                # Calculate propagation speed if we have more than one device with anomalies
                if len(sequential_times) >= 2:
                    time_diffs = [(sequential_times[i+1] - sequential_times[i]).total_seconds() 
                                  for i in range(len(sequential_times)-1)]
                    propagation_speed = sum(time_diffs) / len(time_diffs)
                    
            elif all(sequential_positions[i] > sequential_positions[i+1] for i in range(len(sequential_positions)-1)):
                cascade_detected = True
                propagation_direction = "backward"
                
                # Calculate propagation speed if we have more than one device with anomalies
                if len(sequential_times) >= 2:
                    time_diffs = [(sequential_times[i+1] - sequential_times[i]).total_seconds() 
                                  for i in range(len(sequential_times)-1)]
                    propagation_speed = sum(time_diffs) / len(time_diffs)
        
        # Prepare response
        response = {
            "sector_id": sector_id,
            "data_type": data_type,
            "devices_analyzed": len(devices),
            "anomalies_detected": len(anomalies),
            "cascade_detected": cascade_detected,
            "device_anomalies": anomalies
        }
        
        if cascade_detected:
            response["propagation_direction"] = propagation_direction
            response["propagation_speed_seconds"] = propagation_speed
            
            # If cascade is detected, send alert with high severity
            alert_data = {
                "sector_id": sector_id,
                "alert_type": "cascade_problem",
                "severity": "high",
                "message": f"Cascade problem detected in sector {sector_id} for {data_type}. " +
                          f"Propagating {propagation_direction} at {round(propagation_speed, 2)} seconds between devices.",
                "devices_affected": [a["device_id"] for a in anomalies],
                "timestamp": datetime.now().isoformat()
            }
            self.send_alert(alert_data)
            
            # Send control recommendation to the Control Center
            # For a cascade problem, we want to close valves to isolate the affected sector
            first_affected_device = sequential_devices[0]
            recommendation = {
                "sector_id": sector_id,
                "device_id": first_affected_device,
                "action": "close_valve",
                "reason": f"Cascade problem detected, propagating {propagation_direction}",
                "severity": "high",
                "timestamp": datetime.now().isoformat()
            }
            self.send_control_recommendation(sector_id, first_affected_device, recommendation)
            
        return response

    def send_alert(self, alert_data):
        if not self.telegram_bot_url:
            self.discover_services()
            if not self.telegram_bot_url:
                print("Telegram Bot URL not available")
                return
        
        try:
            alert_message = {
                "alert_type": "cascade_problem",
                "root_cause_device": alert_data["root_cause_device"],
                "recommendation": alert_data["recommendation"],
                "timestamp": datetime.now().isoformat()
            }
            
            response = requests.post(f"{self.telegram_bot_url}/alerts", json=alert_message)
            
            if response.status_code != 200:
                print(f"Error sending alert: {response.status_code}, {response.text}")
        except Exception as e:
            print(f"Error in send_alert: {e}")

    def send_control_recommendation(self, sector_id, device_id, recommendation):
        if not self.control_center_url:
            self.discover_services()
            if not self.control_center_url:
                print("Control Center URL not available")
                return
        
        try:
            control_message = {
                "sector_id": sector_id,
                "device_id": device_id,
                "recommendation": recommendation,
                "timestamp": datetime.now().isoformat()
            }
            
            response = requests.post(f"{self.control_center_url}/recommendations", json=control_message)
            
            if response.status_code != 200:
                print(f"Error sending control recommendation: {response.status_code}, {response.text}")
        except Exception as e:
            print(f"Error in send_control_recommendation: {e}")

    def periodic_anomaly_check(self):
        while True:
            try:
                sectors = self.get_all_sectors()
                for sector in sectors:
                    sector_id = sector["sector_id"]
                    
                    # Check temperature anomalies
                    self.analyze_cascade_problem(sector_id, "temperature")
                    
                    # Check pressure anomalies
                    self.analyze_cascade_problem(sector_id, "pressure")
                
                time.sleep(self.anomaly_check_interval)
            except Exception as e:
                print(f"Error in periodic_anomaly_check: {e}")
                time.sleep(60)  # Retry after a minute if there's an error

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self):
        return {
            "service": self.service_name,
            "status": "running",
            "endpoints": {
                "predictions": "/predictions",
                "anomalies": "/anomalies",
                "cascade_analysis": "/cascade_analysis"
            }
        }

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def predictions(self):
        if cherrypy.request.method == 'POST':
            data = cherrypy.request.json
            
            sector_id = data.get('sector_id')
            device_id = data.get('device_id')
            data_type = data.get('data_type')  # 'temperature' or 'pressure'
            
            if not (sector_id and device_id and data_type):
                return {"error": "Missing required parameters"}
            
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=24)  # Last 24 hours of data
            
            # Get historical data
            historical_data = self.get_sensor_data(sector_id, device_id, data_type, start_time, end_time)
            
            if not historical_data:
                return {"error": "No historical data available"}
            
            # Generate predictions
            predictions = self.create_arima_prediction(historical_data, self.prediction_window)
            
            return {
                "sector_id": sector_id,
                "device_id": device_id,
                "data_type": data_type,
                "historical_data": historical_data,
                "predictions": predictions
            }
        else:
            return {"error": "Method not allowed"}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def anomalies(self):
        if cherrypy.request.method == 'POST':
            data = cherrypy.request.json
            
            sector_id = data.get('sector_id')
            device_id = data.get('device_id')
            data_type = data.get('data_type')  # 'temperature' or 'pressure'
            
            if not (sector_id and device_id and data_type):
                return {"error": "Missing required parameters"}
            
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=24)  # Last 24 hours of data
            
            # Get historical data
            historical_data = self.get_sensor_data(sector_id, device_id, data_type, start_time, end_time)
            
            if not historical_data:
                return {"error": "No historical data available"}
            
            # Generate predictions
            predictions = self.create_arima_prediction(historical_data, self.prediction_window)
            
            # Define thresholds based on data type
            if data_type == "temperature":
                threshold_high = self.threshold_temp_high
                threshold_low = self.threshold_temp_low
            else:  # pressure
                threshold_high = self.threshold_pressure_high
                threshold_low = self.threshold_pressure_low
            
            # Detect anomalies
            anomalies = self.detect_anomalies(historical_data, predictions, threshold_high, threshold_low)
            
            return {
                "sector_id": sector_id,
                "device_id": device_id,
                "data_type": data_type,
                "anomalies": anomalies
            }
        else:
            return {"error": "Method not allowed"}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def cascade_analysis(self):
        if cherrypy.request.method == 'POST':
            data = cherrypy.request.json
            
            sector_id = data.get('sector_id')
            data_type = data.get('data_type')  # 'temperature' or 'pressure'
            
            if not (sector_id and data_type):
                return {"error": "Missing required parameters"}
            
            return self.analyze_cascade_problem(sector_id, data_type)
        else:
            return {"error": "Method not allowed"}

def main():
    try:
        # Create the analytics service
        analytics_service = AnalyticsMicroservice()
        
        # Configure CherryPy
        cherrypy.config.update({
            'server.socket_host': analytics_service.host,
            'server.socket_port': analytics_service.port,
            'engine.autoreload.on': False
        })
        
        # Mount the service at the root
        cherrypy.tree.mount(analytics_service, '/', {
            '/': {
                'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
                'tools.sessions.on': True,
                'tools.response_headers.on': True,
                'tools.response_headers.headers': [('Content-Type', 'application/json')],
            }
        })
        
        # Start the server
        print(f"Starting Analytics Microservice on {analytics_service.host}:{analytics_service.port}")
        cherrypy.engine.start()
        cherrypy.engine.block()
    except Exception as e:
        print(f"Failed to start Analytics Microservice: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()