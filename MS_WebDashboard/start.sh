#!/bin/bash

# Start the Smart Bolt Web Dashboard
echo "Starting Smart Bolt Web Dashboard service..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Start the web dashboard service
echo "Starting web dashboard on port 5006..."
python main.py

# Deactivate virtual environment on exit
trap "deactivate" EXIT