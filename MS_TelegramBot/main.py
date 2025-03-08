import os
import json
import time
import logging
import asyncio
import threading
import requests
import cherrypy
import paho.mqtt.client as mqtt
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("telegram_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("TelegramBot")

SELECT_PIPELINE, SELECT_DEVICE, SELECT_ACTION, CONFIRM_ACTION = range(4)

class TelegramBotService:
    def __init__(self):
        self.config = self.load_config()
        self.service_id = "telegram_bot_service"
        self.service_info = {
            "id": self.service_id,
            "name": "Telegram Bot Service",
            "type": "notification_service",
            "endpoint": f"http://{self.get_host_ip()}:{self.config['api_port']}",
            "description": "Telegram Bot interface for Smart IoT Bolt platform",
            "apis": {
                "webhook": "/api/webhook",
                "health": "/api/health"
            },
            "status": "active",
            "last_update": int(time.time())
        }
        self.mqtt_client = None
        self.setup_mqtt()
        self.authorized_users = set()
        self.user_sessions = {}
        self.service_cache = {}
        self.cache_timestamp = 0
        self.register_with_catalog()
        self.application = None
        self.setup_telegram_bot()
        self.start_update_thread()
        logger.info("Telegram Bot Service initialized")

    def load_config(self):
        config = {
            "telegram_token": os.getenv("TELEGRAM_TOKEN"),
            "catalog_url": os.getenv("CATALOG_URL", "http://localhost:8080"),
            "mqtt_broker": os.getenv("MQTT_BROKER", "localhost"),
            "mqtt_port": int(os.getenv("MQTT_PORT", 1883)),
            "api_port": int(os.getenv("API_PORT", 8085)),
            "cache_ttl": int(os.getenv("CACHE_TTL", 60)),
            "admin_chat_id": os.getenv("ADMIN_CHAT_ID", "")
        }
        config_path = os.getenv("CONFIG_PATH", "config.json")
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    file_config = json.load(f)
                    for key, value in file_config.items():
                        if key not in config or config[key] is None:
                            config[key] = value
                logger.info(f"Loaded configuration from {config_path}")
            except Exception as e:
                logger.error(f"Error loading config file: {e}")
        if not config["telegram_token"]:
            logger.error("TELEGRAM_TOKEN is required")
            raise ValueError("TELEGRAM_TOKEN environment variable is required")
        return config

    def get_host_ip(self):
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "localhost"

    def setup_mqtt(self):
        try:
            broker_info = self.get_service_by_type("messageBroker")
            if broker_info:
                broker_address = broker_info.get("address", self.config["mqtt_broker"])
                broker_port = broker_info.get("port", self.config["mqtt_port"])
            else:
                broker_address = self.config["mqtt_broker"]
                broker_port = self.config["mqtt_port"]
            self.mqtt_client = mqtt.Client(client_id=f"telegram_bot_{int(time.time())}")
            self.mqtt_client.on_connect = self.on_mqtt_connect
            self.mqtt_client.on_message = self.on_mqtt_message
            self.mqtt_client.on_disconnect = self.on_mqtt_disconnect
            self.mqtt_client.connect(broker_address, broker_port, 60)
            self.mqtt_client.loop_start()
            logger.info(f"Connected to MQTT broker at {broker_address}:{broker_port}")
        except Exception as e:
            logger.error(f"Error setting up MQTT: {e}")

    def on_mqtt_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("Connected to MQTT broker")
            client.subscribe("alerts/temperature/#")
            client.subscribe("alerts/pressure/#")
            client.subscribe("alerts/valve/#")
            client.subscribe("alerts/prediction/#")
            client.subscribe("control/commands/response/#")
        else:
            logger.error(f"Failed to connect to MQTT broker with code {rc}")

    def on_mqtt_disconnect(self, client, userdata, rc):
        logger.warning(f"Disconnected from MQTT broker with code {rc}")
        if rc != 0:
            logger.info("Attempting to reconnect...")
            threading.Timer(5.0, self.setup_mqtt).start()

    def on_mqtt_message(self, client, userdata, msg):
        try:
            logger.info(f"Received message on topic {msg.topic}")
            payload = json.loads(msg.payload.decode())
            if msg.topic.startswith("alerts/"):
                alert_parts = msg.topic.split('/')
                if len(alert_parts) >= 2:
                    alert_type = alert_parts[1]
                    self.process_alert(alert_type, payload)
            elif msg.topic.startswith("control/commands/response/"):
                command_id = msg.topic.split('/')[-1]
                self.process_command_response(command_id, payload)
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from topic {msg.topic}")
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    def process_alert(self, alert_type, alert_data):
        alert_message = self.format_alert_message(alert_type, alert_data)
        pipeline_id = alert_data.get("pipeline_id")
        if not pipeline_id:
            logger.warning(f"Alert missing pipeline_id: {alert_data}")
            return
        self.send_alert_to_users(pipeline_id, alert_message)

    def format_alert_message(self, alert_type, alert_data):
        if alert_type == "temperature":
            return (
                f"🔥 <b>TEMPERATURE ALERT</b>\n\n"
                f"<b>Pipeline:</b> {alert_data.get('pipeline_id')}\n"
                f"<b>Device:</b> {alert_data.get('device_id')}\n"
                f"<b>Temperature:</b> {alert_data.get('value')}°C\n"
                f"<b>Threshold:</b> {alert_data.get('threshold')}°C\n"
                f"<b>Time:</b> {alert_data.get('timestamp')}\n\n"
                f"<b>Status:</b> {alert_data.get('status', 'Warning')}"
            )
        elif alert_type == "pressure":
            return (
                f"⚠️ <b>PRESSURE ALERT</b>\n\n"
                f"<b>Pipeline:</b> {alert_data.get('pipeline_id')}\n"
                f"<b>Device:</b> {alert_data.get('device_id')}\n"
                f"<b>Pressure:</b> {alert_data.get('value')} bar\n"
                f"<b>Threshold:</b> {alert_data.get('threshold')} bar\n"
                f"<b>Time:</b> {alert_data.get('timestamp')}\n\n"
                f"<b>Status:</b> {alert_data.get('status', 'Warning')}"
            )
        elif alert_type == "valve":
            return (
                f"🔧 <b>VALVE ALERT</b>\n\n"
                f"<b>Pipeline:</b> {alert_data.get('pipeline_id')}\n"
                f"<b>Device:</b> {alert_data.get('device_id')}\n"
                f"<b>Status:</b> {alert_data.get('status')}\n"
                f"<b>Time:</b> {alert_data.get('timestamp')}\n\n"
                f"<b>Action:</b> {alert_data.get('action', 'Manual review required')}"
            )
        elif alert_type == "prediction":
            return (
                f"🔮 <b>PREDICTIVE ALERT</b>\n\n"
                f"<b>Pipeline:</b> {alert_data.get('pipeline_id')}\n"
                f"<b>Device:</b> {alert_data.get('device_id')}\n"
                f"<b>Prediction:</b> {alert_data.get('message')}\n"
                f"<b>Confidence:</b> {alert_data.get('confidence', 'N/A')}%\n"
                f"<b>Time Frame:</b> {alert_data.get('time_frame', 'N/A')}\n\n"
                f"<b>Recommended Action:</b> {alert_data.get('recommended_action', 'Monitor the situation')}"
            )
        else:
            return f"<b>ALERT:</b> {json.dumps(alert_data)}"

    def send_alert_to_users(self, pipeline_id, alert_message):
        asyncio.run(self._async_send_alert_to_users(pipeline_id, alert_message))

    async def _async_send_alert_to_users(self, pipeline_id, alert_message):
        if not self.application:
            logger.error("Telegram application not initialized")
            return
        account_service = self.get_service_by_type("accountManager")
        if not account_service:
            logger.error("Account Manager service not found")
            for user_id in self.authorized_users:
                await self._send_telegram_message(user_id, alert_message)
            return
        try:
            account_url = f"{account_service['endpoint']}/pipeline_access/{pipeline_id}"
            response = requests.get(account_url)
            if response.status_code == 200:
                authorized_users = response.json().get("users", [])
                telegram_ids = [user.get("telegram_id") for user in authorized_users 
                               if user.get("telegram_id")]
                for telegram_id in telegram_ids:
                    await self._send_telegram_message(telegram_id, alert_message)
                if self.config["admin_chat_id"]:
                    await self._send_telegram_message(
                        self.config["admin_chat_id"], 
                        f"{alert_message}\n\n<i>Sent to {len(telegram_ids)} users</i>"
                    )
            else:
                logger.error(f"Failed to get pipeline access: {response.status_code}")
                for user_id in self.authorized_users:
                    await self._send_telegram_message(user_id, alert_message)
        except Exception as e:
            logger.error(f"Error sending alerts to users: {e}")
            for user_id in self.authorized_users:
                await self._send_telegram_message(user_id, alert_message)

    async def _send_telegram_message(self, chat_id, message):
        try:
            await self.application.bot.send_message(
                chat_id=chat_id,
                text=message,
                parse_mode="HTML"
            )
            logger.info(f"Alert sent to user {chat_id}")
        except Exception as e:
            logger.error(f"Failed to send message to {chat_id}: {e}")

    def process_command_response(self, command_id, response_data):
        for user_id, session in self.user_sessions.items():
            if session.get("last_command_id") == command_id:
                success = response_data.get("success", False)
                if success:
                    message = (
                        f" <b>Command Successful</b>\n\n"
                        f"<b>Action:</b> {session.get('last_action', 'Unknown')}\n"
                        f"<b>Pipeline:</b> {session.get('selected_pipeline', 'Unknown')}\n"
                        f"<b>Device:</b> {session.get('selected_device', 'Unknown')}\n"
                        f"<b>Time:</b> {datetime.now().isoformat()}\n\n"
                        f"<b>Response:</b> {response_data.get('message', 'Command processed successfully')}"
                    )
                else:
                    message = (
                        f" <b>Command Failed</b>\n\n"
                        f"<b>Action:</b> {session.get('last_action', 'Unknown')}\n"
                        f"<b>Pipeline:</b> {session.get('selected_pipeline', 'Unknown')}\n"
                        f"<b>Device:</b> {session.get('selected_device', 'Unknown')}\n"
                        f"<b>Time:</b> {datetime.now().isoformat()}\n\n"
                        f"<b>Error:</b> {response_data.get('error', 'Unknown error occurred')}"
                    )
                asyncio.run(self._send_telegram_message(user_id, message))
                return

    def register_with_catalog(self):
        try:
            response = requests.post(
                f"{self.config['catalog_url']}/services",
                json=self.service_info
            )
            if response.status_code in (200, 201):
                logger.info("Successfully registered with catalog")
                return True
            else:
                logger.error(f"Failed to register with catalog: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error registering with catalog: {e}")
            return False

    def update_status_with_catalog(self):
        self.service_info["last_update"] = int(time.time())
        try:
            response = requests.put(
                f"{self.config['catalog_url']}/services/{self.service_id}",
                json=self.service_info
            )
            if response.status_code == 200:
                logger.debug("Successfully updated status with catalog")
                return True
            else:
                logger.error(f"Failed to update status with catalog: {response.status_code} {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error updating status with catalog: {e}")
            return False

    def start_update_thread(self):
        def update_loop():
            while True:
                self.update_status_with_catalog()
                time.sleep(60)
        thread = threading.Thread(target=update_loop)
        thread.daemon = True
        thread.start()
        logger.info("Started catalog update thread")

    def get_service_by_type(self, service_type):
        current_time = time.time()
        if (service_type in self.service_cache 
                and current_time - self.cache_timestamp < self.config["cache_ttl"]):
            return self.service_cache[service_type]
        try:
            response = requests.get(
                f"{self.config['catalog_url']}/services/type/{service_type}"
            )
            if response.status_code == 200:
                services = response.json()
                if services and len(services) > 0:
                    self.service_cache[service_type] = services[0]
                    self.cache_timestamp = current_time
                    return services[0]
                else:
                    logger.warning(f"No services of type {service_type} found")
                    return None
            else:
                logger.error(f"Failed to get service by type: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error getting service by type: {e}")
            return None

    def get_pipelines(self):
        try:
            response = requests.get(f"{self.config['catalog_url']}/sectors")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get pipelines: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error getting pipelines: {e}")
            return []

    def get_devices_by_pipeline(self, pipeline_id):
        try:
            response = requests.get(
                f"{self.config['catalog_url']}/sectors/{pipeline_id}/bolts"
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get devices for pipeline {pipeline_id}: {response.status_code}")
                return []
        except Exception as e:
            logger.error(f"Error getting devices for pipeline {pipeline_id}: {e}")
            return []

    def get_latest_data(self, pipeline_id=None, device_id=None):
        try:
            ts_service = self.get_service_by_type("timeSeriesConnector")
            if not ts_service:
                logger.error("Time Series DB Connector service not found")
                return None
            params = {}
            if pipeline_id:
                params["pipeline_id"] = pipeline_id
            if device_id:
                params["device_id"] = device_id
            response = requests.get(
                f"{ts_service['endpoint']}/api/latest",
                params=params
            )
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get latest data: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error getting latest data: {e}")
            return None

    def setup_telegram_bot(self):
        if not self.config["telegram_token"]:
            logger.error("Telegram token not available")
            return
        try:
            self.application = Application.builder().token(self.config["telegram_token"]).build()
            self.application.add_handler(CommandHandler("start", self.start_command))
            self.application.add_handler(CommandHandler("help", self.help_command))
            self.application.add_handler(CommandHandler("status", self.status_command))
            self.application.add_handler(CommandHandler("stats", self.stats_command))
            self.application.add_handler(CommandHandler("alerts", self.alerts_command))
            conv_handler = ConversationHandler(
                entry_points=[CommandHandler("control", self.control_command)],
                states={
                    SELECT_PIPELINE: [CallbackQueryHandler(self.select_pipeline_callback)],
                    SELECT_DEVICE: [CallbackQueryHandler(self.select_device_callback)],
                    SELECT_ACTION: [CallbackQueryHandler(self.select_action_callback)],
                    CONFIRM_ACTION: [CallbackQueryHandler(self.confirm_action_callback)],
                },
                fallbacks=[CommandHandler("cancel", self.cancel_conversation)],
            )
            self.application.add_handler(conv_handler)
            self.application.run_polling(allowed_updates=Update.ALL_TYPES)
            logger.info("Telegram bot started successfully")
        except Exception as e:
            logger.error(f"Error setting up Telegram bot: {e}")
            self.application = None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        chat_id = update.effective_chat.id
        is_authorized = await self.authorize_user(user.id)
        if is_authorized:
            self.authorized_users.add(str(chat_id))
            self.user_sessions[str(chat_id)] = {
                "user_id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "last_activity": time.time()
            }
            await update.message.reply_html(
                f"Hi {user.mention_html()}! Welcome to the Smart IoT Bolt Monitoring System.\n\n"
                f"You are now authorized to receive alerts and control the system.\n\n"
                f"Use /help to see available commands."
            )
        else:
            await update.message.reply_text(
                "You are not authorized to use this bot. Please contact the system administrator."
            )

    async def authorize_user(self, user_id):
        account_service = self.get_service_by_type("accountManager")
        if not account_service:
            logger.warning("Account Manager service not found, authorization check will be skipped")
            return True
        try:
            response = requests.post(
                f"{account_service['endpoint']}/auth/verify_telegram",
                json={"telegram_id": user_id}
            )
            if response.status_code == 200:
                return response.json().get("authorized", False)
            else:
                logger.error(f"Failed to verify user: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Error authorizing user: {e}")
            if self.config["admin_chat_id"] and str(user_id) == self.config["admin_chat_id"]:
                return True
            return False

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_user_authorized(update.effective_chat.id):
            await update.message.reply_text("You are not authorized to use this bot.")
            return
        help_text = (
            "🤖 <b>Smart IoT Bolt Bot Commands</b> 🤖\n\n"
            "/start - Start the bot and verify authorization\n"
            "/help - Show this help message\n"
            "/status - Check current system status\n"
            "/control - Control valve actuators\n"
            "/stats - View system statistics and trends\n"
            "/alerts - View recent alerts\n"
            "/cancel - Cancel current operation\n\n"
            "<b>Alerts</b>: You will automatically receive alerts when anomalies are detected."
        )
        await update.message.reply_html(help_text)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_user_authorized(update.effective_chat.id):
            await update.message.reply_text("You are not authorized to use this bot.")
            return
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, 
            action="typing"
        )
        try:
            pipelines = self.get_pipelines()
            if not pipelines:
                await update.message.reply_text("No pipelines found in the system.")
                return
            latest_data = self.get_latest_data()
            if not latest_data:
                await update.message.reply_text("Unable to retrieve sensor data.")
                return
            status_text = " <b>Current System Status</b> \n\n"
            organized_data = {}
            for item in latest_data.get("data", []):
                pipeline_id = item.get("pipeline_id", "unknown")
                device_id = item.get("device_id", "unknown")
                measurement = item.get("measurement", "")
                field = item.get("field", "")
                value = item.get("value", "N/A")
                if pipeline_id not in organized_data:
                    organized_data[pipeline_id] = {}
                if device_id not in organized_data[pipeline_id]:
                    organized_data[pipeline_id][device_id] = {}
                key = f"{measurement.split('_')[0]}_{field}" if "_" in measurement else field
                organized_data[pipeline_id][device_id][key] = value
            for pipeline_id, devices in organized_data.items():
                status_text += f"<b>Pipeline {pipeline_id}</b>\n"
                for device_id, metrics in devices.items():
                    status_text += f"  └ <b>Device {device_id}</b>:\n"
                    temperature = metrics.get("sensor_value", metrics.get("temperature_value", "N/A"))
                    status_text += f"     Temperature: {temperature}°C\n"
                    pressure = metrics.get("pressure_value", "N/A")
                    status_text += f"     Pressure: {pressure} bar\n"
                    valve = metrics.get("actuator_status", metrics.get("valve_status", "N/A"))
                    status_text += f"     Valve: {valve}\n"
                status_text += "\n"
            status_text += f"<i>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
            await update.message.reply_html(status_text)
        except Exception as e:
            logger.error(f"Error in status command: {e}")
            await update.message.reply_text(f"Error retrieving system status: {str(e)}")

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_user_authorized(update.effective_chat.id):
            await update.message.reply_text("You are not authorized to use this bot.")
            return
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, 
            action="typing"
        )
        try:
            analytics_service = self.get_service_by_type("analytics")
            if not analytics_service:
                await update.message.reply_text("Analytics service not available.")
                return
            pipelines = self.get_user_pipelines(update.effective_chat.id)
            if not pipelines:
                await update.message.reply_text("No pipelines available or you don't have access to any.")
                return
            keyboard = []
            for pipeline in pipelines:
                pipeline_id = pipeline.get("id", "unknown")
                keyboard.append([InlineKeyboardButton(f"Pipeline {pipeline_id}", callback_data=f"stats_{pipeline_id}")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Select a pipeline to view statistics:",
                reply_markup=reply_markup
            )
        except Exception as e:
            logger.error(f"Error in stats command: {e}")
            await update.message.reply_text(f"Error retrieving statistics: {str(e)}")

    async def alerts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_user_authorized(update.effective_chat.id):
            await update.message.reply_text("You are not authorized to use this bot.")
            return
        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, 
            action="typing"
        )
        try:
            analytics_service = self.get_service_by_type("analytics")
            if not analytics_service:
                await update.message.reply_text("Analytics service not available.")
                return
            response = requests.get(f"{analytics_service['endpoint']}/api/alerts")
            if response.status_code != 200:
                await update.message.reply_text(f"Failed to retrieve alerts: {response.status_code}")
                return
            alerts = response.json().get("alerts", [])
            if not alerts:
                await update.message.reply_text("No active alerts at the moment.")
                return
            alerts_text = "🚨 <b>Current Active Alerts</b> 🚨\n\n"
            for alert in alerts:
                alert_type = alert.get("type", "unknown")
                pipeline_id = alert.get("pipeline_id", alert.get("bolt_id", "unknown")).split("_")[0]
                device_id = alert.get("device_id", alert.get("bolt_id", "unknown")).split("_")[-1]
                value = alert.get("predicted_value", alert.get("value", "N/A"))
                threshold = alert.get("threshold", "N/A")
                hours_until = alert.get("hours_until", "N/A")
                alert_level = alert.get("alert_level", "warning")
                alerts_text += (
                    f"<b>{alert_type.upper()} ALERT - {alert_level.upper()}</b>\n"
                    f"Pipeline: {pipeline_id}\n"
                    f"Device: {device_id}\n"
                    f"Value: {value}\n"
                    f"Threshold: {threshold}\n"
                )
                if hours_until != "N/A":
                    alerts_text += f"Predicted in: {hours_until} hours\n"
                alerts_text += "\n"
            alerts_text += f"<i>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
            await update.message.reply_html(alerts_text)
        except Exception as e:
            logger.error(f"Error in alerts command: {e}")
            await update.message.reply_text(f"Error retrieving alerts: {str(e)}")

    async def control_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.is_user_authorized(update.effective_chat.id):
            await update.message.reply_text("You are not authorized to use this bot.")
            return ConversationHandler.END
        chat_id = str(update.effective_chat.id)
        try:
            pipelines = self.get_user_pipelines(chat_id)
            if not pipelines:
                await update.message.reply_text("No pipelines available or you don't have access to any.")
                return ConversationHandler.END
            keyboard = []
            for pipeline in pipelines:
                pipeline_id = pipeline.get("id", "unknown")
                keyboard.append([InlineKeyboardButton(f"Pipeline {pipeline_id}", callback_data=pipeline_id)])
            keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Please select a pipeline to control:",
                reply_markup=reply_markup
            )
            return SELECT_PIPELINE
        except Exception as e:
            logger.error(f"Error in control command: {e}")
            await update.message.reply_text(f"Error starting control operation: {str(e)}")
            return ConversationHandler.END

    async def select_pipeline_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if query.data == "cancel":
            await query.edit_message_text("Operation cancelled.")
            return ConversationHandler.END
        chat_id = str(update.effective_chat.id)
        if chat_id not in self.user_sessions:
            self.user_sessions[chat_id] = {}
        self.user_sessions[chat_id]["selected_pipeline"] = query.data
        try:
            devices = self.get_devices_by_pipeline(query.data)
            if not devices:
                await query.edit_message_text(f"No devices found for Pipeline {query.data}.")
                return ConversationHandler.END
            keyboard = []
            for device in devices:
                device_id = device.get("id", "unknown")
                keyboard.append([InlineKeyboardButton(f"Device {device_id}", callback_data=device_id)])
            keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"Pipeline: {query.data}\nPlease select a device to control:",
                reply_markup=reply_markup
            )
            return SELECT_DEVICE
        except Exception as e:
            logger.error(f"Error in select_pipeline_callback: {e}")
            await query.edit_message_text(f"Error selecting pipeline: {str(e)}")
            return ConversationHandler.END

    async def select_device_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if query.data == "cancel":
            await query.edit_message_text("Operation cancelled.")
            return ConversationHandler.END
        chat_id = str(update.effective_chat.id)
        self.user_sessions[chat_id]["selected_device"] = query.data
        keyboard = [
            [InlineKeyboardButton("Open Valve", callback_data="open")],
            [InlineKeyboardButton("Close Valve", callback_data="close")],
            [InlineKeyboardButton("Cancel", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"Pipeline: {self.user_sessions[chat_id]['selected_pipeline']}\n"
            f"Device: {query.data}\n\n"
            f"Please select an action:",
            reply_markup=reply_markup
        )
        return SELECT_ACTION

    async def select_action_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if query.data == "cancel":
            await query.edit_message_text("Operation cancelled.")
            return ConversationHandler.END
        chat_id = str(update.effective_chat.id)
        self.user_sessions[chat_id]["selected_action"] = query.data
        keyboard = [
            [InlineKeyboardButton("Confirm", callback_data="confirm")],
            [InlineKeyboardButton("Cancel", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        action_name = "Open" if query.data == "open" else "Close"
        pipeline_id = self.user_sessions[chat_id]["selected_pipeline"]
        device_id = self.user_sessions[chat_id]["selected_device"]
        await query.edit_message_text(
            f"Please confirm the following action:\n\n"
            f"<b>Action:</b> {action_name} valve\n"
            f"<b>Pipeline:</b> {pipeline_id}\n"
            f"<b>Device:</b> {device_id}\n\n"
            f"Are you sure you want to proceed?",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        return CONFIRM_ACTION

    async def confirm_action_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        if query.data == "cancel":
            await query.edit_message_text("Operation cancelled.")
            return ConversationHandler.END
        chat_id = str(update.effective_chat.id)
        session = self.user_sessions[chat_id]
        action = session["selected_action"]
        pipeline_id = session["selected_pipeline"]
        device_id = session["selected_device"]
        command_id = f"cmd_{int(time.time())}_{chat_id[-6:]}"
        session["last_command_id"] = command_id
        session["last_action"] = "Open valve" if action == "open" else "Close valve"
        try:
            command_payload = {
                "command_id": command_id,
                "pipeline_id": pipeline_id,
                "device_id": device_id,
                "command": action,
                "source": "telegram_bot",
                "user_id": chat_id,
                "timestamp": datetime.now().isoformat()
            }
            if self.mqtt_client and self.mqtt_client.is_connected():
                topic = f"control/commands/valve/{pipeline_id}/{device_id}"
                result = self.mqtt_client.publish(
                    topic,
                    json.dumps(command_payload),
                    qos=1
                )
                if result.rc == mqtt.MQTT_ERR_SUCCESS:
                    await query.edit_message_text(
                        f"✅ Command sent!\n\n"
                        f"<b>Action:</b> {session['last_action']}\n"
                        f"<b>Pipeline:</b> {pipeline_id}\n"
                        f"<b>Device:</b> {device_id}\n\n"
                        f"Command ID: {command_id}\n\n"
                        f"You will be notified when the action is completed.",
                        parse_mode="HTML"
                    )
                else:
                    await query.edit_message_text(
                        f"❌ Failed to send command. Please try again later."
                    )
            else:
                control_service = self.get_service_by_type("controlCenter")
                if control_service:
                    response = requests.post(
                        f"{control_service['endpoint']}/api/valve/{device_id}",
                        json={"command": action, "pipeline_id": pipeline_id}
                    )
                    if response.status_code == 200:
                        await query.edit_message_text(
                            f"✅ Command sent via REST API!\n\n"
                            f"<b>Action:</b> {session['last_action']}\n"
                            f"<b>Pipeline:</b> {pipeline_id}\n"
                            f"<b>Device:</b> {device_id}\n\n"
                            f"You will be notified when the action is completed.",
                            parse_mode="HTML"
                        )
                    else:
                        await query.edit_message_text(
                            f"❌ Failed to send command via REST API: {response.status_code}\n"
                            f"Please try again later."
                        )
                else:
                    await query.edit_message_text(
                        f"❌ Error: MQTT client not connected and Control Center not available.\n"
                        f"Cannot send command."
                    )
        except Exception as e:
            logger.error(f"Error sending command: {e}")
            await query.edit_message_text(
                f"❌ Error sending command: {str(e)}\n"
                f"Please try again later."
            )
        return ConversationHandler.END

    async def cancel_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Operation cancelled.")
        return ConversationHandler.END

    def get_user_pipelines(self, chat_id):
        pipelines = self.get_pipelines()
        if self.config["admin_chat_id"] and str(chat_id) == self.config["admin_chat_id"]:
            return pipelines
        account_service = self.get_service_by_type("accountManager")
        if not account_service:
            logger.warning("Account Manager service not found, returning all pipelines")
            return pipelines
        try:
            user_response = requests.get(
                f"{account_service['endpoint']}/users/telegram/{chat_id}"
            )
            if user_response.status_code != 200:
                logger.error(f"Failed to get user by telegram ID: {user_response.status_code}")
                return []
            user_email = user_response.json().get("email")
            if not user_email:
                logger.error("User email not found")
                return []
            access_response = requests.get(
                f"{account_service['endpoint']}/user_pipelines",
                params={"email": user_email}
            )
            if access_response.status_code != 200:
                logger.error(f"Failed to get user pipelines: {access_response.status_code}")
                return []
            allowed_pipeline_ids = access_response.json().get("pipelines", [])
            filtered_pipelines = [p for p in pipelines if p.get("id") in allowed_pipeline_ids]
            return filtered_pipelines
        except Exception as e:
            logger.error(f"Error getting user pipelines: {e}")
            return []

    def is_user_authorized(self, chat_id):
        return str(chat_id) in self.authorized_users or (
            self.config["admin_chat_id"] and str(chat_id) == self.config["admin_chat_id"]
        )

class TelegramBotAPI:
    def __init__(self, bot_service):
        self.bot_service = bot_service

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self):
        return {
            "service": "Telegram Bot Service",
            "version": "1.0",
            "status": "running"
        }

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def health(self):
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat()
        }

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def webhook(self):
        try:
            data = cherrypy.request.json
            if "alert_type" not in data or "data" not in data:
                cherrypy.response.status = 400
                return {"error": "Missing required fields (alert_type, data)"}
            self.bot_service.process_alert(data["alert_type"], data["data"])
            return {"status": "success", "message": "Alert received and processed"}
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            cherrypy.response.status = 500
            return {"error": str(e)}

def main():
    try:
        bot_service = TelegramBotService()
        cherrypy.config.update({
            'server.socket_host': '0.0.0.0',
            'server.socket_port': bot_service.config['api_port'],
            'log.screen': True,
            'log.access_file': 'access.log',
            'log.error_file': 'error.log'
        })
        cherrypy.tree.mount(TelegramBotAPI(bot_service), '/api', {
            '/': {
                'tools.sessions.on': True,
                'tools.response_headers.on': True,
                'tools.response_headers.headers': [('Content-Type', 'application/json')],
            }
        })
        cherrypy.engine.start()
        cherrypy.engine.block()
    except Exception as e:
        logger.critical(f"Failed to start Telegram Bot Service: {e}")

if __name__ == "__main__":
    main()
