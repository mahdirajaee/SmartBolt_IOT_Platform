import os
import json
import time
import logging
import requests
import threading
import cherrypy
import paho.mqtt.client as mqtt
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
PORT = 8085  # Adjust if needed
HOST = "0.0.0.0"
BASE_URL = f"http://{HOST}:{PORT}"
SERVICE_NAME = "TelegramBotService"
SERVICE_TYPE = "telegramService"

# Environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CATALOG_URL = os.getenv("CATALOG_URL", "http://localhost:8080")

# State constants for conversation handler
SELECT_PIPELINE, SELECT_ACTION, CONFIRM_ACTION = range(3)


class TelegramBotService:
    def __init__(self):
        self.mqtt_client = None
        self.broker_address = None
        self.broker_port = None
        self.catalog_url = CATALOG_URL
        self.registered = False
        self.authorized_users = set()
        self.service_endpoints = {}
        
        # Initialize MQTT client
        self.setup_mqtt()
        
        # Start the registration process
        self.register_service()
        
        # Setup telegram bot
        self.setup_telegram_bot()
        
        # Thread for periodic actions
        self.scheduler_thread = threading.Thread(target=self.periodic_tasks)
        self.scheduler_thread.daemon = True
        self.scheduler_thread.start()

    def setup_mqtt(self):
        """Set up MQTT client and connections"""
        try:
            # Get MQTT broker info from catalog
            broker_info = self.get_service_by_type("messageBroker")
            if broker_info:
                self.broker_address = broker_info.get("address", "localhost")
                self.broker_port = broker_info.get("port", 1883)
                
                # Setup MQTT client
                self.mqtt_client = mqtt.Client(client_id=f"telegram_bot_{int(time.time())}")
                self.mqtt_client.on_connect = self.on_mqtt_connect
                self.mqtt_client.on_message = self.on_mqtt_message
                
                # Connect to broker
                self.mqtt_client.connect(self.broker_address, self.broker_port, 60)
                
                # Start MQTT loop in a separate thread
                self.mqtt_client.loop_start()
                logger.info(f"Connected to MQTT broker at {self.broker_address}:{self.broker_port}")
            else:
                logger.error("Could not find MQTT broker information in catalog")
        except Exception as e:
            logger.error(f"Error setting up MQTT: {e}")

    def on_mqtt_connect(self, client, userdata, flags, rc):
        """Callback when connected to MQTT broker"""
        logger.info(f"Connected to MQTT broker with result code {rc}")
        # Subscribe to control topics
        client.subscribe("control/alerts/#")
        client.subscribe("control/commands/response/#")

    def on_mqtt_message(self, client, userdata, msg):
        """Handle incoming MQTT messages"""
        try:
            logger.info(f"Received message on topic {msg.topic}: {msg.payload.decode()}")
            
            # Parse message
            payload = json.loads(msg.payload.decode())
            
            # Handle based on topic
            if msg.topic.startswith("control/alerts/"):
                # Process alerts and notify users
                alert_type = msg.topic.split('/')[-1]
                self.broadcast_alert(alert_type, payload)
            
            elif msg.topic.startswith("control/commands/response/"):
                # Handle command responses
                response_id = msg.topic.split('/')[-1]
                self.process_command_response(response_id, payload)
        
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    async def broadcast_alert(self, alert_type, alert_data):
        """Send alerts to all authorized users"""
        if not self.application:
            logger.error("Telegram application not initialized")
            return
            
        alert_message = self.format_alert_message(alert_type, alert_data)
        
        for user_id in self.authorized_users:
            try:
                await self.application.bot.send_message(
                    chat_id=user_id,
                    text=alert_message,
                    parse_mode="HTML"
                )
                logger.info(f"Alert sent to user {user_id}")
            except Exception as e:
                logger.error(f"Failed to send alert to user {user_id}: {e}")

    def format_alert_message(self, alert_type, alert_data):
        """Format alert message based on type"""
        if alert_type == "threshold_exceeded":
            return (
                f"⚠️ <b>ALERT: Threshold Exceeded</b> ⚠️\n\n"
                f"<b>Pipeline:</b> {alert_data.get('pipeline_id')}\n"
                f"<b>Device:</b> {alert_data.get('device_id')}\n"
                f"<b>Sensor:</b> {alert_data.get('sensor_type')}\n"
                f"<b>Value:</b> {alert_data.get('value')} {alert_data.get('unit', '')}\n"
                f"<b>Threshold:</b> {alert_data.get('threshold')} {alert_data.get('unit', '')}\n"
                f"<b>Time:</b> {alert_data.get('timestamp')}\n\n"
                f"<b>Action:</b> {alert_data.get('action_taken', 'None')}"
            )
        elif alert_type == "prediction_alert":
            return (
                f"🔮 <b>PREDICTION ALERT</b> 🔮\n\n"
                f"<b>Pipeline:</b> {alert_data.get('pipeline_id')}\n"
                f"<b>Device:</b> {alert_data.get('device_id')}\n"
                f"<b>Prediction:</b> {alert_data.get('prediction_message')}\n"
                f"<b>Confidence:</b> {alert_data.get('confidence', 'N/A')}%\n"
                f"<b>Time Frame:</b> {alert_data.get('time_frame', 'N/A')}\n\n"
                f"<b>Recommended Action:</b> {alert_data.get('recommended_action', 'Monitor the situation')}"
            )
        elif alert_type == "system_alert":
            return (
                f"🔧 <b>SYSTEM ALERT</b> 🔧\n\n"
                f"<b>Component:</b> {alert_data.get('component')}\n"
                f"<b>Status:</b> {alert_data.get('status')}\n"
                f"<b>Message:</b> {alert_data.get('message')}\n"
                f"<b>Time:</b> {alert_data.get('timestamp')}"
            )
        else:
            return f"<b>ALERT:</b> {json.dumps(alert_data, indent=2)}"

    def process_command_response(self, response_id, response_data):
        """Process responses to commands sent via MQTT"""
        # Implementation depends on your command structure
        pass

    def setup_telegram_bot(self):
        """Set up the Telegram bot and handlers"""
        if not TELEGRAM_TOKEN:
            logger.error("TELEGRAM_TOKEN environment variable not set")
            return

        try:
            # Create application
            self.application = Application.builder().token(TELEGRAM_TOKEN).build()
            
            # Add command handlers
            self.application.add_handler(CommandHandler("start", self.start_command))
            self.application.add_handler(CommandHandler("help", self.help_command))
            self.application.add_handler(CommandHandler("status", self.status_command))
            
            # Add conversation handler for valve control
            conv_handler = ConversationHandler(
                entry_points=[CommandHandler("control", self.control_command)],
                states={
                    SELECT_PIPELINE: [CallbackQueryHandler(self.select_pipeline_callback)],
                    SELECT_ACTION: [CallbackQueryHandler(self.select_action_callback)],
                    CONFIRM_ACTION: [CallbackQueryHandler(self.confirm_action_callback)],
                },
                fallbacks=[CommandHandler("cancel", self.cancel_conversation)],
            )
            self.application.add_handler(conv_handler)
            
            # Run the bot until the user presses Ctrl-C
            self.application.run_polling(allowed_updates=Update.ALL_TYPES)
            
            logger.info("Telegram bot started successfully")
        except Exception as e:
            logger.error(f"Error setting up Telegram bot: {e}")
            self.application = None

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /start command"""
        user = update.effective_user
        
        # Check if user is authorized
        is_authorized = await self.authorize_user(user.id)
        
        if is_authorized:
            self.authorized_users.add(user.id)
            await update.message.reply_html(
                f"Hi {user.mention_html()}! Welcome to Smart IoT Bolt Monitoring Bot.\n\n"
                f"You are now authorized to receive alerts and control the system.\n\n"
                f"Use /help to see available commands."
            )
        else:
            await update.message.reply_text(
                "Sorry, you are not authorized to use this bot. "
                "Please contact the system administrator."
            )

    async def authorize_user(self, user_id):
        """Check if a user is authorized"""
        try:
            # Get authentication service from catalog
            auth_service = self.get_service_by_type("accountManager")
            if not auth_service:
                logger.error("Account manager service not found in catalog")
                return False
                
            # Check authorization
            auth_url = f"http://{auth_service.get('address')}:{auth_service.get('port')}/auth/verify_telegram"
            response = requests.post(
                auth_url,
                json={"telegram_id": user_id}
            )
            
            if response.status_code == 200:
                return response.json().get("authorized", False)
            return False
        except Exception as e:
            logger.error(f"Error authorizing user: {e}")
            return False

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /help command"""
        if update.effective_user.id not in self.authorized_users:
            await update.message.reply_text("You are not authorized to use this bot.")
            return
            
        help_text = (
            "🤖 <b>Smart IoT Bolt Bot Commands</b> 🤖\n\n"
            "/start - Start the bot and check authorization\n"
            "/help - Show this help message\n"
            "/status - Check system status\n"
            "/control - Control valve actuators\n"
            "/cancel - Cancel current operation\n\n"
            "<b>Alerts</b>: You will automatically receive alerts when anomalies are detected."
        )
        
        await update.message.reply_html(help_text)

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /status command"""
        if update.effective_user.id not in self.authorized_users:
            await update.message.reply_text("You are not authorized to use this bot.")
            return
            
        try:
            # Get pipeline data from the catalog
            catalog_service = self.get_service_by_type("catalog")
            if not catalog_service:
                await update.message.reply_text("Error: Cannot connect to service catalog.")
                return
                
            catalog_url = f"http://{catalog_service.get('address')}:{catalog_service.get('port')}/pipelines"
            response = requests.get(catalog_url)
            
            if response.status_code != 200:
                await update.message.reply_text(f"Error retrieving pipeline data: {response.status_code}")
                return
                
            pipelines = response.json()
            
            if not pipelines:
                await update.message.reply_text("No pipelines found in the system.")
                return
                
            # Format status message
            status_text = "📊 <b>System Status</b> 📊\n\n"
            
            for pipeline in pipelines:
                pipeline_id = pipeline.get("pipeline_id")
                status_text += f"<b>Pipeline {pipeline_id}</b>\n"
                
                # Get latest sensor data
                timeseries_service = self.get_service_by_type("timeSeriesConnector")
                if timeseries_service:
                    ts_url = f"http://{timeseries_service.get('address')}:{timeseries_service.get('port')}/data/{pipeline_id}/latest"
                    ts_response = requests.get(ts_url)
                    
                    if ts_response.status_code == 200:
                        latest_data = ts_response.json()
                        
                        for device_id, device_data in latest_data.items():
                            status_text += f"  └ <b>Device {device_id}</b>:\n"
                            status_text += f"     Temperature: {device_data.get('temperature', 'N/A')}°C\n"
                            status_text += f"     Pressure: {device_data.get('pressure', 'N/A')} bar\n"
                            status_text += f"     Valve: {device_data.get('valve_status', 'N/A')}\n"
                    else:
                        status_text += "  └ Error retrieving sensor data\n"
                else:
                    status_text += "  └ Cannot connect to time series service\n"
                
                status_text += "\n"
            
            await update.message.reply_html(status_text)
        except Exception as e:
            logger.error(f"Error in status command: {e}")
            await update.message.reply_text(f"Error retrieving system status: {str(e)}")

    async def control_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle the /control command - start the valve control conversation"""
        if update.effective_user.id not in self.authorized_users:
            await update.message.reply_text("You are not authorized to use this bot.")
            return
            
        try:
            # Get pipelines from catalog
            catalog_service = self.get_service_by_type("catalog")
            if not catalog_service:
                await update.message.reply_text("Error: Cannot connect to service catalog.")
                return ConversationHandler.END
                
            catalog_url = f"http://{catalog_service.get('address')}:{catalog_service.get('port')}/pipelines"
            response = requests.get(catalog_url)
            
            if response.status_code != 200:
                await update.message.reply_text(f"Error retrieving pipeline data: {response.status_code}")
                return ConversationHandler.END
                
            pipelines = response.json()
            
            if not pipelines:
                await update.message.reply_text("No pipelines found in the system.")
                return ConversationHandler.END
            
            # Create keyboard with pipeline options
            keyboard = []
            for pipeline in pipelines:
                pipeline_id = pipeline.get("pipeline_id")
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
        """Handle pipeline selection"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "cancel":
            await query.edit_message_text("Operation cancelled.")
            return ConversationHandler.END
        
        # Store the selected pipeline
        context.user_data["selected_pipeline"] = query.data
        
        # Get devices for the selected pipeline
        try:
            catalog_service = self.get_service_by_type("catalog")
            if not catalog_service:
                await query.edit_message_text("Error: Cannot connect to service catalog.")
                return ConversationHandler.END
                
            catalog_url = f"http://{catalog_service.get('address')}:{catalog_service.get('port')}/pipelines/{query.data}/devices"
            response = requests.get(catalog_url)
            
            if response.status_code != 200:
                await query.edit_message_text(f"Error retrieving device data: {response.status_code}")
                return ConversationHandler.END
                
            devices = response.json()
            
            if not devices:
                await query.edit_message_text(f"No devices found for Pipeline {query.data}.")
                return ConversationHandler.END
            
            # Create keyboard with device options
            keyboard = []
            for device in devices:
                device_id = device.get("device_id")
                keyboard.append([InlineKeyboardButton(f"Device {device_id}", callback_data=device_id)])
            
            keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"Selected Pipeline: {query.data}\nPlease select a device to control:",
                reply_markup=reply_markup
            )
            
            # Next state: select action for the device
            return SELECT_ACTION
            
        except Exception as e:
            logger.error(f"Error in select_pipeline_callback: {e}")
            await query.edit_message_text(f"Error selecting pipeline: {str(e)}")
            return ConversationHandler.END

    async def select_action_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle device selection and action selection"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "cancel":
            await query.edit_message_text("Operation cancelled.")
            return ConversationHandler.END
        
        # Store the selected device
        context.user_data["selected_device"] = query.data
        
        # Create keyboard with action options
        keyboard = [
            [InlineKeyboardButton("Open Valve", callback_data="open_valve")],
            [InlineKeyboardButton("Close Valve", callback_data="close_valve")],
            [InlineKeyboardButton("Cancel", callback_data="cancel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"Selected Pipeline: {context.user_data['selected_pipeline']}\n"
            f"Selected Device: {query.data}\n\n"
            f"Please select an action:",
            reply_markup=reply_markup
        )
        
        # Next state: confirm the action
        return CONFIRM_ACTION

    async def confirm_action_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle action confirmation"""
        query = update.callback_query
        await query.answer()
        
        if query.data == "cancel":
            await query.edit_message_text("Operation cancelled.")
            return ConversationHandler.END
        
        # Store the selected action
        context.user_data["selected_action"] = query.data
        
        # Get the action details
        action_name = "Open" if query.data == "open_valve" else "Close"
        action_value = 1 if query.data == "open_valve" else 0
        
        # Send command to control center via MQTT
        pipeline_id = context.user_data["selected_pipeline"]
        device_id = context.user_data["selected_device"]
        command_id = f"{int(time.time())}"
        
        command_payload = {
            "command_id": command_id,
            "pipeline_id": pipeline_id,
            "device_id": device_id,
            "actuator": "valve",
            "value": action_value,
            "source": "telegram_bot",
            "user_id": update.effective_user.id
        }
        
        # Publish to MQTT
        if self.mqtt_client:
            self.mqtt_client.publish(
                f"control/commands/actuator/{command_id}",
                json.dumps(command_payload)
            )
            
            # Inform user
            await query.edit_message_text(
                f"✅ Command sent!\n\n"
                f"Action: {action_name} valve\n"
                f"Pipeline: {pipeline_id}\n"
                f"Device: {device_id}\n\n"
                f"Command ID: {command_id}\n\n"
                f"You will be notified when the action is completed."
            )
        else:
            await query.edit_message_text(
                f"❌ Error: MQTT client not connected. Cannot send command."
            )
        
        return ConversationHandler.END

    async def cancel_conversation(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Cancel the conversation"""
        await update.message.reply_text("Operation cancelled.")
        return ConversationHandler.END

    def register_service(self):
        """Register this service with the catalog"""
        service_data = {
            "serviceType": SERVICE_TYPE,
            "serviceName": SERVICE_NAME,
            "address": HOST,
            "port": PORT,
            "endpoints": {
                "webhook": f"{BASE_URL}/webhook",
                "health": f"{BASE_URL}/health"
            },
            "status": "active",
            "timestamp": int(time.time())
        }
        
        try:
            response = requests.post(
                f"{self.catalog_url}/services",
                json=service_data
            )
            
            if response.status_code == 201:
                self.registered = True
                self.service_id = response.json().get("serviceId")
                logger.info(f"Service registered with ID: {self.service_id}")
            else:
                logger.error(f"Failed to register service: {response.status_code}, {response.text}")
        
        except Exception as e:
            logger.error(f"Error registering service: {e}")

    def update_service_status(self):
        """Update service status in the catalog"""
        if not self.registered:
            self.register_service()
            return
            
        try:
            status_data = {
                "status": "active",
                "timestamp": int(time.time())
            }
            
            response = requests.put(
                f"{self.catalog_url}/services/{self.service_id}",
                json=status_data
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to update service status: {response.status_code}, {response.text}")
                self.registered = False
        
        except Exception as e:
            logger.error(f"Error updating service status: {e}")
            self.registered = False

    def get_service_by_type(self, service_type):
        """Get service details from the catalog by type"""
        try:
            # First check if we have it cached
            if service_type in self.service_endpoints and time.time() - self.service_endpoints[service_type]["timestamp"] < 60:
                return self.service_endpoints[service_type]["service"]
                
            # Otherwise fetch from catalog
            response = requests.get(f"{self.catalog_url}/services/type/{service_type}")
            
            if response.status_code == 200:
                services = response.json()
                
                if services and len(services) > 0:
                    # Cache the result
                    self.service_endpoints[service_type] = {
                        "service": services[0],
                        "timestamp": time.time()
                    }
                    return services[0]
                    
            logger.error(f"Service {service_type} not found in catalog")
            return None
            
        except Exception as e:
            logger.error(f"Error getting service by type: {e}")
            return None

    def periodic_tasks(self):
        """Run periodic tasks in background"""
        while True:
            try:
                # Update service status
                self.update_service_status()
                
                # Other periodic tasks can be added here
                
            except Exception as e:
                logger.error(f"Error in periodic tasks: {e}")
                
            # Sleep for a while
            time.sleep(30)  # Update every 30 seconds

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def health(self):
        """Health check endpoint"""
        return {
            "status": "ok",
            "service": SERVICE_NAME,
            "timestamp": int(time.time())
        }

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def webhook(self):
        """Webhook for REST API alerts"""
        try:
            data = cherrypy.request.json
            
            # Process the webhook data (e.g., alerts from Analytics)
            alert_type = data.get("alert_type")
            alert_data = data.get("alert_data")
            
            if alert_type and alert_data:
                # Create a task to broadcast the alert
                threading.Thread(
                    target=self.async_broadcast_alert,
                    args=(alert_type, alert_data)
                ).start()
                
                return {"status": "success", "message": "Alert processing started"}
            else:
                return {"status": "error", "message": "Invalid alert data"}, 400
                
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            return {"status": "error", "message": str(e)}, 500

    def async_broadcast_alert(self, alert_type, alert_data):
        """Asynchronously broadcast alert (used from REST webhook)"""
        import asyncio
        asyncio.run(self.broadcast_alert(alert_type, alert_data))


def main():
    # Configure CherryPy
    cherrypy.config.update({
        'server.socket_host': HOST,
        'server.socket_port': PORT,
    })
    
    # Start the service
    telegram_service = TelegramBotService()
    cherrypy.quickstart(telegram_service)


if __name__ == "__main__":
    main()