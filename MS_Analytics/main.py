#!/usr/bin/env python3

import requests
import time
import json
import logging
import threading
import datetime
import pandas as pd
import cherrypy
import config
from prediction import PredictionEngine
from alert import AlertManager
import registration

# Set up global objects
prediction_engine = PredictionEngine()
alert_manager = AlertManager()
last_analysis_time = None
latest_forecast = None
latest_risk_level = 'NORMAL'

def fetch_sensor_data(hours=24):
    """Fetch historical sensor data from the time series database"""
    try:
        # If we haven't found the timeseries service from Resource Catalog yet
        if not config.TIMESERIES_DB_API_URL:
            service_data = registration.discover_services()
            if service_data and service_data.get("endpoints", {}).get("api"):
                config.TIMESERIES_DB_API_URL = service_data.get("endpoints", {}).get("api")
                logger.info(f"Discovered Time Series DB API URL: {config.TIMESERIES_DB_API_URL}")
            else:
                logger.error("Failed to discover Time Series DB API URL from Resource Catalog")
                return None
        # Calculate the time range for the query
        end_time = datetime.datetime.now().isoformat()
        start_time = (datetime.datetime.now() - datetime.timedelta(hours=hours)).isoformat()
        
        # Make the request to the time series DB API
        url = f"{config.TIMESERIES_DB_API_URL}/all_seneor_data"
        params = {
            'start': start_time,
            'end': end_time,
            # 'metrics': 'temperature,pressure'
        }
        print(f"@@@@ Fetching sensor data from @@@@ {url}/////{params}")
        response = requests.get(url, params=params, timeout=100)
        print(f"@@@@########## Fetching sensor data from #############@@@@ {response}")
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and len(data['data']) > 0:
                logger.info(f"Fetched {len(data['data'])} sensor readings from time series DB")
                return data['data']
            else:
                logger.warning("No sensor data returned from time series DB")
                return None
        else:
            logger.error(f"Error fetching sensor data: HTTP {response.status_code}")
            return None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error fetching sensor data: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching sensor data: {e}")
        return None

def run_analysis():
    """Run the full analysis pipeline: fetch data, predict, evaluate risk, send alerts"""
    global last_analysis_time, latest_forecast, latest_risk_level
    
    try:
        logger.info("Starting analysis run")
        
        # Fetch historical sensor data
        sensor_data = fetch_sensor_data(hours=config.DATA_HISTORY_HOURS)
        if not sensor_data or len(sensor_data) < 10:  # Need enough data points for prediction
            logger.warning("Insufficient sensor data for analysis")
            return False
        
        # Convert to pandas DataFrame
        df = pd.DataFrame(sensor_data)
        
        # Train the prediction models
        if not prediction_engine.train_models(df):
            logger.error("Failed to train prediction models")
            return False
        
        # Make predictions
        forecast_data = prediction_engine.predict_future_values(
            minutes_ahead=config.FORECAST_HORIZON_MINUTES
        )
        
        if forecast_data is None or forecast_data.empty:
            logger.error("Failed to generate forecast data")
            return False
        
        # Evaluate risk levels
        forecast_with_risk, risk_level = prediction_engine.evaluate_risk(forecast_data)
        
        # Store the latest results
        latest_forecast = forecast_with_risk
        latest_risk_level = risk_level
        last_analysis_time = datetime.datetime.now()
        
        # Generate and send alerts if needed
        if risk_level != 'NORMAL':
            alert_result = alert_manager.process_alert(forecast_with_risk, risk_level)
            if alert_result:
                logger.info(f"Alert sent for {risk_level} risk level")
        
        logger.info(f"Analysis completed successfully. Risk level: {risk_level}")
        return True
        
    except Exception as e:
        logger.error(f"Error running analysis: {e}")
        return False

def analysis_worker():
    """Background worker that runs the analysis at regular intervals"""
    while True:
        try:
            run_analysis()
        except Exception as e:
            logger.error(f"Error in analysis worker: {e}")
        
        # Sleep for the configured interval
        time.sleep(config.ANALYSIS_FREQUENCY_SECONDS)

class AnalyticsAPI:
    """CherryPy REST API for Analytics service"""
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def health(self):
        """Health check endpoint"""
        return {
            "status": "healthy",
            "service": config.SERVICE_NAME,
            "timestamp": datetime.datetime.now().isoformat()
        }
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def forecast(self):
        """Endpoint to get the latest forecast data"""
        if latest_forecast is None:
            cherrypy.response.status = 404
            return {
                "status": "error",
                "message": "No forecast data available yet"
            }
        
        # Convert DataFrame to dict for JSON serialization
        df = latest_forecast.copy()
        # Convert any datetime columns to ISO format strings
        df['forecast_timestamp'] = df['forecast_timestamp'].astype(str)
        # Convert DataFrame to dict for JSON serialization
        forecast_dict = df.to_dict(orient='records')
        
        return {
            "status": "success",
            "data": {
                "forecast": forecast_dict,
                "risk_level": latest_risk_level,
                "generated_at": last_analysis_time.isoformat() if last_analysis_time else None,
                "config": {
                    "temperature_warning_threshold": config.TEMPERATURE_WARNING_THRESHOLD,
                    "temperature_max_threshold": config.TEMPERATURE_MAX_THRESHOLD,
                    "pressure_warning_threshold": config.PRESSURE_WARNING_THRESHOLD,
                    "pressure_max_threshold": config.PRESSURE_MAX_THRESHOLD
                }
            }
        }
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    @cherrypy.tools.json_in()
    def run_analysis(self):
        """Manually trigger an analysis run"""
        success = run_analysis()
        if success:
            return {
                "status": "success",
                "message": "Analysis completed successfully",
                "risk_level": latest_risk_level,
                "timestamp": datetime.datetime.now().isoformat()
            }
        else:
            cherrypy.response.status = 500
            return {
                "status": "error",
                "message": "Analysis failed. Check logs for details.",
                "timestamp": datetime.datetime.now().isoformat()
            }

def main():
    """Main entry point for the application"""
    try:
        # Register with Resource Catalog
        registration.start_registration(background=True)
        
        # Start the background analysis worker
        analysis_thread = threading.Thread(target=analysis_worker, daemon=True)
        analysis_thread.start()
        
        # Configure CherryPy server
        cherrypy.config.update({
            'server.socket_host': '0.0.0.0',
            'server.socket_port': config.API_PORT,  # Use port from config instead of hardcoded value
            'engine.autoreload.on': False
        })
        
        # Configure API paths
        conf = {
            '/': {
                'tools.response_headers.on': True,
                'tools.response_headers.headers': [('Content-Type', 'application/json')],
            }
        }
        
        # Mount API endpoints
        cherrypy.tree.mount(AnalyticsAPI(), '/api', conf)
        
        # Start the server
        cherrypy.engine.start()
        logger.info(f"Analytics service started on port {config.API_PORT}")
        
        # Keep main thread alive
        cherrypy.engine.block()
    except KeyboardInterrupt:
        logger.info("Shutting down analytics service")
        # Update status to offline before exiting
        registration.update_status("offline")
        cherrypy.engine.exit()

if __name__ == "__main__":
    # Set up logging
    logger = logging.getLogger("analytics_service")
    main()