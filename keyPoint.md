Key Differences Between Analytics and Control Center
1. Analytics Service (Existing)
The Analytics service currently focuses on:

Predictive Analysis: Uses machine learning (LinearRegression) to forecast future temperature and pressure values
Risk Evaluation: Evaluates risk levels (NORMAL, WARNING, DANGER) based on forecasted values
Alert Generation: Generates alerts when predicted values exceed thresholds
Notification: Sends alerts to dashboard and Telegram (when configured)
It's primarily focused on future predictions (forecasting what will happen in the next 5-30 minutes) and generating alerts based on those predictions.

2. Control Center (New Service)
The Control Center would focus on:

Real-time Monitoring: Processing current sensor readings as they arrive
Immediate Decision Making: Evaluating current conditions against rules
Direct Control Actions: Sending commands to valves when thresholds are exceeded
Real-time Alerts: Generating alerts for immediate action
It would be focused on current conditions and taking immediate control actions when needed.

How They Complement Each Other
These services would work together in a complementary way:

Analytics provides predictive insights - "The temperature is likely to reach critical levels in 15 minutes"
Control Center provides immediate actions - "Temperature is too high right now, close the valve"
Example Workflow Together
Analytics predicts temperature will reach a dangerous level in 10 minutes
Analytics sends an alert to Telegram and dashboard
Control Center monitors actual readings in real-time
When actual temperature exceeds thresholds, Control Center immediately sends command to close valve
Control Center sends confirmation of action taken
Implementation Benefits
This separation provides several advantages:

Separation of concerns: The Analytics service can focus on complex prediction algorithms while Control Center can focus on responsive actions
Redundancy: If one service fails, the other can still function
Different optimization priorities: Analytics can be optimized for computational analysis, while Control Center can be optimized for low latency
Different scaling needs: Analytics might need to scale for computational power, while Control Center might need to scale for high throughput of messages



3. analytics : 
/api/forecast : 
{
  "status": "success",
  "data": {
    "forecast": [
      {
        "minutes_ahead": 5,
        "forecasted_temperature": 75.2,
        "forecasted_pressure": 102.4,
        "forecast_timestamp": "2025-04-26T16:35:00.000Z",
        "temperature_risk": "NORMAL",
        "pressure_risk": "NORMAL",
        "overall_risk": "NORMAL",
        "risk_level": 0
      },
      {
        "minutes_ahead": 10,
        "forecasted_temperature": 78.6,
        "forecasted_pressure": 103.1,
        "forecast_timestamp": "2025-04-26T16:40:00.000Z",
        "temperature_risk": "NORMAL",
        "pressure_risk": "NORMAL",
        "overall_risk": "NORMAL",
        "risk_level": 0
      },
      {
        "minutes_ahead": 15,
        "forecasted_temperature": 82.1,
        "forecasted_pressure": 104.5,
        "forecast_timestamp": "2025-04-26T16:45:00.000Z",
        "temperature_risk": "WARNING",
        "pressure_risk": "NORMAL",
        "overall_risk": "WARNING",
        "risk_level": 1
      },
      {
        "minutes_ahead": 20,
        "forecasted_temperature": 86.3,
        "forecasted_pressure": 106.8,
        "forecast_timestamp": "2025-04-26T16:50:00.000Z",
        "temperature_risk": "DANGER",
        "pressure_risk": "WARNING",
        "overall_risk": "DANGER",
        "risk_level": 2
      },
      {
        "minutes_ahead": 25,
        "forecasted_temperature": 89.7,
        "forecasted_pressure": 108.2,
        "forecast_timestamp": "2025-04-26T16:55:00.000Z",
        "temperature_risk": "DANGER",
        "pressure_risk": "WARNING",
        "overall_risk": "DANGER",
        "risk_level": 2
      },
      {
        "minutes_ahead": 30,
        "forecasted_temperature": 92.4,
        "forecasted_pressure": 110.5,
        "forecast_timestamp": "2025-04-26T17:00:00.000Z",
        "temperature_risk": "DANGER",
        "pressure_risk": "DANGER",
        "overall_risk": "DANGER",
        "risk_level": 2
      }
    ],
    "risk_level": "DANGER",
    "generated_at": "2025-04-26T16:30:00.000Z",
    "config": {
      "temperature_warning_threshold": 80.0,
      "temperature_max_threshold": 85.0,
      "pressure_warning_threshold": 105.0,
      "pressure_max_threshold": 110.0
    }
  }
}


