FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY message_broker.py .
COPY broker_utils.py .
COPY config.json .

# Create directory for logs
RUN mkdir -p /app/logs

# Run the message broker
CMD ["python", "message_broker.py"]