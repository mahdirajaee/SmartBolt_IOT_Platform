# Telegram Bot Service

A Telegram bot service that interfaces with the Smart Bolt system, allowing users to:
- Authenticate via account manager
- Retrieve latest temperature and pressure readings
- Send commands to actuators through the control center

## Requirements

- Python 3.7+
- Dependencies listed in `requirements.txt`

## Configuration

Edit `config.json` to set:
- Telegram bot token (obtain from BotFather)
- Service port
- Resource catalog URL
- Account manager URL
- MQTT broker settings

## Installation

1. Install dependencies:

```
pip install -r requirements.txt
```

2. Configure the bot token in `config.json`

## Usage

Start the service:

```
python main.py
```

## Telegram Bot Commands

- `/start` - Welcome message and basic help
- `/login username password` - Authenticate with the system
- `/logout` - End your session
- `/temperature` - Get latest temperature readings
- `/pressure` - Get latest pressure readings 
- `/actuator` - Access actuator controls

## API Endpoints

- `GET /` - Service status
- `GET /health` - Health check
- `POST /send_message` - Send message to a Telegram chat (requires chat_id and text in JSON body)

## Architecture

- Uses CherryPy as web server
- Registers with Resource Catalog
- Communicates with Control Center via MQTT
- Retrieves sensor data from Catalog via REST API
- Uses authentication via Account Manager 