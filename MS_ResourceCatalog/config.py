import os
import json

# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Default configuration
DEFAULT_CONFIG = {
    "server": {
        "host": "0.0.0.0",
        "port": 8080
    },
    "storage": {
        "db_path": os.path.join(BASE_DIR, "catalog_db.json")
    },
    "timeout": {
        "device_offline": 300,  # 5 minutes
        "cleanup_interval": 60  # 1 minute
    },
    "logging": {
        "level": "INFO",
        "file": os.path.join(BASE_DIR, "resource_catalog.log")
    }
}

class Config:
    """Configuration manager for the Resource Catalog"""
    
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = os.path.join(BASE_DIR, "config.json")
        self.config_path = config_path
        self.config = DEFAULT_CONFIG.copy()
        self._load_config()
    
    def _load_config(self):
        """Load configuration from file if it exists"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as config_file:
                    loaded_config = json.load(config_file)
                    # Update the default config with loaded values
                    for section in loaded_config:
                        if section in self.config:
                            if isinstance(loaded_config[section], dict):
                                self.config[section].update(loaded_config[section])
                            else:
                                self.config[section] = loaded_config[section]
            except Exception as e:
                print(f"Error loading config file: {e}")
                # Use default config if there's an error
                pass
        else:
            # Save default config if no file exists
            self.save_config()
    
    def save_config(self):
        """Save current configuration to file"""
        try:
            with open(self.config_path, 'w') as config_file:
                json.dump(self.config, config_file, indent=4)
        except Exception as e:
            print(f"Error saving config file: {e}")
    
    def get(self, section=None, key=None):
        """Get configuration value(s)"""
        if section is None:
            return self.config
        
        if key is None and section in self.config:
            return self.config[section]
        
        if section in self.config and key in self.config[section]:
            return self.config[section][key]
        
        return None
    
    def set(self, section, key, value):
        """Set a configuration value"""
        if section not in self.config:
            self.config[section] = {}
        
        self.config[section][key] = value
        self.save_config()
        return value