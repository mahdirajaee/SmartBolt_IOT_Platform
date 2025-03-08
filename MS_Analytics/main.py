import os
import json
import time
import logging
import datetime
import requests
import numpy as np
import pandas as pd
import cherrypy
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.arima.model import ARIMA
import threading

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("analytics_service.log")
    ]
)
logger = logging.getLogger("AnalyticsService")

CONFIG = {
    "catalog_url": os.getenv("CATALOG_URL", "http://localhost:8080"),
    "timeseries_db_url": os.getenv("TIMESERIES_DB_URL", "http://localhost:8086"),
    "prediction_interval": int(os.getenv("PREDICTION_INTERVAL", "3600")),
    "alert_thresholds": {
        "temperature": {
            "warning": float(os.getenv("TEMP_WARNING_THRESHOLD", "85.0")),
            "critical": float(os.getenv("TEMP_CRITICAL_THRESHOLD", "95.0"))
        },
        "pressure": {
            "warning": float(os.getenv("PRESSURE_WARNING_THRESHOLD", "8.5")),
            "critical": float(os.getenv("PRESSURE_CRITICAL_THRESHOLD", "9.5"))
        }
    },
    "prediction_window": int(os.getenv("PREDICTION_WINDOW", "24")),
    "model_update_interval": int(os.getenv("MODEL_UPDATE_INTERVAL", "86400")),
    "analysis_interval": int(os.getenv("ANALYSIS_INTERVAL", "3600")),
    "service_id": "analytics_microservice"
}

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
        pass
    
    def get_bolt_sectors(self):
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
    
    def get_historical_data(self, bolt_id, measurement_type, hours=168):
        end_time = datetime.datetime.now()
        start_time = end_time - datetime.timedelta(hours=hours)
        
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
                
                df = pd.DataFrame(data["measurements"])
                df["timestamp"] = pd.to_datetime(df["timestamp"])
                df.set_index("timestamp", inplace=True)
                df.sort_index(inplace=True)
                
                hourly_data = df["value"].resample("1H").mean().interpolate(method="time")
                
                return hourly_data
            else:
                logger.error(f"Failed to get historical data: {response.status_code} {response.text}")
                return None
        except Exception as e:
            logger.error(f"Error getting historical data: {str(e)}")
            return None
    
    def train_random_forest_model(self, data, measurement_type):
        if data is None or len(data) < 24:
            logger.warning(f"Insufficient data to train model for {measurement_type}")
            return None
        
        df = pd.DataFrame(data)
        df.columns = ["value"]
        
        df["hour"] = df.index.hour
        df["day_of_week"] = df.index.dayofweek
        df["day_of_month"] = df.index.day
        df["month"] = df.index.month
        
        for i in range(1, 25):
            df[f"lag_{i}"] = df["value"].shift(i)
        
        for i in range(1, self.config["prediction_window"] + 1):
            df[f"future_{i}"] = df["value"].shift(-i)
        
        df.dropna(inplace=True)
        
        if len(df) == 0:
            logger.warning(f"No valid data after feature engineering for {measurement_type}")
            return None
        
        X = df.drop([f"future_{i}" for i in range(1, self.config["prediction_window"] + 1)], axis=1)
        y = df[[f"future_{i}" for i in range(1, self.config["prediction_window"] + 1)]]
        
        X_values = X.values
        scaler = scalers[measurement_type]
        scaler.fit(X_values)
        X_scaled = scaler.transform(X_values)
        
        model = RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1)
        model.fit(X_scaled, y)
        
        models[measurement_type] = model
        last_model_update[measurement_type] = time.time()
        
        logger.info(f"Successfully trained model for {measurement_type}")
        return model
    
    def make_predictions(self, bolt_id, measurement_type, hours_ahead=24):
        historical_data = self.get_historical_data(bolt_id, measurement_type)
        
        if historical_data is None or len(historical_data) < 24:
            logger.warning(f"Insufficient data for predictions for bolt {bolt_id}, {measurement_type}")
            return None
        
        current_time = time.time()
        if (models[measurement_type] is None or 
            current_time - last_model_update[measurement_type] > self.config["model_update_interval"]):
            self.train_random_forest_model(historical_data, measurement_type)
        
        latest_data = historical_data[-24:]
        
        prediction_df = pd.DataFrame(latest_data)
        prediction_df.columns = ["value"]
        
        last_timestamp = prediction_df.index[-1]
        prediction_df["hour"] = prediction_df.index.hour
        prediction_df["day_of_week"] = prediction_df.index.dayofweek
        prediction_df["day_of_month"] = prediction_df.index.day
        prediction_df["month"] = prediction_df.index.month
        
        for i in range(1, 25):
            if i < len(prediction_df):
                prediction_df[f"lag_{i}"] = prediction_df["value"].shift(i)
            else:
                prediction_df[f"lag_{i}"] = prediction_df["value"].iloc[0]
        
        current_features = prediction_df.iloc[-1:].drop("value", axis=1)
        
        current_features_scaled = scalers[measurement_type].transform(current_features)
        
        if models[measurement_type] is not None:
            predictions = models[measurement_type].predict(current_features_scaled)[0]
            
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
                    break
        
        return alerts
    
    def send_alerts(self, alerts):
        if not alerts:
            return
        
        try:
            response = requests.get(f"{self.config['catalog_url']}/services")
            if response.status_code != 200:
                logger.error(f"Failed to get services from catalog: {response.status_code}")
                return
            
            services = response.json()
            
            web_dashboard = next((s for s in services if s["name"] == "Web Dashboard"), None)
            telegram_bot = next((s for s in services if s["name"] == "Telegram Bot"), None)
            
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
        while True:
            try:
                self.update_registration()
                
                sectors = self.get_bolt_sectors()
                all_alerts = []
                
                for sector in sectors:
                    sector_id = sector["id"]
                    bolts = self.get_bolts_in_sector(sector_id)
                    
                    for bolt in bolts:
                        bolt_id = bolt["id"]
                        alerts = self.analyze_predictions(bolt_id)
                        if alerts:
                            all_alerts.extend(alerts)
                
                if all_alerts:
                    self.send_alerts(all_alerts)
                    logger.info(f"Generated and sent {len(all_alerts)} alerts")
                
                time.sleep(self.config["analysis_interval"])
            
            except Exception as e:
                logger.error(f"Error in analysis loop: {str(e)}")
                time.sleep(60)


class AnalyticsRESTService:
    def __init__(self, analytics_service):
        self.analytics_service = analytics_service
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def health(self):
        return {"status": "healthy"}
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def predictions(self, bolt_id=None, type=None, hours=24):
        if not bolt_id or not type:
            raise cherrypy.HTTPError(400, "Missing required parameters")
        
        if type not in ["temperature", "pressure"]:
            raise cherrypy.HTTPError(400, "Invalid measurement type")
        
        predictions = self.analytics_service.make_predictions(bolt_id, type, int(hours))
        
        if predictions is None:
            raise cherrypy.HTTPError(500, "Failed to generate predictions")
        
        return {"predictions": predictions}
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def alerts(self, bolt_id=None):
        if bolt_id:
            alerts = self.analytics_service.analyze_predictions(bolt_id)
        else:
            alerts = []
            sectors = self.analytics_service.get_bolt_sectors()
            
            for sector in sectors:
                sector_id = sector["id"]
                bolts = self.analytics_service.get_bolts_in_sector(sector_id)
                
                for bolt in bolts:
                    bolt_alerts = self.analytics_service.analyze_predictions(bolt["id"])
                    if bolt_alerts:
                        alerts.extend(bolt_alerts)
        
        return {"alerts": alerts}


def start_analysis_thread(analytics_service):
    analysis_thread = threading.Thread(target=analytics_service.run_analysis_loop)
    analysis_thread.daemon = True
    analysis_thread.start()
    logger.info("Analysis background thread started")


def setup_api_endpoints():
    analytics_service = AnalyticsService(CONFIG)
    
    start_analysis_thread(analytics_service)
    
    rest_service = AnalyticsRESTService(analytics_service)
    
    conf = {
        '/': {
            'tools.sessions.on': True,
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [('Content-Type', 'application/json')],
        }
    }
    
    api = cherrypy.tree.mount(rest_service, '/', conf)
    
    api.merge({
        '/health': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
        },
        '/api/predictions': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
        },
        '/api/alerts': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
        }
    })
    
    return analytics_service


if __name__ == "__main__":
    try:
        cherrypy.config.update({
            'server.socket_host': '0.0.0.0',
            'server.socket_port': int(os.getenv("PORT", "5001")),
            'engine.autoreload.on': False,
            'log.access_file': 'access.log',
            'log.error_file': 'error.log'
        })
        
        analytics_service = setup_api_endpoints()
        
        cherrypy.engine.start()
        cherrypy.engine.block()
        
    except Exception as e:
        logger.critical(f"Failed to start analytics service: {str(e)}")