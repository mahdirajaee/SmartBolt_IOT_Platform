import os
import sys
import importlib.util

def get_account_manager_port():
    account_manager_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                       "MS_AccountManager", "config.py")
    
    try:
        spec = importlib.util.spec_from_file_location("account_manager_config", account_manager_path)
        account_manager_config = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(account_manager_config)
        
        return account_manager_config.API_PORT
    except Exception as e:
        return 8088  # Default fallback port
