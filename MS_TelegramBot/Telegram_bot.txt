import sys
import os

# Add the current directory to the Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Import bot configuration before importing telegram libraries
# This sets environment variables needed for compatibility
import bot_config

import time
import json
import asyncio
import threading
import requests
import cherrypy
import socket
from dotenv import load_dotenv

# Load environment variables from .env file in the current directory
load_dotenv(os.path.join(current_dir, '.env'))

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

class TelegramBotService:
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.bot_token:
            cherrypy.log("Warning: TELEGRAM_BOT_TOKEN not found in environment variables")
            self.bot_token = "YOUR_BOT_TOKEN_HERE"  # Placeholder - service will start but bot won't work
            
        self.catalog_url = os.getenv("RESOURCE_CATALOG_URL", "http://localhost:8080")
        self.service_id = "telegram_bot"
        self.service_port = self.find_available_port()
        self.service_host = os.getenv("SERVICE_HOST", "localhost")
        self.service_address = f"http://{self.service_host}:{self.service_port}"
        
        self.endpoints = {}
        self.authenticated_users = {}
        self.active_chat_ids = set()
        
        # Record start time
        self.start_time = time.time()
        
        # Use a more compatible configuration for ApplicationBuilder
        try:
            # Attempt to build the application with a simplified configuration
            self.bot_application = (
                ApplicationBuilder()
                .token(self.bot_token)
                # Skip proxy settings which are causing issues
                .concurrent_updates(True)
                .build()
            )
            
            self.bot_application.add_handler(CommandHandler("start", self.start_command))
            self.bot_application.add_handler(CommandHandler("help", self.help_command))
            self.bot_application.add_handler(CommandHandler("status", self.status_command))
            self.bot_application.add_handler(CommandHandler("login", self.login_command))
            self.bot_application.add_handler(CommandHandler("valve", self.valve_command))
            self.bot_application.add_handler(CommandHandler("sectors", self.list_sectors_command))
            self.bot_application.add_handler(CallbackQueryHandler(self.handle_callback))
            
            self.bot_thread = threading.Thread(target=self.run_bot)
            self.bot_thread.daemon = True
            self.bot_thread.start()
        except Exception as e:
            cherrypy.log(f"Error initializing Telegram bot: {str(e)}")
            cherrypy.log("Telegram bot functionality will be disabled")
            self.bot_application = None
    
    def find_available_port(self):
        preferred_port = int(os.getenv("SERVICE_PORT", 8085))
        
        if self.is_port_available(preferred_port):
            return preferred_port
            
        cherrypy.log(f"Port {preferred_port} is not available, searching for alternative...")
        
        for port in range(8000, 9000):
            if port != preferred_port and self.is_port_available(port):
                cherrypy.log(f"Using alternative port: {port}")
                return port
                
        raise RuntimeError("No available ports found")
    
    def is_port_available(self, port):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            return result != 0
        except:
            return False
    
    def run_bot(self):
        if self.bot_application:
            try:
                self.bot_application.run_polling()
            except Exception as e:
                cherrypy.log(f"Error running Telegram bot: {str(e)}")
        else:
            cherrypy.log("Bot application not initialized, skipping run_polling")
    
    def register_with_catalog(self):
        service_info = {
            "name": self.service_id,
            "endpoint": self.service_address,
            "port": self.service_port,
            "additional_info": {
                "description": "Telegram Bot Service for notifications and control",
                "commands": ["/start", "/help", "/login", "/status", "/sectors", "/valve"],
                "notification_endpoint": f"{self.service_address}/send_notification"
            }
        }
        
        try:
            response = requests.post(f"{self.catalog_url}/service", json=service_info)
            if response.status_code in (200, 201):
                cherrypy.log("Successfully registered with the Resource Catalog")
                return True
            else:
                cherrypy.log(f"Failed to register with catalog: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            cherrypy.log(f"Error registering with catalog: {str(e)}")
            return False
    
    def update_service_status(self):
        status_update = {
            "status": "active",
            "last_update": int(time.time())
        }
        
        try:
            response = requests.put(f"{self.catalog_url}/services/{self.service_id}", json=status_update)
            return response.status_code in (200, 204)
        except Exception:
            return False
    
    def discover_services(self):
        try:
            response = requests.get(f"{self.catalog_url}/services")
            if response.status_code == 200:
                services = response.json()
                
                for service in services:
                    if service["id"] == "analytics":
                        self.endpoints["analytics"] = service["endpoint"]
                    elif service["id"] == "account_manager":
                        self.endpoints["account_manager"] = service["endpoint"]
                    elif service["id"] == "control_center":
                        self.endpoints["control_center"] = service["endpoint"]
                
                cherrypy.log(f"Discovered services: {self.endpoints}")
                return True
            return False
        except Exception as e:
            cherrypy.log(f"Error discovering services: {str(e)}")
            return False
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.active_chat_ids.add(update.effective_chat.id)
        
        await update.message.reply_text(
            "Welcome to the Smart IoT Bolt Pipeline Monitoring Bot!\n\n"
            "Use /help to see available commands.\n"
            "Use /login to authenticate and access control features."
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.active_chat_ids.add(update.effective_chat.id)
        
        help_text = (
            "Available commands:\n\n"
            "/start - Start the bot\n"
            "/help - Show this help message\n"
            "/login username password - Authenticate to access control functions\n"
            "/status - Get current pipeline status\n"
            "/sectors - List available pipeline sectors\n"
            "/valve sector_id device_id open|close - Control a valve (requires authentication)"
        )
        await update.message.reply_text(help_text)
    
    async def login_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.active_chat_ids.add(update.effective_chat.id)
        
        if len(context.args) != 2:
            await update.message.reply_text("Usage: /login username password")
            return
        
        username = context.args[0]
        password = context.args[1]
        
        if "account_manager" not in self.endpoints:
            await update.message.reply_text("Authentication service is not available. Please try again later.")
            return
        
        try:
            response = requests.post(
                f"{self.endpoints['account_manager']}/auth/login",
                json={"username": username, "password": password}
            )
            
            if response.status_code == 200:
                auth_data = response.json()
                user_id = update.effective_user.id
                self.authenticated_users[user_id] = {
                    "token": auth_data.get("token"),
                    "expires": time.time() + auth_data.get("expires_in", 3600)
                }
                await update.message.reply_text("Authentication successful! You can now use control functions.")
            else:
                await update.message.reply_text("Authentication failed. Please check your credentials.")
        except Exception as e:
            await update.message.reply_text(f"Error during authentication: {str(e)}")
    
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.active_chat_ids.add(update.effective_chat.id)
        
        if "analytics" not in self.endpoints:
            await update.message.reply_text("Analytics service is not available. Please try again later.")
            return
        
        try:
            response = requests.get(f"{self.endpoints['analytics']}/status")
            if response.status_code == 200:
                status_data = response.json()
                
                status_text = "Pipeline Status:\n\n"
                
                for sector_id, sector_data in status_data.items():
                    status_text += f"Sector {sector_id}:\n"
                    
                    for device_id, device_data in sector_data.items():
                        status_text += f"  Device {device_id}:\n"
                        status_text += f"    Temperature: {device_data.get('temperature', 'N/A')} °C\n"
                        status_text += f"    Pressure: {device_data.get('pressure', 'N/A')} bar\n"
                        
                        if device_data.get("alerts"):
                            status_text += "    Alerts:\n"
                            for alert in device_data["alerts"]:
                                status_text += f"      - {alert}\n"
                    
                    status_text += "\n"
                
                await update.message.reply_text(status_text)
            else:
                await update.message.reply_text("Failed to retrieve pipeline status. Please try again later.")
        except Exception as e:
            await update.message.reply_text(f"Error retrieving status: {str(e)}")
    
    async def list_sectors_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.active_chat_ids.add(update.effective_chat.id)
        
        if "analytics" not in self.endpoints:
            await update.message.reply_text("Analytics service is not available. Please try again later.")
            return
        
        try:
            response = requests.get(f"{self.endpoints['analytics']}/sectors")
            if response.status_code == 200:
                sectors_data = response.json()
                
                if not sectors_data:
                    await update.message.reply_text("No sectors found.")
                    return
                
                sectors_text = "Available Pipeline Sectors:\n\n"
                
                for sector in sectors_data:
                    sectors_text += f"Sector ID: {sector['sector_id']}\n"
                    sectors_text += f"Description: {sector.get('description', 'No description')}\n"
                    sectors_text += "Devices:\n"
                    
                    for device in sector.get('devices', []):
                        sectors_text += f"  - {device['device_id']}: {device.get('description', 'No description')}\n"
                    
                    sectors_text += "\n"
                
                await update.message.reply_text(sectors_text)
            else:
                await update.message.reply_text("Failed to retrieve sectors information. Please try again later.")
        except Exception as e:
            await update.message.reply_text(f"Error retrieving sectors: {str(e)}")
    
    async def valve_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        self.active_chat_ids.add(update.effective_chat.id)
        
        user_id = update.effective_user.id
        if user_id not in self.authenticated_users or time.time() > self.authenticated_users[user_id]["expires"]:
            await update.message.reply_text("You need to authenticate first. Use /login username password")
            return
        
        if len(context.args) != 3:
            await update.message.reply_text("Usage: /valve sector_id device_id open|close")
            return
        
        sector_id = context.args[0]
        device_id = context.args[1]
        action = context.args[2].lower()
        
        if action not in ["open", "close"]:
            await update.message.reply_text("Valve action must be 'open' or 'close'")
            return
        
        if "control_center" not in self.endpoints:
            await update.message.reply_text("Control service is not available. Please try again later.")
            return
        
        try:
            response = requests.post(
                f"{self.endpoints['control_center']}/valve/control",
                json={
                    "sector_id": sector_id,
                    "device_id": device_id,
                    "action": action
                },
                headers={"Authorization": f"Bearer {self.authenticated_users[user_id]['token']}"}
            )
            
            if response.status_code == 200:
                await update.message.reply_text(f"Valve command '{action}' sent successfully to device {device_id} in sector {sector_id}.")
            else:
                await update.message.reply_text(f"Failed to send valve command: {response.text}")
        except Exception as e:
            await update.message.reply_text(f"Error sending valve command: {str(e)}")
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        data = query.data.split('_')
        
        if len(data) >= 4 and data[0] == "valve":
            sector_id = data[1]
            device_id = data[2]
            action = data[3]
            
            user_id = update.effective_user.id
            if user_id not in self.authenticated_users or time.time() > self.authenticated_users[user_id]["expires"]:
                await query.edit_message_text("You need to authenticate first. Use /login username password")
                return
            
            if "control_center" not in self.endpoints:
                await query.edit_message_text("Control service is not available. Please try again later.")
                return
            
            try:
                response = requests.post(
                    f"{self.endpoints['control_center']}/valve/control",
                    json={
                        "sector_id": sector_id,
                        "device_id": device_id,
                        "action": action
                    },
                    headers={"Authorization": f"Bearer {self.authenticated_users[user_id]['token']}"}
                )
                
                if response.status_code == 200:
                    await query.edit_message_text(f"Valve command '{action}' sent successfully to device {device_id} in sector {sector_id}.")
                else:
                    await query.edit_message_text(f"Failed to send valve command: {response.text}")
            except Exception as e:
                await query.edit_message_text(f"Error sending valve command: {str(e)}")
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self):
        return {"service": "Telegram Bot", "status": "running"}
    
    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def alert(self):
        if cherrypy.request.method == 'POST':
            alert_data = cherrypy.request.json
            
            try:
                message = self._format_alert_message(alert_data)
                self._send_alert_to_users(message)
                return {"status": "success", "message": "Alert sent to users"}
            except Exception as e:
                cherrypy.response.status = 500
                return {"status": "error", "message": str(e)}
        else:
            cherrypy.response.status = 405
            return {"status": "error", "message": "Method not allowed"}
    
    def _format_alert_message(self, alert_data):
        message = "🚨 ALERT 🚨\n\n"
        
        message += f"Time: {time.ctime(alert_data.get('timestamp', time.time()))}\n"
        message += f"Sector: {alert_data.get('sector_id', 'Unknown')}\n"
        message += f"Device: {alert_data.get('device_id', 'Unknown')}\n"
        message += f"Type: {alert_data.get('alert_type', 'Unknown')}\n"
        
        if alert_data.get('measurement_type'):
            message += f"Measurement: {alert_data.get('measurement_type')}\n"
        
        if alert_data.get('value') is not None:
            message += f"Value: {alert_data.get('value')}\n"
        
        if alert_data.get('threshold') is not None:
            message += f"Threshold: {alert_data.get('threshold')}\n"
        
        message += f"\nMessage: {alert_data.get('message', 'No additional information')}"
        
        if alert_data.get('device_id') and alert_data.get('sector_id'):
            message += "\n\nUse the command below to control the valve:"
            message += f"\n/valve {alert_data.get('sector_id')} {alert_data.get('device_id')} open|close"
        
        return message
    
    def _send_alert_to_users(self, message):
        async def send_alerts():
            for chat_id in self.active_chat_ids:
                try:
                    await self.bot_application.bot.send_message(chat_id=chat_id, text=message)
                except Exception as e:
                    cherrypy.log(f"Failed to send alert to chat {chat_id}: {e}")
        
        threading.Thread(target=lambda: asyncio.run(send_alerts())).start()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def status(self):
        """Status endpoint for the Telegram Bot Service"""
        return {
            "service": "Telegram Bot Service",
            "bot_running": self.bot_application is not None,
            "active_chats": len(self.active_chat_ids),
            "authenticated_users": len(self.authenticated_users),
            "uptime": time.time() - self.start_time if hasattr(self, 'start_time') else 0
        }

def periodic_tasks():
    service = cherrypy.engine.telegram_service
    service.update_service_status()
    service.discover_services()

if __name__ == '__main__':
    telegram_service = TelegramBotService()
    telegram_service.register_with_catalog()
    telegram_service.discover_services()
    
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': telegram_service.service_port,
        'engine.autoreload.on': False,
    })
    
    cherrypy.engine.telegram_service = telegram_service
    
    monitor = cherrypy.process.plugins.Monitor(
        cherrypy.engine,
        periodic_tasks,
        60
    )
    monitor.subscribe()
    
    cherrypy.quickstart(telegram_service)