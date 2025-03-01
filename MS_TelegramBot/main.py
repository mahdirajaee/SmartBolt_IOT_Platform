import os
import logging
import json
import requests
import asyncio
import threading
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters

# Load environment variables
load_dotenv()

# Bot configuration
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
RESOURCE_CATALOG_URL = os.getenv("RESOURCE_CATALOG_URL", "http://localhost:5000")
ANALYTICS_API_URL = os.getenv("ANALYTICS_API_URL", "http://localhost:8080/analytics")
CONTROL_CENTER_URL = os.getenv("CONTROL_CENTER_URL", "http://localhost:5002")
TIME_SERIES_DB_URL = os.getenv("TIME_SERIES_DB_URL", "http://localhost:5000/data")

# States for conversation handler
SELECTING_SECTOR, SELECTING_ACTION, WAITING_FOR_VALUE = range(3)

# Notification settings
NOTIFICATION_INTERVAL = int(os.getenv("NOTIFICATION_INTERVAL", "300"))  # 5 minutes by default

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Store for authorized users
authorized_users = set()
# Store for subscribed sectors by user
user_subscriptions = {}
# Store for sector data
sectors = []
# Initialize with default sectors if needed
default_sectors = [
    {"id": "sector1", "name": "Pipeline Sector 1"}, 
    {"id": "sector2", "name": "Pipeline Sector 2"}
]
# Alert thresholds
thresholds = {
    "temperature": float(os.getenv("THRESHOLD_TEMP", "28")),
    "pressure": float(os.getenv("THRESHOLD_PRESSURE", "250"))
}

# Cache for last notification time per user and alert type
notification_cache = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a welcome message when the user starts the bot."""
    user_id = update.effective_user.id
    authorized_users.add(user_id)
    
    await update.message.reply_text(
        f"Hello, {update.effective_user.first_name}! Welcome to the Smart IoT Bolt Monitoring Bot.\n\n"
        "This bot helps you monitor your pipeline sensors and receive alerts.\n\n"
        "Available commands:\n"
        "/status - Check current sensor data\n"
        "/sectors - View and select pipeline sectors\n"
        "/subscribe - Subscribe to alerts from specific sectors\n"
        "/control - Control pipeline actuators\n"
        "/settings - Configure notification settings\n"
        "/help - Show this help message"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help information."""
    await update.message.reply_text(
        "Smart IoT Bolt Monitoring Bot Commands:\n\n"
        "📊 *Monitoring Commands*\n"
        "/status - Check current sensor data\n"
        "/history - View historical data\n"
        "/alerts - View recent alerts\n\n"
        "🔧 *Control Commands*\n"
        "/sectors - View and select pipeline sectors\n"
        "/control - Control pipeline actuators\n\n"
        "⚙️ *Configuration Commands*\n"
        "/subscribe - Subscribe to alerts\n"
        "/settings - Configure notification settings\n\n"
        "/help - Show this help message",
        parse_mode="Markdown"
    )

async def fetch_sectors() -> list:
    """Fetch sectors from the Resource Catalog."""
    global sectors
    try:
        response = requests.get(f"{RESOURCE_CATALOG_URL}/sectors")
        if response.status_code == 200:
            fetched_sectors = response.json()
            if fetched_sectors:
                sectors = fetched_sectors
                return sectors
            else:
                # If no sectors returned, use defaults
                if not sectors:
                    sectors = default_sectors.copy()
                return sectors
        else:
            logger.error(f"Failed to fetch sectors: {response.status_code}")
            # Use default sectors if none are available
            if not sectors:
                sectors = default_sectors.copy()
            return sectors
    except Exception as e:
        logger.error(f"Error fetching sectors: {e}")
        # Use default sectors if none are available
        if not sectors:
            sectors = default_sectors.copy()
        return sectors

async def fetch_sensor_data(sector_id=None) -> dict:
    """Fetch sensor data from the Analytics service."""
    try:
        params = {"sector_id": sector_id} if sector_id else {}
        response = requests.get(ANALYTICS_API_URL, params=params)
        if response.status_code == 200:
            return response.json()
        else:
            logger.error(f"Failed to fetch sensor data: {response.status_code}")
            return {}
    except Exception as e:
        logger.error(f"Error fetching sensor data: {e}")
        return {}

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetch and display current sensor status."""
    user_id = update.effective_user.id
    
    # Check if user has a selected sector
    selected_sector = None
    if user_id in user_subscriptions and user_subscriptions[user_id]:
        selected_sector = user_subscriptions[user_id][0]  # Use first subscribed sector
    
    # Fetch sensor data
    data = await fetch_sensor_data(selected_sector)
    
    if not data:
        await update.message.reply_text(
            "❌ Failed to retrieve sensor data. Please try again later."
        )
        return
    
    # Format the sensor data message
    sector_name = selected_sector if selected_sector else "All Sectors"
    
    # Temperature and pressure status indicators
    temp_status = "🔴" if data.get("last_temperature", 0) > thresholds["temperature"] else "🟢"
    pressure_status = "🔴" if data.get("last_pressure", 0) > thresholds["pressure"] else "🟢"
    
    # Format response message
    message = (
        f"📊 *Sensor Status for {sector_name}*\n\n"
        f"🌡 Temperature: {temp_status} {data.get('last_temperature', 'N/A')} °C\n"
        f"⚙️ Pressure: {pressure_status} {data.get('last_pressure', 'N/A')} Pa\n\n"
        f"*Analytics Insights:*\n"
        f"- Temperature Trend: {data.get('rolling_avg_temp', 'N/A')} °C (avg)\n"
        f"- Pressure Trend: {data.get('rolling_avg_pressure', 'N/A')} Pa (avg)\n"
        f"- Temperature Severity: {data.get('severity_temp', 'N/A')}\n"
        f"- Pressure Severity: {data.get('severity_pressure', 'N/A')}\n"
        f"- Correlation: {data.get('correlation_temp_pressure', 'N/A')}\n\n"
        f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    # Create keyboard with refresh button
    keyboard = [
        [InlineKeyboardButton("Refresh Data", callback_data="refresh_status")],
        [InlineKeyboardButton("View History", callback_data="history")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        message,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def sectors_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display available sectors and let user select one."""
    # Fetch sectors
    global sectors
    sectors = await fetch_sectors()
    
    if not sectors:
        await update.message.reply_text(
            "❌ No sectors available or couldn't fetch sector data. Please try again later."
        )
        return ConversationHandler.END
    
    # Create keyboard with sector options
    keyboard = []
    for sector in sectors:
        keyboard.append([InlineKeyboardButton(sector["name"], callback_data=f"sector_{sector['id']}")])
    
    keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Please select a pipeline sector to monitor:",
        reply_markup=reply_markup
    )
    
    return SELECTING_SECTOR

async def sector_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the sector selection."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text("Sector selection cancelled.")
        return ConversationHandler.END
    
    # Extract sector ID from callback data
    sector_id = query.data.replace("sector_", "")
    user_id = update.effective_user.id
    
    # Store the selected sector for this user
    if user_id not in user_subscriptions:
        user_subscriptions[user_id] = []
    
    if sector_id not in user_subscriptions[user_id]:
        user_subscriptions[user_id].append(sector_id)
    
    # Get the sector name for display
    sector_name = next((s["name"] for s in sectors if s["id"] == sector_id), "Unknown Sector")
    
    await query.edit_message_text(f"You've selected: {sector_name}\n\nUse /status to check current sensor data for this sector.")
    
    return ConversationHandler.END

async def control_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Display control options for actuators."""
    # First, ensure user has selected a sector
    user_id = update.effective_user.id
    
    if user_id not in user_subscriptions or not user_subscriptions[user_id]:
        await update.message.reply_text(
            "You haven't selected any sector yet. Please use /sectors first to select a sector."
        )
        return ConversationHandler.END
    
    # Create keyboard with control options
    keyboard = [
        [InlineKeyboardButton("Open Valve", callback_data="open_valve")],
        [InlineKeyboardButton("Close Valve", callback_data="close_valve")],
        [InlineKeyboardButton("Emergency Shutdown", callback_data="emergency_shutdown")],
        [InlineKeyboardButton("Cancel", callback_data="cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Select an action to perform:",
        reply_markup=reply_markup
    )
    
    return SELECTING_ACTION

async def action_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the action selection for control."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text("Control operation cancelled.")
        return ConversationHandler.END
    
    action = query.data
    user_id = update.effective_user.id
    sector_id = user_subscriptions[user_id][0]  # Use first subscribed sector
    
    # For open/close valve, no need for additional input
    if action in ["open_valve", "close_valve", "emergency_shutdown"]:
        success = await send_control_command(sector_id, action)
        
        if success:
            action_text = {
                "open_valve": "opened the valve",
                "close_valve": "closed the valve",
                "emergency_shutdown": "initiated emergency shutdown"
            }.get(action, "performed action")
            
            await query.edit_message_text(f"✅ Successfully {action_text} for selected sector.")
        else:
            await query.edit_message_text("❌ Failed to perform control action. Please try again later.")
        
        return ConversationHandler.END
    
    return ConversationHandler.END

async def send_control_command(sector_id, action) -> bool:
    """Send control command to the Control Center."""
    try:
        payload = {
            "sector_id": sector_id,
            "action": action
        }
        response = requests.post(f"{CONTROL_CENTER_URL}/trigger_action", json=payload)
        
        if response.status_code == 200:
            return True
        else:
            logger.error(f"Failed to send control command: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"Error sending control command: {e}")
        return False

async def subscribe_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Let users subscribe to alerts from specific sectors."""
    # Fetch sectors
    global sectors
    sectors = await fetch_sectors()
    
    if not sectors:
        await update.message.reply_text(
            "❌ No sectors available or couldn't fetch sector data. Please try again later."
        )
        return
    
    user_id = update.effective_user.id
    subscribed_sectors = user_subscriptions.get(user_id, [])
    
    # Create keyboard with sector options and their subscription status
    keyboard = []
    for sector in sectors:
        status = "✅" if sector["id"] in subscribed_sectors else "❌"
        keyboard.append([
            InlineKeyboardButton(
                f"{status} {sector['name']}", 
                callback_data=f"subscribe_{sector['id']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("Done", callback_data="subscribe_done")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Select sectors to subscribe for alerts:\n"
        "✅ = Subscribed\n"
        "❌ = Not subscribed",
        reply_markup=reply_markup
    )

async def subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle subscription callbacks."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "subscribe_done":
        user_id = update.effective_user.id
        subscribed_count = len(user_subscriptions.get(user_id, []))
        
        if subscribed_count > 0:
            await query.edit_message_text(f"You are now subscribed to {subscribed_count} sectors.")
        else:
            await query.edit_message_text("You are not subscribed to any sectors.")
        return
    
    # Extract sector ID from callback data
    sector_id = query.data.replace("subscribe_", "")
    user_id = update.effective_user.id
    
    # Initialize user subscriptions if needed
    if user_id not in user_subscriptions:
        user_subscriptions[user_id] = []
    
    # Toggle subscription status
    if sector_id in user_subscriptions[user_id]:
        user_subscriptions[user_id].remove(sector_id)
        subscribed = False
    else:
        user_subscriptions[user_id].append(sector_id)
        subscribed = True
    
    # Update keyboard to reflect new status
    keyboard = []
    for sector in sectors:
        status = "✅" if sector["id"] in user_subscriptions[user_id] else "❌"
        keyboard.append([
            InlineKeyboardButton(
                f"{status} {sector['name']}", 
                callback_data=f"subscribe_{sector['id']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("Done", callback_data="subscribe_done")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Get the sector name for the message
    sector_name = next((s["name"] for s in sectors if s["id"] == sector_id), "Unknown Sector")
    status_text = "Subscribed to" if subscribed else "Unsubscribed from"
    
    await query.edit_message_text(
        f"{status_text} {sector_name}\n\n"
        "Select sectors to subscribe for alerts:\n"
        "✅ = Subscribed\n"
        "❌ = Not subscribed",
        reply_markup=reply_markup
    )

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display and allow changes to notification settings."""
    # Create keyboard with notification settings
    keyboard = [
        [InlineKeyboardButton("Alert Thresholds", callback_data="settings_thresholds")],
        [InlineKeyboardButton("Notification Frequency", callback_data="settings_frequency")],
        [InlineKeyboardButton("Cancel", callback_data="settings_cancel")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "Notification Settings:\n\n"
        f"🌡 Temperature Threshold: {thresholds['temperature']} °C\n"
        f"⚙️ Pressure Threshold: {thresholds['pressure']} Pa\n"
        f"⏱ Notification Interval: {NOTIFICATION_INTERVAL} seconds\n\n"
        "Select a setting to modify:",
        reply_markup=reply_markup
    )

async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle settings callbacks."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "settings_cancel":
        await query.edit_message_text("Settings unchanged.")
        return
    
    # Handle different settings options
    if query.data == "settings_thresholds":
        keyboard = [
            [InlineKeyboardButton("Temperature Threshold", callback_data="threshold_temp")],
            [InlineKeyboardButton("Pressure Threshold", callback_data="threshold_pressure")],
            [InlineKeyboardButton("Back", callback_data="settings_back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Select a threshold to modify:",
            reply_markup=reply_markup
        )
    
    elif query.data == "settings_frequency":
        keyboard = [
            [InlineKeyboardButton("Real-time (5 min)", callback_data="freq_300")],
            [InlineKeyboardButton("Hourly", callback_data="freq_3600")],
            [InlineKeyboardButton("Daily", callback_data="freq_86400")],
            [InlineKeyboardButton("Back", callback_data="settings_back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Select notification frequency:",
            reply_markup=reply_markup
        )
    
    elif query.data.startswith("freq_"):
        # Extract frequency value
        global NOTIFICATION_INTERVAL
        NOTIFICATION_INTERVAL = int(query.data.replace("freq_", ""))
        
        # Format interval text
        if NOTIFICATION_INTERVAL < 3600:
            interval_text = f"{NOTIFICATION_INTERVAL // 60} minutes"
        elif NOTIFICATION_INTERVAL < 86400:
            interval_text = f"{NOTIFICATION_INTERVAL // 3600} hours"
        else:
            interval_text = f"{NOTIFICATION_INTERVAL // 86400} days"
        
        await query.edit_message_text(f"Notification frequency set to: {interval_text}")
    
    elif query.data == "settings_back":
        # Go back to main settings menu
        keyboard = [
            [InlineKeyboardButton("Alert Thresholds", callback_data="settings_thresholds")],
            [InlineKeyboardButton("Notification Frequency", callback_data="settings_frequency")],
            [InlineKeyboardButton("Cancel", callback_data="settings_cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "Notification Settings:\n\n"
            f"🌡 Temperature Threshold: {thresholds['temperature']} °C\n"
            f"⚙️ Pressure Threshold: {thresholds['pressure']} Pa\n"
            f"⏱ Notification Interval: {NOTIFICATION_INTERVAL} seconds\n\n"
            "Select a setting to modify:",
            reply_markup=reply_markup
        )
    
    elif query.data.startswith("threshold_"):
        # Prompt the user to enter a new threshold value
        threshold_type = query.data.replace("threshold_", "")
        context.user_data["threshold_type"] = threshold_type
        
        await query.edit_message_text(
            f"Please enter a new value for the {threshold_type} threshold:"
        )
        return  # Wait for text input

async def threshold_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle threshold value input."""
    threshold_type = context.user_data.get("threshold_type")
    if not threshold_type:
        await update.message.reply_text("Please start the threshold setting process again.")
        return
    
    try:
        value = float(update.message.text)
        if value <= 0:
            raise ValueError("Threshold must be positive")
        
        # Update the threshold
        thresholds[threshold_type] = value
        
        await update.message.reply_text(
            f"✅ {threshold_type.title()} threshold updated to: {value}"
        )
    except ValueError:
        await update.message.reply_text(
            "❌ Please enter a valid positive number."
        )

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetch and display historical sensor data."""
    user_id = update.effective_user.id
    
    # Check if user has a selected sector
    if user_id not in user_subscriptions or not user_subscriptions[user_id]:
        await update.message.reply_text(
            "You haven't selected any sector yet. Please use /sectors first to select a sector."
        )
        return
    
    sector_id = user_subscriptions[user_id][0]
    
    try:
        # Fetch historical data from Time Series DB
        response = requests.get(
            f"{TIME_SERIES_DB_URL}",
            params={"sensor": sector_id, "limit": 5}
        )
        
        if response.status_code != 200:
            await update.message.reply_text(
                "❌ Failed to retrieve historical data. Please try again later."
            )
            return
        
        data = response.json()
        
        if not data:
            await update.message.reply_text(
                "No historical data available for the selected sector."
            )
            return
        
        # Format the historical data
        message = "📈 *Historical Sensor Data*\n\n"
        
        for entry in data:
            timestamp = datetime.fromisoformat(entry["time"].replace("Z", "+00:00"))
            temp = entry.get("temperature", "N/A")
            pressure = entry.get("pressure", "N/A")
            
            message += (
                f"*{timestamp.strftime('%Y-%m-%d %H:%M')}*\n"
                f"🌡 Temperature: {temp} °C\n"
                f"⚙️ Pressure: {pressure} Pa\n\n"
            )
        
        await update.message.reply_text(
            message,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Error fetching historical data: {e}")
        await update.message.reply_text(
            "❌ An error occurred while retrieving historical data. Please try again later."
        )

async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Display recent alerts for the user's subscribed sectors."""
    user_id = update.effective_user.id
    
    # Check if user has any subscribed sectors
    if user_id not in user_subscriptions or not user_subscriptions[user_id]:
        await update.message.reply_text(
            "You haven't subscribed to any sectors. Please use /subscribe to subscribe to sectors."
        )
        return
    
    # In a real implementation, you would fetch actual alerts from a database
    # Here we'll simulate with some mock data
    mock_alerts = [
        {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "Temperature",
            "value": 35.2,
            "sector_id": user_subscriptions[user_id][0],
            "severity": "Critical"
        },
        {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "type": "Pressure",
            "value": 280.5,
            "sector_id": user_subscriptions[user_id][0],
            "severity": "Warning"
        }
    ]
    
    # Format alert message
    message = "⚠️ *Recent Alerts*\n\n"
    
    for alert in mock_alerts:
        severity_icon = "🔴" if alert["severity"] == "Critical" else "🟠"
        
        message += (
            f"{severity_icon} *{alert['severity']} {alert['type']} Alert*\n"
            f"Value: {alert['value']}\n"
            f"Time: {alert['timestamp']}\n\n"
        )
    
    # Add action buttons
    keyboard = [
        [InlineKeyboardButton("Acknowledge All", callback_data="ack_all")],
        [InlineKeyboardButton("View Status", callback_data="refresh_status")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        message,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle button callbacks."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "refresh_status":
        # Get user and their selected sector
        user_id = update.effective_user.id
        selected_sector = None
        if user_id in user_subscriptions and user_subscriptions[user_id]:
            selected_sector = user_subscriptions[user_id][0]
        
        # Fetch updated sensor data
        data = await fetch_sensor_data(selected_sector)
        
        if not data:
            await query.edit_message_text(
                "❌ Failed to retrieve sensor data. Please try again later."
            )
            return
        
        # Format the updated message
        sector_name = selected_sector if selected_sector else "All Sectors"
        
        # Temperature and pressure status indicators
        temp_status = "🔴" if data.get("last_temperature", 0) > thresholds["temperature"] else "🟢"
        pressure_status = "🔴" if data.get("last_pressure", 0) > thresholds["pressure"] else "🟢"
        
        message = (
            f"📊 *Sensor Status for {sector_name}*\n\n"
            f"🌡 Temperature: {temp_status} {data.get('last_temperature', 'N/A')} °C\n"
            f"⚙️ Pressure: {pressure_status} {data.get('last_pressure', 'N/A')} Pa\n\n"
            f"*Analytics Insights:*\n"
            f"- Temperature Trend: {data.get('rolling_avg_temp', 'N/A')} °C (avg)\n"
            f"- Pressure Trend: {data.get('rolling_avg_pressure', 'N/A')} Pa (avg)\n"
            f"- Temperature Severity: {data.get('severity_temp', 'N/A')}\n"
            f"- Pressure Severity: {data.get('severity_pressure', 'N/A')}\n"
            f"- Correlation: {data.get('correlation_temp_pressure', 'N/A')}\n\n"
            f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # Create keyboard with refresh button
        keyboard = [
            [InlineKeyboardButton("Refresh Data", callback_data="refresh_status")],
            [InlineKeyboardButton("View History", callback_data="history")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    
    elif query.data == "history":
        await query.edit_message_text("Fetching historical data...")
        await history_command(update, context)
    
    elif query.data == "ack_all":
        await query.edit_message_text("All alerts have been acknowledged.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    # Extract the update and error info
    if update and isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "An error occurred while processing your request. Please try again later."
        )

async def check_sensor_status():
    """Utility function to check sensor status - can be called from anywhere."""
    results = {}
    
    for sector in sectors:
        sector_id = sector["id"]
        data = await fetch_sensor_data(sector_id)
        if data:
            results[sector_id] = {
                "name": sector["name"],
                "temperature": data.get("last_temperature"),
                "pressure": data.get("last_pressure"),
                "status": "ok" if (data.get("last_temperature", 0) <= thresholds["temperature"] and 
                                  data.get("last_pressure", 0) <= thresholds["pressure"]) else "alert"
            }
    
    return results

def run_alert_checker(app):
    """Run the alert checker in the background."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def send_alert(user_id, message):
        """Send an alert message to a user."""
        await app.bot.send_message(chat_id=user_id, text=message, parse_mode="Markdown")
    
    async def check_and_notify():
        """Check for alerts and notify users."""
        while True:
            try:
                for user_id, subscribed_sectors in user_subscriptions.items():
                    for sector_id in subscribed_sectors:
                        # Fetch sensor data for this sector
                        data = await fetch_sensor_data(sector_id)
                        
                        if not data:
                            continue
                        
                        # Get sector name
                        sector_name = next((s["name"] for s in sectors if s["id"] == sector_id), f"Sector {sector_id}")
                        
                        # Check for threshold violations
                        temp = data.get("last_temperature")
                        pressure = data.get("last_pressure")
                        
                        if temp and temp > thresholds["temperature"]:
                            # Check if we should notify (based on notification interval)
                            current_time = datetime.now()
                            cache_key = f"{user_id}_{sector_id}_temp"
                            
                            if (cache_key not in notification_cache or
                                (current_time - notification_cache[cache_key]).total_seconds() >= NOTIFICATION_INTERVAL):
                                
                                # Format alert message
                                message = (
                                    f"🚨 *TEMPERATURE ALERT* 🚨\n\n"
                                    f"Sector: *{sector_name}*\n"
                                    f"Temperature: *{temp}°C* (Threshold: {thresholds['temperature']}°C)\n"
                                    f"Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                                    f"Please check the system status immediately."
                                )
                                
                                # Send notification
                                notification_cache[cache_key] = current_time
                                await send_alert(user_id, message)
                        
                        if pressure and pressure > thresholds["pressure"]:
                            # Similar logic for pressure alerts
                            current_time = datetime.now()
                            cache_key = f"{user_id}_{sector_id}_pressure"
                            
                            if (cache_key not in notification_cache or
                                (current_time - notification_cache[cache_key]).total_seconds() >= NOTIFICATION_INTERVAL):
                                
                                # Format alert message
                                message = (
                                    f"🚨 *PRESSURE ALERT* 🚨\n\n"
                                    f"Sector: *{sector_name}*\n"
                                    f"Pressure: *{pressure}Pa* (Threshold: {thresholds['pressure']}Pa)\n"
                                    f"Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                                    f"Please check the system status immediately."
                                )
                                
                                # Send notification
                                notification_cache[cache_key] = current_time
                                await send_alert(user_id, message)
            except Exception as e:
                logger.error(f"Error in alert checker: {e}")
            
            # Sleep for a while before checking again
            await asyncio.sleep(60)  # Check every minute
    
    # Create task for alerts
    loop.create_task(check_and_notify())
    loop.run_forever()