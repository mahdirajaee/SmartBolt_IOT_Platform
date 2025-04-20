"""
Configuration for Telegram Bot
This file sets environment variables to configure the python-telegram-bot library
before it is imported.
"""
import os
import sys

# Set environment variable to disable usage of proxies in httpx
# This fixes the "AsyncClient.__init__() got an unexpected keyword argument 'proxies'" error
os.environ["PTB_HTTPX_DISABLE_PROXIES"] = "True" 