import os
import json
import time
import requests
import threading
import cherrypy
import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

class AnalyticsMicroservice:
    def __init__(self):
        self.catalog_url = os.getenv("CATALOG_URL", "http://localhost:8080")
        self.service_id = "analytics_service"
        self.service_name = "Analytics Microservice"
        self.host = os.getenv("HOST", "0.0.0.0")
        self.port = int(os.getenv("PORT", 8082))
        self.base_url = f"http://{self.host}:{self.port}"
        
        self.ts_db_connector_url = None
        self.web_dashboard_url = None
        self.telegram_bot_url = None
        self.control_center_url = None
        
        self.threshold_temp_high = float(os.getenv("THRESHOLD_TEMP_HIGH", "80.0"))
        self.threshold_temp_low = float(os.getenv("THRESHOLD_TEMP_LOW", "10.0"))
        self.threshold_pressure_high = float(os.getenv("THRESHOLD_PRESSURE_HIGH", "10.0"))
        self.threshold_pressure_low = float(os.getenv("THRESHOLD_PRESSURE_LOW", "1.0"))
        
        self.prediction_window = int(os.getenv("PREDICTION_WINDOW", "12"))  # 12 data points ahead
        self.anomaly_check_interval = int(os.getenv("ANOMALY_CHECK_INTERVAL", "300"))  # seconds
        
        threading.Thread(target=self.register_with_catalog, daemon=True).start()
        threading.Thread(target=self.periodic_anomaly_check, daemon=True).start()

    def register_with_catalog(self):
        while True:
            try:
                service_info = {
                    "service_id": self.service_id,
                    "service_name": self.service_name,
                    "endpoints": {
                        "base_url": self.base_url,
                        "predictions": f"{self.base_url}/predictions",
                        "anomalies": f"{self.base_url}/anomalies",
                        "cascade_analysis": f"{self.base_url}/cascade_analysis"
                    }
                }
                
                response = requests.post(f"{self.catalog_url}/services", json=service_info)
                
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
            response = requests.get(f"{self.catalog_url}/services")
            if response.status_code == 200:
                services = response.json()
                
                for service in services:
                    if "service_name" in service:
                        if service["service_name"] == "Time Series DB Connector":
                            self.ts_db_connector_url = service["endpoints"]["base_url"]
                        elif service["service_name"] == "Web Dashboard":
                            self.web_dashboard_url = service["endpoints"]["base_url"]
                        elif service["service_name"] == "Telegram Bot":
                            self.telegram_bot_url = service["endpoints"]["base_url"]
                        elif service["service_name"] == "Control Center":
                            self.control_center_url = service["endpoints"]["base_url"]
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
            return {"error": "No devices found for sector"}
        
        # Time range for analysis (last hour)
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=1)
        
        device_data = {}
        anomalies_by_device = {}
        
        # Get data for each device
        for device in devices:
            device_id = device["device_id"]
            data = self.get_sensor_data(sector_id, device_id, data_type, start_time, end_time)
            
            if data:
                device_data[device_id] = data
                
                # Determine threshold based on data type
                if data_type == "temperature":
                    threshold_high = self.threshold_temp_high
                    threshold_low = self.threshold_temp_low
                else:  # pressure
                    threshold_high = self.threshold_pressure_high
                    threshold_low = self.threshold_pressure_low
                
                # Check for anomalies
                anomalies = []
                for item in data:
                    if item['value'] > threshold_high or item['value'] < threshold_low:
                        anomalies.append({
                            'timestamp': item['timestamp'],
                            'value': item['value'],
                            'threshold_violated': 'high' if item['value'] > threshold_high else 'low'
                        })
                
                if anomalies:
                    anomalies_by_device[device_id] = anomalies
        
        # If no anomalies detected, return empty result
        if not anomalies_by_device:
            return {"result": "No anomalies detected", "devices": [device["device_id"] for device in devices]}
        
        # Find the first device with anomaly (root cause)
        first_anomaly_device = None
        earliest_anomaly_time = None
        
        for device_id, anomalies in anomalies_by_device.items():
            for anomaly in anomalies:
                anomaly_time = datetime.fromisoformat(anomaly['timestamp'])
                if earliest_anomaly_time is None or anomaly_time < earliest_anomaly_time:
                    earliest_anomaly_time = anomaly_time
                    first_anomaly_device = device_id
        
        # Check if subsequent devices also have anomalies (cascade effect)
        cascade_effects = []
        
        if first_anomaly_device:
            first_device_index = next(i for i, device in enumerate(devices) if device["device_id"] == first_anomaly_device)
            
            # Check devices after the first anomaly device
            for i in range(first_device_index + 1, len(devices)):
                subsequent_device_id = devices[i]["device_id"]
                if subsequent_device_id in anomalies_by_device:
                    cascade_effects.append({
                        "device_id": subsequent_device_id,
                        "anomalies": anomalies_by_device[subsequent_device_id]
                    })
        
        result = {
            "root_cause_device": first_anomaly_device,
            "root_cause_anomalies": anomalies_by_device.get(first_anomaly_device, []),
            "cascade_effects": cascade_effects,
            "recommendation": f"Close valve before {first_anomaly_device} to prevent cascade effects"
        }
        
        # Send alert to Telegram Bot if a root cause is identified
        if first_anomaly_device and self.telegram_bot_url:
            self.send_alert(result)
        
        # Send control recommendation to Control Center
        if first_anomaly_device and self.control_center_url:
            self.send_control_recommendation(sector_id, first_anomaly_device, result["recommendation"])
        
        return result

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
    analytics_service = AnalyticsMicroservice()
    
    cherrypy.config.update({
        'server.socket_host': analytics_service.host,
        'server.socket_port': analytics_service.port,
    })
    
    cherrypy.quickstart(analytics_service)

if __name__ == "__main__":
    main()