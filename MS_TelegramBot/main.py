import json
import logging
import os
import signal
import sys
import cherrypy
from telegram_bot import TelegramBot

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")

def setup_logging(config):
    log_level = getattr(logging, config["logging"]["level"])
    log_file = config["logging"]["file"]
    
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    
    cherrypy.log.screen = False
    
    return logging.getLogger("main")

class TelegramBotService:
    def __init__(self):
        with open(CONFIG_PATH, 'r') as f:
            self.config = json.load(f)
            
        self.logger = setup_logging(self.config)
        self.bot = TelegramBot(CONFIG_PATH)
        self.port = self.config["service"]["port"]
        
        self.logger.info("Telegram Bot Service initializing")
        
    @cherrypy.expose
    def index(self):
        return "Telegram Bot Service Running"
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def health(self):
        return {
            "status": "ok",
            "service": self.config["service"]["id"],
            "version": "1.0.0"
        }
    
    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def send_message(self):
        try:
            data = cherrypy.request.json
            
            if "chat_id" not in data or "text" not in data:
                raise ValueError("Missing required parameters: chat_id, text")
                
            chat_id = data["chat_id"]
            text = data["text"]
            
            self.bot.bot.send_message(chat_id=chat_id, text=text)
            
            return {"status": "ok", "message": "Message sent"}
            
        except Exception as e:
            self.logger.error(f"Error sending message: {str(e)}")
            cherrypy.response.status = 500
            return {"status": "error", "message": str(e)}
    
    def start(self):
        self.bot.start()
        
        cherrypy.config.update({
            'server.socket_host': '0.0.0.0',
            'server.socket_port': self.port
        })
        
        cherrypy.engine.signals.subscribe()
        
        cherrypy.tree.mount(self, '/', {
            '/': {
                'tools.sessions.on': True,
                'tools.response_headers.on': True,
                'tools.response_headers.headers': [('Content-Type', 'text/plain')]
            }
        })
        
        self.logger.info(f"Starting CherryPy server on port {self.port}")
        cherrypy.engine.start()
    
    def stop(self):
        self.logger.info("Stopping Telegram Bot Service")
        self.bot.stop()
        cherrypy.engine.exit()

def signal_handler(sig, frame):
    logger = logging.getLogger("main")
    logger.info("Shutdown signal received")
    if hasattr(signal_handler, "service"):
        signal_handler.service.stop()
    sys.exit(0)

if __name__ == "__main__":
    service = TelegramBotService()
    
    signal_handler.service = service
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    service.start()
    cherrypy.engine.block() 