#!/usr/bin/env python3

import requests
import json
import datetime
import logging
import config

# Setup logging
logger = logging.getLogger('alert')

class AlertManager:
    """Manages the generation and distribution of alerts"""
    
    def __init__(self):
        self.last_alert_time = {}  # Track when last alert of each type was sent
        self.alert_cooldown = 300  # 5 minutes between repeated alerts of same type
    
    def generate_alert(self, risk_data, risk_level):
        """Generate an alert based on the risk evaluation"""
        if risk_data is None:
            logger.error("No risk data provided for alert generation")
            return None
        
        try:
            # Get the soonest forecast that represents the highest risk
            if risk_level == 'DANGER':
                subset = risk_data[risk_data['overall_risk'] == 'DANGER']
            elif risk_level == 'WARNING':
                subset = risk_data[risk_data['overall_risk'] == 'WARNING']
            else:
                logger.info("No alert needed - normal conditions")
                return None
                
            if subset.empty:
                logger.warning(f"Risk level is {risk_level} but no matching forecasts found")
                return None
                
            # Get the earliest forecast with the highest risk
            earliest_forecast = subset.iloc[0]
            
            # Determine what triggers the alert
            triggers = []
            if earliest_forecast['temperature_risk'] != 'NORMAL':
                triggers.append('temperature')
            if earliest_forecast['pressure_risk'] != 'NORMAL':
                triggers.append('pressure')
                
            if not triggers:
                logger.warning("No specific trigger identified for alert")
                return None
                
            # Create alert data
            alert = {
                'alert_id': f"alert-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
                'timestamp': datetime.datetime.now().isoformat(),
                'risk_level': risk_level,
                'triggers': triggers,
                'forecast_timestamp': earliest_forecast['forecast_timestamp'].isoformat(),
                'minutes_ahead': int(earliest_forecast['minutes_ahead']),
                'forecasted_values': {
                    'temperature': float(earliest_forecast['forecasted_temperature']),
                    'pressure': float(earliest_forecast['forecasted_pressure'])
                },
                'thresholds': {
                    'temperature_warning': config.TEMPERATURE_WARNING_THRESHOLD,
                    'temperature_danger': config.TEMPERATURE_MAX_THRESHOLD,
                    'pressure_warning': config.PRESSURE_WARNING_THRESHOLD,
                    'pressure_danger': config.PRESSURE_MAX_THRESHOLD
                },
                'message': self._generate_alert_message(
                    risk_level, 
                    triggers, 
                    int(earliest_forecast['minutes_ahead']),
                    {
                        'temperature': float(earliest_forecast['forecasted_temperature']),
                        'pressure': float(earliest_forecast['forecasted_pressure'])
                    }
                )
            }
            
            logger.info(f"Generated {risk_level} alert: {alert['message']}")
            return alert
            
        except Exception as e:
            logger.error(f"Error generating alert: {e}")
            return None
    
    def _generate_alert_message(self, risk_level, triggers, minutes_ahead, values):
        """Generate a human-readable alert message"""
        if risk_level == 'DANGER':
            prefix = "DANGER ALERT:"
        elif risk_level == 'WARNING':
            prefix = "WARNING ALERT:"
        else:
            prefix = "NOTICE:"
            
        trigger_texts = []
        if 'temperature' in triggers:
            temp_val = values['temperature']
            if temp_val > config.TEMPERATURE_MAX_THRESHOLD:
                trigger_texts.append(f"Temperature expected to reach critical level of {temp_val:.1f}°C")
            elif temp_val > config.TEMPERATURE_WARNING_THRESHOLD:
                trigger_texts.append(f"Temperature expected to reach concerning level of {temp_val:.1f}°C")
                
        if 'pressure' in triggers:
            pressure_val = values['pressure']
            if pressure_val > config.PRESSURE_MAX_THRESHOLD:
                trigger_texts.append(f"Pressure expected to reach critical level of {pressure_val:.1f} PSI")
            elif pressure_val > config.PRESSURE_WARNING_THRESHOLD:
                trigger_texts.append(f"Pressure expected to reach concerning level of {pressure_val:.1f} PSI")
        
        time_text = f"in approximately {minutes_ahead} minutes."
        
        return f"{prefix} {'; '.join(trigger_texts)} {time_text}"
    
    def should_send_alert(self, risk_level, triggers):
        """Determine if we should send an alert based on cooldown periods"""
        now = datetime.datetime.now()
        alert_key = f"{risk_level}-{'-'.join(sorted(triggers))}"
        
        # If we've never sent this alert, or cooldown has passed, send it
        if alert_key not in self.last_alert_time:
            self.last_alert_time[alert_key] = now
            return True
            
        # Check if cooldown period has passed
        time_diff = (now - self.last_alert_time[alert_key]).total_seconds()
        if time_diff > self.alert_cooldown:
            self.last_alert_time[alert_key] = now
            return True
            
        return False
    
    def send_to_dashboard(self, alert):
        """Send alert to web dashboard via REST API"""
        if not alert:
            return False
            
        try:
            if not config.DASHBOARD_API_URL:
                logger.info("Dashboard URL not configured, skipping dashboard notification")
                return False
                
            response = requests.post(
                config.DASHBOARD_API_URL,
                json=alert,
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            
            if response.status_code == 200 or response.status_code == 201:
                logger.info("Alert sent to dashboard successfully")
                return True
            else:
                logger.error(f"Failed to send alert to dashboard. Status code: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending alert to dashboard: {e}")
            return False
    
    def send_to_telegram(self, alert):
        """Send alert to Telegram Bot"""
        if not alert:
            return False
            
        try:
            if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
                logger.info("Telegram credentials not configured, skipping Telegram notification")
                return False
                
            # Prepare message for Telegram
            message = alert['message']
            
            # Telegram Bot API endpoint
            url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
            
            # Send the message
            response = requests.post(
                url,
                json={
                    "chat_id": config.TELEGRAM_CHAT_ID,
                    "text": message,
                    "parse_mode": "HTML"
                },
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info("Alert sent to Telegram successfully")
                return True
            else:
                logger.error(f"Failed to send alert to Telegram. Status code: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error sending alert to Telegram: {e}")
            return False
    
    def process_alert(self, risk_data, risk_level):
        """Process and send alerts if needed"""
        # If normal risk level, no alert needed
        if risk_level == 'NORMAL':
            return False
            
        try:
            # Generate the alert
            alert = self.generate_alert(risk_data, risk_level)
            if not alert:
                return False
                
            # Check if we should send based on cooldown
            if not self.should_send_alert(risk_level, alert['triggers']):
                logger.info("Alert suppressed due to cooldown period")
                return False
                
            # Send to available notification channels
            dashboard_result = self.send_to_dashboard(alert)
            telegram_result = self.send_to_telegram(alert)
            
            return dashboard_result or telegram_result
            
        except Exception as e:
            logger.error(f"Error processing alert: {e}")
            return False