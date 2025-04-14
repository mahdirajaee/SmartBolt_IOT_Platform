# Environment Configuration

This project now uses environment variables to configure the various microservices. The configuration is stored in a `.env` file in the root directory of the project. 

## Setting Up the Environment

1. Copy the `.env` file to create a custom configuration:
   ```bash
   cp .env .env.local
   ```

2. Edit the `.env.local` file to customize the configuration for your environment.

3. The system will load variables from `.env` by default, but you can override them by setting environment variables directly or using a different .env file.

## Configuration Parameters

### Resource Catalog Configuration
- `RESOURCE_CATALOG_PORT`: The port for the Resource Catalog service (default: 8080)
- `RESOURCE_CATALOG_HOST`: The host address for the Resource Catalog service (default: 0.0.0.0)
- `ENABLE_AUTH`: Whether to enable authentication for the Resource Catalog API (default: false)
- `API_USERNAME`: Username for API authentication if enabled (default: admin)
- `API_PASSWORD`: Password for API authentication if enabled (default: password)

### Message Broker Configuration
- `MQTT_PORT`: The port for the MQTT message broker (default: 1883)
- `MQTT_BROKER`: The host address for the MQTT message broker (default: localhost)

### TimeSeriesDB Connector Configuration
- `TIMESERIES_PORT`: The port for the TimeSeriesDB Connector service (default: 8081)
- `INFLUXDB_URL`: The URL for the InfluxDB database (default: http://localhost:8086)
- `INFLUXDB_TOKEN`: The authentication token for InfluxDB (default: mydevtoken123)
- `INFLUXDB_ORG`: The organization name in InfluxDB (default: smart_iot)
- `INFLUXDB_BUCKET`: The bucket name in InfluxDB for storing data (default: sensor_data)

### Control Center Configuration
- `CONTROL_CENTER_PORT`: The port for the Control Center service (default: 8083)
- `CONTROL_CENTER_HOST`: The host address for the Control Center service (default: 0.0.0.0)

### Account Manager Configuration
- `ACCOUNT_MANAGER_PORT`: The port for the Account Manager service (default: 8086)
- `JWT_SECRET`: The secret key used for JWT token generation (default: smart_iot_bolt_secret_key)

### Raspberry Pi Connector Configuration
- `RPI_CONNECTOR_PORT`: The port for the Raspberry Pi Connector service (default: 8090)

### Telegram Bot Configuration
- `TELEGRAM_BOT_PORT`: The port for the Telegram Bot service (default: 8085)
- `TELEGRAM_BOT_HOST`: The host address for the Telegram Bot service (default: localhost)
- `PTB_HTTPX_DISABLE_PROXIES`: Whether to disable proxies for the Telegram Bot (default: True)

### Analytics Service Configuration
- `ANALYTICS_PORT`: The port for the Analytics service (default: 8082)
- `ANALYTICS_HOST`: The host address for the Analytics service (default: 0.0.0.0)

### General Configuration
- `DEBUG`: Enable or disable debug mode (default: true)
- `CATALOG_URL`: The URL for the Resource Catalog service (default: http://localhost:8080)

## Security Considerations

1. For production environments, make sure to:
   - Change default passwords and secrets
   - Enable authentication
   - Use secure connections (HTTPS/TLS)
   - Store sensitive information in environment variables rather than in the .env file

2. Never commit sensitive credentials to version control. The `.env` file should be included in your `.gitignore` file.

## Using Custom Environment Files

You can specify a different environment file when running the services:

```bash
python3 -m dotenv.cli -f .env.production run python3 run_services.py
```

## Troubleshooting

If a service fails to start, check:
1. If the specified port is already in use
2. If the required environment variables are set correctly
3. If the dependent services are running (e.g., Resource Catalog must be running for other services) 