import json
import logging
import requests
import threading
import time
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Updater, CommandHandler, CallbackContext, 
    MessageHandler, Filters, CallbackQueryHandler
)

from catalog_client import CatalogClient
from mqtt_client import MQTTClient

class TelegramBot:
    def __init__(self, config_path="config.json"):
        with open(config_path, 'r') as f:
            self.config = json.load(f)
        
        self.token = self.config["telegram"]["bot_token"]
        self.account_manager_url = self.config["account_manager"]["url"]
        self.logger = logging.getLogger("telegram_bot")
        
        self.catalog_client = CatalogClient(config_path)
        self.mqtt_client = MQTTClient(config_path)
        
        self.authenticated_users = {}
        self.updater = None
        self.bot = None
    
    def start(self):
        self.mqtt_client.connect()
        self.catalog_client.register_service()
        
        self.updater = Updater(self.token)
        self.bot = self.updater.bot
        dispatcher = self.updater.dispatcher
        
        dispatcher.add_handler(CommandHandler("start", self.handle_start))
        dispatcher.add_handler(CommandHandler("help", self.handle_help))
        dispatcher.add_handler(CommandHandler("login", self.handle_login))
        dispatcher.add_handler(CommandHandler("logout", self.handle_logout))
        dispatcher.add_handler(CommandHandler("temperature", self.handle_temperature))
        dispatcher.add_handler(CommandHandler("pressure", self.handle_pressure))
        dispatcher.add_handler(CommandHandler("actuator", self.handle_actuator))
        dispatcher.add_handler(CallbackQueryHandler(self.handle_callback))
        
        dispatcher.add_handler(MessageHandler(
            Filters.text & ~Filters.command, 
            self.handle_message
        ))
        
        self.start_heartbeat()
        
        self.updater.start_polling()
        self.logger.info("Telegram bot started")
        
    def stop(self):
        if self.updater:
            self.updater.stop()
        self.mqtt_client.disconnect()
        self.logger.info("Telegram bot stopped")
    
    def start_heartbeat(self):
        def heartbeat_task():
            while True:
                self.catalog_client.update_service_status()
                time.sleep(60)
        
        heartbeat_thread = threading.Thread(target=heartbeat_task, daemon=True)
        heartbeat_thread.start()
    
    def is_authenticated(self, user_id):
        if user_id in self.authenticated_users:
            token_info = self.authenticated_users[user_id]
            if token_info["expires_at"] > time.time():
                return True
            else:
                del self.authenticated_users[user_id]
        return False
    
    def authenticate_user(self, username, password):
        try:
            response = requests.post(
                f"{self.account_manager_url}/login",
                json={"username": username, "password": password}
            )
            
            if response.status_code == 200:
                token_data = response.json()
                return token_data
            else:
                self.logger.error(f"Authentication failed: {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error during authentication: {str(e)}")
            return None
    
    def handle_start(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        message = (
            "🔧 *Welcome to Smart Bolt System*\n\n"
            "This bot helps you monitor and control your Smart Bolt system.\n\n"
            "📋 *Available Commands:*\n"
            "• /login - Login to your account\n"
            "• /help - Show this help message\n"
            "• /status - Check system status\n"
            "• /sensors - View sensor readings\n"
            "• /control - Control system actuators\n"
            "• /logout - Logout from the system\n\n"
            "🔐 *Authentication Required*\n"
            "Most commands require you to be logged in.\n"
            "Use /login username password to authenticate."
        )
        update.message.reply_text(message, parse_mode='Markdown')
    
    def handle_help(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        message = (
            "📚 *Smart Bolt System Help*\n\n"
            "🔐 *Authentication*\n"
            "• /login username password - Login to your account\n"
            "• /logout - Logout from the system\n\n"
            "📊 *Sensor Readings*\n"
            "• /temperature - Get latest temperature reading\n"
            "• /pressure - Get latest pressure reading\n\n"
            "🎛️ *Control*\n"
            "• /actuator - Control system actuators (valve and motor)\n\n"
            "ℹ️ *System Information*\n"
            "• /status - Check system status\n"
            "• /help - Show this help message\n\n"
            "🔒 *Note:* Most commands require authentication.\n"
            "Use /login to authenticate first."
        )
        update.message.reply_text(message, parse_mode='Markdown')
    
    def handle_login(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        
        if len(context.args) != 2:
            update.message.reply_text(
                "❌ *Invalid Login Format*\n\n"
                "Please use: /login username password\n"
                "Example: /login john password123",
                parse_mode='Markdown'
            )
            return
        
        username = context.args[0]
        password = context.args[1]
        
        token_data = self.authenticate_user(username, password)
        
        if token_data:
            self.authenticated_users[user_id] = {
                "token": token_data["token"],
                "expires_at": time.time() + token_data["expires_in"],
                "username": username
            }
            update.message.reply_text(
                f"✅ *Login Successful*\n\n"
                f"Welcome, {username}!\n"
                f"Your session will expire in {token_data['expires_in']//60} minutes.\n\n"
                "Use /help to see available commands.",
                parse_mode='Markdown'
            )
        else:
            update.message.reply_text(
                "❌ *Login Failed*\n\n"
                "Please check your credentials and try again.",
                parse_mode='Markdown'
            )
    
    def handle_logout(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        
        if user_id in self.authenticated_users:
            del self.authenticated_users[user_id]
            update.message.reply_text(
                "👋 *Logged Out Successfully*\n\n"
                "You have been logged out of the system.",
                parse_mode='Markdown'
            )
        else:
            update.message.reply_text(
                "ℹ️ *Not Logged In*\n\n"
                "You are not currently logged in.",
                parse_mode='Markdown'
            )
    
    def handle_temperature(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        
        if not self.is_authenticated(user_id):
            update.message.reply_text(
                "🔒 *Authentication Required*\n\n"
                "Please login first using /login username password",
                parse_mode='Markdown'
            )
            return
        
        temp_data = self.catalog_client.get_latest_sensor_data("temperature")
        
        if temp_data:
            message = (
                "🌡️ *Temperature Reading*\n\n"
                f"Current: *{temp_data['value']} {temp_data['unit']}*\n"
            )
            if 'timestamp' in temp_data:
                message += f"Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(temp_data['timestamp']))}"
            update.message.reply_text(message, parse_mode='Markdown')
        else:
            update.message.reply_text(
                "⚠️ *Data Unavailable*\n\n"
                "Could not retrieve temperature data at this time.",
                parse_mode='Markdown'
            )
    
    def handle_pressure(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        
        if not self.is_authenticated(user_id):
            update.message.reply_text(
                "🔒 *Authentication Required*\n\n"
                "Please login first using /login username password",
                parse_mode='Markdown'
            )
            return
        
        pressure_data = self.catalog_client.get_latest_sensor_data("pressure")
        
        if pressure_data:
            message = (
                "📊 *Pressure Reading*\n\n"
                f"Current: *{pressure_data['value']} {pressure_data['unit']}*\n"
            )
            if 'timestamp' in pressure_data:
                message += f"Time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(pressure_data['timestamp']))}"
            update.message.reply_text(message, parse_mode='Markdown')
        else:
            update.message.reply_text(
                "⚠️ *Data Unavailable*\n\n"
                "Could not retrieve pressure data at this time.",
                parse_mode='Markdown'
            )
    
    def handle_actuator(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        
        if not self.is_authenticated(user_id):
            update.message.reply_text(
                "🔒 *Authentication Required*\n\n"
                "Please login first using /login username password",
                parse_mode='Markdown'
            )
            return
        
        keyboard = [
            [
                InlineKeyboardButton("🔓 Valve Open", callback_data="actuator:valve:open"),
                InlineKeyboardButton("🔒 Valve Close", callback_data="actuator:valve:close")
            ],
            [
                InlineKeyboardButton("⚡ Motor On", callback_data="actuator:motor:on"),
                InlineKeyboardButton("⏹️ Motor Off", callback_data="actuator:motor:off")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(
            "🎛️ *Actuator Control*\n\n"
            "Select the action you want to perform:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    def handle_callback(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        query = update.callback_query
        
        if not self.is_authenticated(user_id):
            query.answer("🔒 Please login first")
            return
        
        query.answer()
        
        try:
            data_parts = query.data.split(":")
            if len(data_parts) == 3 and data_parts[0] == "actuator":
                actuator_id = data_parts[1]
                command = data_parts[2]
                
                success = self.mqtt_client.send_command(actuator_id, command)
                
                if success:
                    query.edit_message_text(
                        f"✅ *Command Sent*\n\n"
                        f"Actuator: *{actuator_id}*\n"
                        f"Action: *{command}*",
                        parse_mode='Markdown'
                    )
                else:
                    query.edit_message_text(
                        "❌ *Command Failed*\n\n"
                        f"Could not send command to {actuator_id}",
                        parse_mode='Markdown'
                    )
            else:
                query.edit_message_text(
                    "⚠️ *Invalid Command*\n\n"
                    "Please try again.",
                    parse_mode='Markdown'
                )
        except Exception as e:
            self.logger.error(f"Error handling callback: {str(e)}")
            query.edit_message_text(
                "❌ *Error*\n\n"
                "An error occurred while processing your request.",
                parse_mode='Markdown'
            )
    
    def handle_message(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        
        if not self.is_authenticated(user_id):
            update.message.reply_text(
                "🔒 *Authentication Required*\n\n"
                "Please login first using /login username password",
                parse_mode='Markdown'
            )
            return
        
        update.message.reply_text(
            "📋 *Available Commands*\n\n"
            "• /sensors - View sensor readings\n"
            "• /control - Control system actuators\n"
            "• /status - Check system status\n"
            "• /logout - Logout from the system\n\n"
            "Type /help for more information.",
            parse_mode='Markdown'
        ) 