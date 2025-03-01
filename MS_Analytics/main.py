import os
import json
import time
import logging
import datetime
import requests
import numpy as np
import pandas as pd
from flask import Flask, request, jsonify
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.arima.model import ARIMA
import threading

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("analytics_service.log")
    ]
)
logger = logging.getLogger("AnalyticsService")

app = Flask(__name__)

# Configuration - Would typically be loaded from config file or environment variables
CONFIG = {
    "catalog_url": os.getenv("CATALOG_URL", "http://localhost:8080"),
    "timeseries_db_url": os.getenv("TIMESERIES_DB_URL", "http://localhost:8086"),
    "prediction_interval": int(os.getenv("PREDICTION_INTERVAL", "3600")),  # seconds
    "alert_thresholds": {
        "temperature": {
            "warning": float(os.getenv("TEMP_WARNING_THRESHOLD", "85.0")),  # Celsius
            "critical": float(os.getenv("TEMP_CRITICAL_THRESHOLD", "95.0"))  # Celsius
        },
        "pressure": {
            "warning": float(os.getenv("PRESSURE_WARNING_THRESHOLD", "8.5")),  # Bar
            "critical": float(os.getenv("PRESSURE_CRITICAL_THRESHOLD", "9.5"))  # Bar
        }
    },
    "prediction_window": int(os.getenv("PREDICTION_WINDOW", "24")),  # hours to predict ahead
    "model_update_interval": int(os.getenv("MODEL_UPDATE_INTERVAL", "86400")),  # 24 hours in seconds
    "analysis_interval": int(os.getenv("ANALYSIS_INTERVAL", "3600")),  # Run analysis every hour
    "service_id": "analytics_microservice"
}

# Global variables
models = {
    "temperature": None,
    "pressure": None
}
scalers = {
    "temperature": StandardScaler(),
    "pressure": StandardScaler()
}
last_model_update = {
    "temperature": 0,
    "pressure": 0
}

class AnalyticsService:
    def __init__(self, config):
        self.config = config
        self.token = None
        self.service_info = self._get_service_info()
        self.register_to_catalog()
        logger.info("Analytics Service initialized")
    
    def _get_service_info(self):
        """Get service information to register with the catalog"""
        hostname = os.getenv("HOSTNAME", "localhost")
        port = int(os.getenv("PORT", "5000"))
        
        return {
            "id": self.config["service_id"],
            "name": "Analytics Microservice",
            "endpoint": f"http://{hostname}:{port}",
            "version": "1.0",
            "description": "Predictive analytics service for IoT Smart Bolt platform",
            "apis": {
                "get_predictions": "/api/predictions",
                "get_alerts": "/api/alerts",
                "health": "/health"
            },
            "last_update": time.time()
        }
    
    def register_to_catalog(self):
        """Register this service to the Resource/Service Catalog"""
        try:
            response = requests.post(
                f"{self.config['catalog_url']}/services",
                json=self.service_info
            )
            if response.status_code in (200, 201):
                logger.info("Successfully registered with Resource Catalog")
            else:
                logger.error(f"Failed to register with Resource Catalog: {response.status_code} {response.text}")
        except Exception as e:
            logger.error(f"Error registering with Resource Catalog: {str(e)}")
    
    def update_registration(self):
        """Update registration with the catalog"""
        self.service_info["last_update"] = time.time()
        try:
            response = requests.put(
                f"{self.config['catalog_url']}/services/{self.config['service_id']}",
                json=self.service_info
            )
            if response.status_code == 200:
                logger.info("Successfully updated registration with Resource Catalog")
            else:
                logger.error(f"Failed to update registration: {response.status_code} {response.text}")
        except Exception as e:
            logger.error(f"Error updating registration: {str(e)}")
    
    def get_auth_token(self):
        """Get authentication token if needed for APIs"""
        # Implement token-based authentication if required
        pass
    
    def get_bolt_sectors(self):
        """Get all sectors with Smart IoT Bolts from the Catalog"""
        try:
            response = requests.get(f"{self.config['catalog_url']}/sectors")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get sectors: {response.status_code} {response.text}")
                return []
        except Exception as e:
            logger.error(f"Error getting sectors: {str(e)}")
            return []
    
    def get_bolts_in_sector(self, sector_id):
        """Get all Smart IoT Bolts in a specific sector"""
        try:
            response = requests.get(f"{self.config['catalog_url']}/sectors/{sector_id}/bolts")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get bolts in sector {sector_id}: {response.status_code} {response.text}")
                return []
        except Exception as e:
            logger.error(f"Error getting bolts in sector {sector_id}: {str(e)}")
            return []
    
    def get_historical_data(self, bolt_id, measurement_type, hours=168):  # Default to last 7 days
        """Get historical sensor data from Time Series DB Connector"""
        end_time = datetime.datetime.now()
        start_time = end_time - datetime.timedelta(hours=hours)
        
        # Format times for API
        start_str = start_time.isoformat() + "Z"
        end_str = end_time.isoformat() + "Z"
        
        try:
            response = requests.get(
                f"{self.config['timeseries_db_url']}/data",
                params={
                    "bolt_id": bolt_id,
                    "type": measurement_type,
                    "start": start_str,
                    "end": end_str
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Convert to DataFrame
                df = pd.DataFrame(data["measurements"])
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df.set_index("timestamp", inplace=True)
                df.sort_index(inplace=True)
                
                # Resample to hourly data to handle gaps and irregular intervals
                hourly_data = df["value"].resample("1H").mean().interpolate(method="time")
                
                return hourly_data
            else:
                logger.error(f"Failed to get historical data: {response.status_code} {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error getting historical data: {str(e)}")
            return None
    
    def train_random_forest_model(self, data, measurement_type):
        """Train a Random Forest model for time series forecasting"""
        if data is None or len(data) < 24:  # Need at least 24 hours of data
            logger.warning(f"Insufficient data to train model for {measurement_type}")
            return None
        
        # Feature engineering
        df = pd.DataFrame(data)
        df.columns = ["value"]
        
        # Add time-based features
        df["hour"] = df.index.hour
        df["day_of_week"] = df.index.dayofweek
        df["day_of_month"] = df.index.day
        df["month"] = df.index.month
        
        # Create lag features
        for i in range(1, 25):  # 24 hours of lag features
            df[f"lag_{i}"] = df["value"].shift(i)
        
        # Create target variable (next 24 hours)
        for i in range(1, self.config["prediction_window"] + 1):
            df[f"future_{i}"] = df["value"].shift(-i)
        
        # Drop rows with NaN (due to lag/future features)
        df.dropna(inplace=True)
        
        if len(df) == 0:
            logger.warning(f"No valid data after feature engineering for {measurement_type}")
            return None
        
        # Split features and targets
        X = df.drop([f"future_{i}" for i in range(1, self.config["prediction_window"] + 1)], axis=1)
        y = df[[f"future_{i}" for i in range(1, self.config["prediction_window"] + 1)]]
        
        # Scale features
        X_values = X.values
        scaler = scalers[measurement_type]
        scaler.fit(X_values)
        X_scaled = scaler.transform(X_values)
        
        # Train model
        model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        model.fit(X_scaled, y)
        
        # Update global model and timestamp
        models[measurement_type] = model
        last_model_update[measurement_type] = time.time()
        
        logger.info(f"Successfully trained model for {measurement_type}")
        return model
    
    def make_predictions(self, bolt_id, measurement_type, hours_ahead=24):
        """Make predictions for a specific bolt and measurement type"""
        # Get historical data
        historical_data = self.get_historical_data(bolt_id, measurement_type)
        
        if historical_data is None or len(historical_data) < 24:
            logger.warning(f"Insufficient data for predictions for bolt {bolt_id}, {measurement_type}")
            return None
        
        # Check if model needs training/updating
        current_time = time.time()
        if (models[measurement_type] is None or 
            current_time - last_model_update[measurement_type] > self.config["model_update_interval"]):
            self.train_random_forest_model(historical_data, measurement_type)
        
        # Prepare current data for prediction
        latest_data = historical_data[-24:]  # Last 24 hours
        
        # Create feature set for prediction
        prediction_df = pd.DataFrame(latest_data)
        prediction_df.columns = ["value"]
        
        # Add time-based features for the prediction window
        last_timestamp = prediction_df.index[-1]
        prediction_df["hour"] = prediction_df.index.hour
        prediction_df["day_of_week"] = prediction_df.index.dayofweek
        prediction_df["day_of_month"] = prediction_df.index.day
        prediction_df["month"] = prediction_df.index.month
        
        # Add lag features
        for i in range(1, 25):
            if i < len(prediction_df):
                prediction_df[f"lag_{i}"] = prediction_df["value"].shift(i)
            else:
                prediction_df[f"lag_{i}"] = prediction_df["value"].iloc[0]  # Fallback for shorter data
        
        # Take the last row (current time) for prediction
        current_features = prediction_df.iloc[-1:].drop("value", axis=1)
        
        # Scale features
        current_features_scaled = scalers[measurement_type].transform(current_features)
        
        # Make prediction
        if models[measurement_type] is not None:
            predictions = models[measurement_type].predict(current_features_scaled)[0]
            
            # Create result with timestamps
            result = []
            for i, pred in enumerate(predictions):
                future_time = last_timestamp + datetime.timedelta(hours=i+1)
                result.append({
                    "timestamp": future_time.isoformat(),
                    "value": float(pred),
                    "hour": i+1
                })
            
            return result
        else:
            logger.warning(f"No model available for {measurement_type}")
            return None
    
    def analyze_predictions(self, bolt_id):
        """Analyze predictions for a bolt and determine if alerts should be triggered"""
        alerts = []
        
        for measurement_type in ["temperature", "pressure"]:
            predictions = self.make_predictions(bolt_id, measurement_type)
            
            if predictions is None:
                continue
            
            thresholds = self.config["alert_thresholds"][measurement_type]
            
            for prediction in predictions:
                value = prediction["value"]
                alert_level = None
                
                if value >= thresholds["critical"]:
                    alert_level = "critical"
                elif value >= thresholds["warning"]:
                    alert_level = "warning"
                
                if alert_level:
                    # Check when the threshold will be crossed
                    hours_until = prediction["hour"]
                    alert = {
                        "bolt_id": bolt_id,
                        "type": measurement_type,
                        "predicted_value": value,
                        "threshold": thresholds[alert_level],
                        "alert_level": alert_level,
                        "hours_until": hours_until,
                        "timestamp": prediction["timestamp"]
                    }
                    alerts.append(alert)
                    break  # Only report the first threshold crossing
        
        return alerts
    
    def send_alerts(self, alerts):
        """Send alerts to Web Dashboard and Telegram Bot via REST API"""
        if not alerts:
            return
        
        # Get service endpoints from catalog
        try:
            response = requests.get(f"{self.config['catalog_url']}/services")
            if response.status_code != 200:
                logger.error(f"Failed to get services from catalog: {response.status_code}")
                return
            
            services = response.json()
            
            # Find Web Dashboard and Telegram Bot services
            web_dashboard = next((s for s in services if s["name"] == "Web Dashboard"), None)
            telegram_bot = next((s for s in services if s["name"] == "Telegram Bot"), None)
            
            # Send alerts to Web Dashboard
            if web_dashboard and "alert_endpoint" in web_dashboard.get("apis", {}):
                dashboard_url = f"{web_dashboard['endpoint']}{web_dashboard['apis']['alert_endpoint']}"
                try:
                    response = requests.post(dashboard_url, json={"alerts": alerts})
                    if response.status_code == 200:
                        logger.info(f"Successfully sent {len(alerts)} alerts to Web Dashboard")
                    else:
                        logger.error(f"Failed to send alerts to Web Dashboard: {response.status_code}")
                except Exception as e:
                    logger.error(f"Error sending alerts to Web Dashboard: {str(e)}")
            
            # Send alerts to Telegram Bot
            if telegram_bot and "alert_endpoint" in telegram_bot.get("apis", {}):
                telegram_url = f"{telegram_bot['endpoint']}{telegram_bot['apis']['alert_endpoint']}"
                try:
                    response = requests.post(telegram_url, json={"alerts": alerts})
                    if response.status_code == 200:
                        logger.info(f"Successfully sent {len(alerts)} alerts to Telegram Bot")
                    else:
                        logger.error(f"Failed to send alerts to Telegram Bot: {response.status_code}")
                except Exception as e:
                    logger.error(f"Error sending alerts to Telegram Bot: {str(e)}")
        
        except Exception as e:
            logger.error(f"Error in send_alerts: {str(e)}")
    
    def run_analysis_loop(self):
        """Main loop to run periodic analysis and generate alerts"""
        while True:
            try:
                # Update service registration
                self.update_registration()
                
                # Get all sectors
                sectors = self.get_bolt_sectors()
                all_alerts = []
                
                for sector in sectors:
                    sector_id = sector["id"]
                    # Get bolts in this sector
                    bolts = self.get_bolts_in_sector(sector_id)
                    
                    for bolt in bolts:
                        bolt_id = bolt["id"]
                        # Analyze predictions for this bolt
                        alerts = self.analyze_predictions(bolt_id)
                        if alerts:
                            all_alerts.extend(alerts)
                
                # Send alerts if any were generated
                if all_alerts:
                    self.send_alerts(all_alerts)
                    logger.info(f"Generated and sent {len(all_alerts)} alerts")
                
                # Sleep until next analysis cycle
                time.sleep(self.config["analysis_interval"])
            
            except Exception as e:
                logger.error(f"Error in analysis loop: {str(e)}")
                # Sleep for a bit before retrying
                time.sleep(60)

# Flask API routes
@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200

@app.route('/api/predictions', methods=['GET'])
def get_predictions():
    """Get predictions for a specific bolt and measurement type"""
    bolt_id = request.args.get('bolt_id')
    measurement_type = request.args.get('type')
    hours = int(request.args.get('hours', 24))
    
    if not bolt_id or not measurement_type:
        return jsonify({"error": "Missing required parameters"}), 400
    
    if measurement_type not in ["temperature", "pressure"]:
        return jsonify({"error": "Invalid measurement type"}), 400
    
    analytics_service = app.config["analytics_service"]
    predictions = analytics_service.make_predictions(bolt_id, measurement_type, hours)
    
    if predictions is None:
        return jsonify({"error": "Failed to generate predictions"}), 500
    
    return jsonify({"predictions": predictions}), 200

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """Get current alerts for a specific bolt or all bolts"""
    bolt_id = request.args.get('bolt_id')
    
    analytics_service = app.config["analytics_service"]
    
    if bolt_id:
        # Get alerts for specific bolt
        alerts = analytics_service.analyze_predictions(bolt_id)
    else:
        # Get alerts for all bolts in all sectors
        alerts = []
        sectors = analytics_service.get_bolt_sectors()
        
        for sector in sectors:
            sector_id = sector["id"]
            bolts = analytics_service.get_bolts_in_sector(sector_id)
            
            for bolt in bolts:
                bolt_alerts = analytics_service.analyze_predictions(bolt["id"])
                if bolt_alerts:
                    alerts.extend(bolt_alerts)
    
    return jsonify({"alerts": alerts}), 200

def start_analysis_thread(analytics_service):
    """Start the background analysis thread"""
    analysis_thread = threading.Thread(target=analytics_service.run_analysis_loop)
    analysis_thread.daemon = True
    analysis_thread.start()
    logger.info("Analysis background thread started")

if __name__ == "__main__":
    try:
        # Initialize the analytics service
        analytics_service = AnalyticsService(CONFIG)
        app.config["analytics_service"] = analytics_service
        
        # Start background analysis thread
        start_analysis_thread(analytics_service)
        
        # Start Flask app
        port = int(os.getenv("PORT", "5000"))
        app.run(host="0.0.0.0", port=port)
    except Exception as e:
        logger.critical(f"Failed to start analytics service: {str(e)}")