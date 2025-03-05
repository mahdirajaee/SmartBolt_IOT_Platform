# SmartBolt_IOT_Platform

🚀 An advanced IoT platform for real-time monitoring and control of industrial pipelines using Smart IoT Bolts.

## Overview

SmartBolt_IOT_Platform is a comprehensive microservices-based IoT system designed for industrial pipeline monitoring, predictive maintenance, and control. The platform uses sensor-equipped Smart IoT Bolts to collect pressure and temperature data from pipelines, enabling real-time monitoring and automated control to prevent failures and support predictive maintenance strategies.

## Key Features

✅ **Smart IoT Bolts** - Specialized bolts equipped with pressure and temperature sensors for pipeline monitoring
✅ **Real-time Monitoring** - MQTT-based communication for transmitting sensor data and actuator commands
✅ **Predictive Analytics** - Uses historical data and ARIMA models to predict potential issues before they become critical
✅ **Microservices Architecture** - Modular, decoupled design ensuring scalability and flexibility
✅ **Time-Series Database** - InfluxDB storage for efficient management of high-frequency sensor readings
✅ **Automated Valve Control** - Smart logic to trigger actuators based on sensor thresholds
✅ **Web Dashboard** - Interactive UI for visualizing pipeline data and controlling actuators
✅ **Telegram Bot Integration** - Real-time alerts and remote control capabilities
✅ **Secure Authentication** - Account management with role-based access control

## Architecture

The system follows a microservices architecture with the following components:

### Core Microservices

| Service | Description |
|---------|-------------|
| **Message Broker** | Facilitates MQTT communication between components using topics for temperature, pressure, and valve actuation |
| **Raspberry Pi Connector** | Simulates Smart IoT Bolts with sensors and actuators, publishing data and responding to commands |
| **Time Series DB Connector** | Interfaces between MQTT data streams and InfluxDB for efficient time-series storage |
| **Analytics Microservice** | Processes sensor data to detect anomalies, predict failures, and trigger preventive actions |
| **Web Dashboard** | Provides UI for monitoring pipeline sectors, sensor status, and historical data visualization |
| **Control Center** | Orchestrates system operations, monitoring service health and coordinating responses |
| **Telegram Bot** | Delivers alerts on anomalies and processes user commands for system monitoring and control |
| **Account Manager** | Handles user authentication and authorization for secure access to the platform |
| **Resource/Service Catalog** | Maintains registry of all services with their endpoints for service discovery |

### Sensor and Actuator Components

- **Pressure Sensor**: Monitors pipeline pressure at bolt locations
- **Temperature Sensor**: Tracks temperature variations at different pipeline points
- **Valve Actuator**: Controls flow based on sensor data and analytics recommendations

## Pipeline & Smart Bolt Architecture

- Each pipeline (sector) can have up to 4 Smart IoT Bolts installed at different positions
- Bolts are sequentially numbered for structured monitoring
- Multiple bolts on a pipeline improve decision-making accuracy and failure prevention
- Each bolt has unique identification linked to its specific pipeline

## Technology Stack

- **Backend**: Python with CherryPy for REST APIs
- **Communication**: MQTT (Mosquitto) for real-time data exchange
- **Database**: InfluxDB for time-series data storage
- **Frontend**: HTML/JavaScript Web Dashboard
- **Notifications**: Telegram Bot API
- **DevOps**: Docker for containerization

## Installation & Setup

1. **Clone the Repository**
```bash
git clone https://github.com/mahdirajaee/SmartBolt_IOT_Platform.git
cd SmartBolt_IOT_Platform
```

2. **Set Up Environment Variables**
Create configuration files or environment variables for:
- MQTT broker connection
- InfluxDB credentials
- Telegram bot token
- Service ports and endpoints

3. **Run Services**
Start individual microservices:
```bash
# Start each microservice
python MS_ResourceCatalog/app.py
python MS_AccountManager/app.py
python MS_Analytics/app.py
python MS_ControlCenter/app.py
python MS_TelegramBot/app.py
python MS_TimeSeriesDbConnector/app.py
python MS_WebDashboard/app.py
python "RaspberryPy Connector v.2"/app.py
```

Or use Docker for containerized deployment:
```bash
docker-compose up --build
```

## API Endpoints

Each microservice exposes RESTful APIs:

- **Resource Catalog**
  - `GET /services` - Retrieve available services
  - `POST /services` - Register a new service

- **Time Series DB Connector**
  - `GET /data/{pipeline_id}/{device_id}` - Retrieve sensor readings
  - `GET /data/history` - Fetch historical data

- **Analytics**
  - `GET /analytics/{pipeline_id}` - Get processed insights
  - `POST /prediction` - Generate predictive analysis

- **Control Center**
  - `POST /actuator/{valve_id}` - Control valve operations
  - `GET /system/status` - System health overview

## MQTT Topics

- `/sensor/temperature` - Real-time temperature readings
- `/sensor/pressure` - Real-time pressure readings
- `/actuator/valve` - Commands for valve operation

## Team
- Mahdi Rajaee 
- Mohammad Eftekhari pour 
- Tanin heidarloui moghaddam
- Hamid Shabanipour 

## Contributing

🚀 Contributions are welcome! Feel free to fork the repository, create a new branch, and submit a pull request.

## License

📜 This project is licensed under the Apache-2.0 license
