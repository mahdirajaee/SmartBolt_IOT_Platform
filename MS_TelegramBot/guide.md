# Guide to Interacting with IOT_SmartBolt Telegram Bot

## Finding Your Bot
1. Open the Telegram app
2. In the search bar, type `@iotSmartBoltbot`
3. Select the bot from search results
4. Send `/start` to begin interaction

## Available Commands

| Command | Description | Example |
|---------|-------------|---------|
| `/start` | Initialize the bot | `/start` |
| `/help` | Display available commands | `/help` |
| `/login` | Authenticate to access control functions | `/login username password` |
| `/status` | Check current pipeline status | `/status` |
| `/sectors` | List available pipeline sectors | `/sectors` |
| `/valve` | Control valve (authentication required) | `/valve sector_id device_id open` |

## Authentication Process
1. Send: `/login username password`
2. Upon successful authentication, you'll receive confirmation
3. Authentication expires after 1 hour

## Command Examples

### Basic Commands
```
/start
> Welcome to the Smart IoT Bolt Pipeline Monitoring Bot!
> 
> Use /help to see available commands.
> Use /login to authenticate and access control features.

/help
> Available commands:
> 
> /start - Start the bot
> /help - Show this help message
> /login username password - Authenticate to access control functions
> /status - Get current pipeline status
> /sectors - List available pipeline sectors
> /valve sector_id device_id open|close - Control a valve (requires authentication)
```

### Checking Pipeline Status
```
/status
> Pipeline Status:
> 
> Sector 1:
>   Device valve_001:
>     Temperature: 24.5 °C
>     Pressure: 3.2 bar
> 
> Sector 2:
>   Device valve_002:
>     Temperature: 26.1 °C
>     Pressure: 2.9 bar
>     Alerts:
>       - Pressure below threshold
```

### Controlling Valves (After Authentication)
```
/login admin password123
> Authentication successful! You can now use control functions.

/valve 1 valve_001 open
> Valve command 'open' sent successfully to device valve_001 in sector 1.
```

## API Interaction (For Developers)

Base URL: `https://api.telegram.org/bot7947622045:AAFK_tTgadra46gYYQ61ISt9SQMbxoMjWrI/`

### Send Message Example
```bash
curl -X POST "https://api.telegram.org/bot7947622045:AAFK_tTgadra46gYYQ61ISt9SQMbxoMjWrI/sendMessage" \
  -d "chat_id=YOUR_CHAT_ID&text=Test message"
```

### Get Bot Updates
```bash
curl "https://api.telegram.org/bot7947622045:AAFK_tTgadra46gYYQ61ISt9SQMbxoMjWrI/getUpdates"
```

For more API methods, see the [Telegram Bot API documentation](https://core.telegram.org/bots/api).
