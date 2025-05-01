import os

BASE_URL = os.environ.get('BASE_URL', 'http://localhost')
PORT = int(os.environ.get('PORT', 8083))

ACCOUNT_MANAGER_URL = os.environ.get('ACCOUNT_MANAGER_URL', f'{BASE_URL}:8000')
RESOURCE_CATALOG_URL = os.environ.get('RESOURCE_CATALOG_URL', f'{BASE_URL}:8080')
ANALYTICS_URL = os.environ.get('ANALYTICS_URL', f'{BASE_URL}:8001')
TIMESERIES_URL = os.environ.get('TIMESERIES_URL', f'{BASE_URL}:8002')

SECRET_KEY = os.environ.get('SECRET_KEY', 'development_secret_key')
DEBUG = os.environ.get('DEBUG', 'True').lower() in ['true', '1', 't']

SERVICE_ID = "web_dashboard"
SERVICE_NAME = "Web Dashboard"
SERVICE_DESCRIPTION = "User interface for Smart Irrigation System"
SERVICE_TYPE = "ui"
REGISTRATION_INTERVAL = 60 