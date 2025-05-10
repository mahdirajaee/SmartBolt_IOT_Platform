#!/usr/bin/env python3

import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import datetime
import logging
import config

# Setup logging
logger = logging.getLogger('prediction')

class PredictionEngine:
    """Handles predictions of temperature and pressure based on historical data"""
    
    def __init__(self):
        self.temp_model = None
        self.pressure_model = None
        
    def preprocess_data(self, data):
        """Preprocess the sensor data for prediction analysis"""
        try:
            # Convert to DataFrame if it's not already
            if not isinstance(data, pd.DataFrame):
                df = pd.DataFrame(data)
            else:
                df = data.copy()
            
            # Ensure timestamp column exists and is in datetime format
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df = df.sort_values('timestamp')
                
                # Add time-based features
                df['hour'] = df['timestamp'].dt.hour
                df['minute'] = df['timestamp'].dt.minute
                
                # Calculate the time difference in minutes from the first entry
                start_time = df['timestamp'].min()
                df['minutes_elapsed'] = (df['timestamp'] - start_time).dt.total_seconds() / 60
                
                return df
            else:
                logger.error("No timestamp column in data")
                return None
        except Exception as e:
            logger.error(f"Error preprocessing data: {e}")
            return None
    
    def train_models(self, historical_data):
        """Train prediction models using historical sensor data"""
        try:
            df = self.preprocess_data(historical_data)
            if df is None or df.empty:
                logger.error("No valid data for training models")
                return False
            
            # Check if temperature and pressure columns exist
            if 'temperature' not in df.columns or 'pressure' not in df.columns:
                logger.error(f"Missing required columns in data. Available columns: {df.columns}")
                return False
            
            # Features for prediction (time-based)
            X = df[['minutes_elapsed']].values
            
            # Train temperature model
            y_temp = df['temperature'].values
            self.temp_model = LinearRegression()
            self.temp_model.fit(X, y_temp)
            logger.info("Temperature prediction model trained")
            
            # Train pressure model
            y_pressure = df['pressure'].values
            self.pressure_model = LinearRegression()
            self.pressure_model.fit(X, y_pressure)
            logger.info("Pressure prediction model trained")
            
            return True
        except Exception as e:
            logger.error(f"Error training prediction models: {e}")
            return False
    
    def predict_future_values(self, minutes_ahead=30):
        """Predict temperature and pressure values for the specified time ahead"""
        if self.temp_model is None or self.pressure_model is None:
            logger.error("Models not trained yet")
            return None
        
        try:
            # Create feature array for future prediction points
            # For simplicity, we'll predict at 5-minute intervals
            intervals = range(5, minutes_ahead + 1, 5)
            future_X = np.array(intervals).reshape(-1, 1)
            
            # Predict future values
            future_temp = self.temp_model.predict(future_X)
            future_pressure = self.pressure_model.predict(future_X)
            
            # Create a result DataFrame with predictions
            result = pd.DataFrame({
                'minutes_ahead': intervals,
                'forecasted_temperature': future_temp,
                'forecasted_pressure': future_pressure
            })
            
            # Add forecast timestamps
            now = datetime.datetime.now()
            result['forecast_timestamp'] = [now + datetime.timedelta(minutes=m) for m in intervals]
            
            return result
        except Exception as e:
            logger.error(f"Error predicting future values: {e}")
            return None
    
    def evaluate_risk(self, forecast_data):
        """Evaluate the risk level based on forecasted values"""
        if forecast_data is None or forecast_data.empty:
            logger.error("No forecast data to evaluate")
            return None
        
        try:
            # Create a copy to avoid modifying the original
            result = forecast_data.copy()
            
            # Initialize risk level columns
            result['temperature_risk'] = 'NORMAL'
            result['pressure_risk'] = 'NORMAL'
            result['overall_risk'] = 'NORMAL'
            result['risk_level'] = config.ALERT_LEVELS['NORMAL']
            
            # Evaluate temperature risks
            mask = result['forecasted_temperature'] > config.TEMPERATURE_MAX_THRESHOLD
            result.loc[mask, 'temperature_risk'] = 'DANGER'
            result.loc[mask, 'risk_level'] = config.ALERT_LEVELS['DANGER']
            
            mask = (result['forecasted_temperature'] > config.TEMPERATURE_WARNING_THRESHOLD) & \
                   (result['forecasted_temperature'] <= config.TEMPERATURE_MAX_THRESHOLD)
            result.loc[mask, 'temperature_risk'] = 'WARNING'
            # Only update risk level if it's not already higher
            mask = mask & (result['risk_level'] < config.ALERT_LEVELS['WARNING'])
            result.loc[mask, 'risk_level'] = config.ALERT_LEVELS['WARNING']
            
            # Evaluate pressure risks
            mask = result['forecasted_pressure'] > config.PRESSURE_MAX_THRESHOLD
            result.loc[mask, 'pressure_risk'] = 'DANGER'
            result.loc[mask, 'risk_level'] = config.ALERT_LEVELS['DANGER']
            
            mask = (result['forecasted_pressure'] > config.PRESSURE_WARNING_THRESHOLD) & \
                   (result['forecasted_pressure'] <= config.PRESSURE_MAX_THRESHOLD)
            result.loc[mask, 'pressure_risk'] = 'WARNING'
            # Only update risk level if it's not already higher
            mask = mask & (result['risk_level'] < config.ALERT_LEVELS['WARNING'])
            result.loc[mask, 'risk_level'] = config.ALERT_LEVELS['WARNING']
            
            # Set overall risk based on the highest risk level
            result.loc[result['risk_level'] == config.ALERT_LEVELS['DANGER'], 'overall_risk'] = 'DANGER'
            result.loc[result['risk_level'] == config.ALERT_LEVELS['WARNING'], 'overall_risk'] = 'WARNING'
            
            # Check if any forecast exceeds thresholds
            has_warning = (result['risk_level'] >= config.ALERT_LEVELS['WARNING']).any()
            has_danger = (result['risk_level'] >= config.ALERT_LEVELS['DANGER']).any()
            
            max_risk = 'NORMAL'
            if has_danger:
                max_risk = 'DANGER'
            elif has_warning:
                max_risk = 'WARNING'
            
            logger.info(f"Risk evaluation completed. Max risk level: {max_risk}")
            
            return result, max_risk
        except Exception as e:
            logger.error(f"Error evaluating risk: {e}")
            return None, 'UNKNOWN'