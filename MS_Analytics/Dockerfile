FROM python:3-slim
WORKDIR /app
COPY main.py /app
COPY requirements.txt /app
RUN pip install --no-cache-dir -r requirements.txt
CMD ["python", "main.py"]

