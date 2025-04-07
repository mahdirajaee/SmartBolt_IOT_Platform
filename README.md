# Smart IoT Platform

A comprehensive microservices-based IoT platform for monitoring and controlling smart devices.

## System Requirements

- Python 3.8+
- InfluxDB 2.x (time-series database)
- Mosquitto MQTT Broker (or any MQTT broker)

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <repository-url>
cd <repository-directory>
```

### 2. Install Dependencies

Install all required Python packages:

```bash
pip install -r requirements.txt
```

### 3. Set Up InfluxDB

1. Install InfluxDB:
   - Download from [InfluxData](https://portal.influxdata.com/downloads/)
   - Or using Homebrew: `brew install influxdb`

2. Start InfluxDB:
   ```bash
   influxd
   ```

3. Access the InfluxDB UI at http://localhost:8086
   - Create an initial user, organization, and bucket
   - Recommended organization name: `smart_iot`
   - Recommended bucket name: `sensor_data`
   - Generate an API token for your application

4. Update the environment variables in `run_services.py` with your InfluxDB token

### 4. Set Up MQTT Broker

1. Install Mosquitto:
   - Download from [Mosquitto](https://mosquitto.org/download/)
   - Or using Homebrew: `brew install mosquitto`

2. Start Mosquitto:
   ```bash
   mosquitto -c mosquitto.conf
   ```

### 5. Start the Platform

Run all microservices using the launcher script:

```bash
python run_services.py
```

This will:
- Check and install required dependencies
- Start InfluxDB if not running
- Start all microservices in separate terminal windows

## Microservices

The platform consists of the following microservices:

1. **Resource Catalog** (port 8080)
   - Central registry for all services and devices

2. **Message Broker** (port 1883)
   - MQTT broker for communication between services

3. **TimeSeriesDB Connector** (port 8081)
   - Stores sensor data in InfluxDB
   - Provides API for data retrieval

4. **Control Center** (port 8083)
   - Manages device control commands

5. **Account Manager** (port 8086)
   - Handles user authentication and management

6. **Raspberry Pi Connector** (port 8090)
   - Interface for Raspberry Pi devices

7. **Telegram Bot** (port 8085)
   - Notification service via Telegram

8. **Analytics Service** (port 8082)
   - Data analysis and anomaly detection

9. **Web Dashboard**
   - Static web interface for monitoring

## Environment Variables

Each service uses environment variables for configuration. See `run_services.py` for details.

## Troubleshooting

- If a service fails to start, check the log output in its terminal window
- Ensure InfluxDB and MQTT broker are running
- Verify that all required ports are available
- Check environment variables are correctly set
