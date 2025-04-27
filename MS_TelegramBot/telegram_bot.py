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
                f"{self.account_manager_url}/api/auth/login",
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
            "Welcome to the Smart Bolt Telegram Bot!\n\n"
            "Use /login username password to authenticate\n"
            "After login, you can use:\n"
            "/temperature - Get latest temperature\n"
            "/pressure - Get latest pressure\n"
            "/actuator - Control actuators"
        )
        update.message.reply_text(message)
    
    def handle_login(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        
        if len(context.args) != 2:
            update.message.reply_text("Usage: /login username password")
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
            update.message.reply_text(f"Login successful. Welcome, {username}!")
        else:
            update.message.reply_text("Login failed. Please check your credentials.")
    
    def handle_logout(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        
        if user_id in self.authenticated_users:
            del self.authenticated_users[user_id]
            update.message.reply_text("You have been logged out.")
        else:
            update.message.reply_text("You are not logged in.")
    
    def handle_temperature(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        
        if not self.is_authenticated(user_id):
            update.message.reply_text("You need to login first using /login username password")
            return
        
        temp_data = self.catalog_client.get_latest_sensor_data("temperature")
        
        if temp_data:
            message = f"Current temperature: {temp_data['value']} {temp_data['unit']}"
            if 'timestamp' in temp_data:
                message += f"\nTimestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(temp_data['timestamp']))}"
            update.message.reply_text(message)
        else:
            update.message.reply_text("Failed to retrieve temperature data.")
    
    def handle_pressure(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        
        if not self.is_authenticated(user_id):
            update.message.reply_text("You need to login first using /login username password")
            return
        
        pressure_data = self.catalog_client.get_latest_sensor_data("pressure")
        
        if pressure_data:
            message = f"Current pressure: {pressure_data['value']} {pressure_data['unit']}"
            if 'timestamp' in pressure_data:
                message += f"\nTimestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(pressure_data['timestamp']))}"
            update.message.reply_text(message)
        else:
            update.message.reply_text("Failed to retrieve pressure data.")
    
    def handle_actuator(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        
        if not self.is_authenticated(user_id):
            update.message.reply_text("You need to login first using /login username password")
            return
        
        keyboard = [
            [
                InlineKeyboardButton("Valve Open", callback_data="actuator:valve:open"),
                InlineKeyboardButton("Valve Close", callback_data="actuator:valve:close")
            ],
            [
                InlineKeyboardButton("Motor On", callback_data="actuator:motor:on"),
                InlineKeyboardButton("Motor Off", callback_data="actuator:motor:off")
            ]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("Select actuator command:", reply_markup=reply_markup)
    
    def handle_callback(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        query = update.callback_query
        
        if not self.is_authenticated(user_id):
            query.answer("You need to login first")
            return
        
        query.answer()
        
        try:
            data_parts = query.data.split(":")
            if len(data_parts) == 3 and data_parts[0] == "actuator":
                actuator_id = data_parts[1]
                command = data_parts[2]
                
                success = self.mqtt_client.send_command(actuator_id, command)
                
                if success:
                    query.edit_message_text(f"Command sent to {actuator_id}: {command}")
                else:
                    query.edit_message_text(f"Failed to send command to {actuator_id}")
            else:
                query.edit_message_text("Invalid callback data")
        except Exception as e:
            self.logger.error(f"Error handling callback: {str(e)}")
            query.edit_message_text("An error occurred while processing your request")
    
    def handle_message(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        
        if not self.is_authenticated(user_id):
            update.message.reply_text("You need to login first using /login username password")
            return
        
        update.message.reply_text(
            "Available commands:\n"
            "/temperature - Get latest temperature\n"
            "/pressure - Get latest pressure\n"
            "/actuator - Control actuators\n"
            "/logout - Log out"
        ) 