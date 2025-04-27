- does the message broker needs to register itself to the resource calatlog ? 
- do i need to read the data from the influx db in order to do the analysis or i can directly read it from the timeseries db connector that is receiving the data from the raspberrypi connector via message broker
- is it realy necessary for the catalog to save the results of the ms analytics to it ? 
service_data = {
     ... existing registration data ...
    "provided_outputs": {
        "predictions": "Forecasted temperature and pressure values",
        "alerts": "Hazard notifications based on predictions",
        "latest_results": {  # Add this new field
            "forecast": latest_forecast,
            "risk_level": latest_risk_level,
            "last_analysis_time": last_analysis_time.isoformat() if last_analysis_time else None
        }
    },
     ... rest of registration data ...
}

