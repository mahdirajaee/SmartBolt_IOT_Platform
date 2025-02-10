import os
import logging
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Updater, CommandHandler, CallbackContext

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ANALYTICS_API_URL = os.getenv("ANALYTICS_API_URL")

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def start(update: Update, context: CallbackContext) -> None:
    """Send a welcome message when the user starts the bot."""
    update.message.reply_text(
        "Hello! I am the Smart Bolt Telegram Bot. "
        "I will notify you when sensor values exceed safe thresholds. "
        "Use /status to check current sensor data."
    )

def get_status(update: Update, context: CallbackContext) -> None:
    """Fetch sensor data from the Analytics service."""
    try:
        response = requests.get(ANALYTICS_API_URL)
        data = response.json()
        message = (
            f"📊 Sensor Status:\n"
            f"🌡 Temperature: {data['temperature']} °C\n"
            f"⚙️ Pressure: {data['pressure']} Pa\n"
            f"🔧 Valve Status: {data['valve']}"
        )
    except Exception as e:
        logger.error(f"Error fetching status: {e}")
        message = "❌ Failed to retrieve sensor data. Please try again later."

    update.message.reply_text(message)

def alert_users(alert_message: str):
    """Send alert messages to all subscribed users."""
    # This function should be called when an alert is triggered.
    # In a production system, you might store user IDs in a database.
    pass  # Implementation for user management can be added here

def main():
    """Start the Telegram bot."""
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Command handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("status", get_status))

    # Start polling
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
