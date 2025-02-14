
# **SmartBolt_IOT_Platform**  
🚀 **An IoT platform for real-time monitoring and control of industrial pipelines using Smart IoT Bolts.**  

## **Overview**  
SmartBolt_IOT_Platform is a microservices-based IoT system designed for **real-time monitoring, analytics, and control** of industrial pipelines. It leverages **MQTT messaging, a time-series database, analytics, and a web dashboard** to provide predictive maintenance and operational insights.  

## **Key Features**  
✅ **Real-time Data Exchange** – Uses MQTT to transmit sensor data (temperature, pressure) and receive actuator commands.  
✅ **Microservices Architecture** – Modular design ensuring scalability and flexibility.  
✅ **Time-Series Database** – Stores sensor readings efficiently for historical analysis.  
✅ **Automated Actuator Control** – Smart logic to trigger actions (e.g., opening a valve) based on sensor thresholds.  
✅ **Web Dashboard** – Visualize live sensor data and control actuators from an interactive UI.  
✅ **Telegram Bot Integration** – Sends real-time alerts on critical events.  
✅ **Secure User Authentication** – Account management for role-based access control.  

## **Architecture**  
The system follows a **microservices-based architecture**, where each component operates independently:  

### **Microservices**  
| Service | Description |
|---------|------------|
| **MS_AccountManager** | Handles user authentication and access control. |
| **MS_Analytics** | Processes sensor data and triggers actions based on thresholds. |
| **MS_ControlCenter** | Central orchestration for managing microservices. |
| **MS_ResourceCatalog** | Maintains service registry for dynamic discovery. |
| **MS_TelegramBot** | Sends notifications to users on threshold violations. |
| **MS_TimeSeriesDbConnector** | Stores and retrieves sensor data in a time-series database. |
| **MS_WebDashboard** | Frontend dashboard for real-time visualization and control. |
| **Raspberry Pi Connector** | Simulates sensors and listens for actuator commands. |

## **Technology Stack**  
- **Backend:** Python (CherryPy, Paho-MQTT)  
- **Frontend:** HTML, JavaScript (Web Dashboard)  
- **Database:** InfluxDB (Time-Series Data Storage)  
- **Messaging:** MQTT (Mosquitto)  
- **DevOps:** Docker (Containerization)  

## **Installation & Setup**  
### **1. Clone the Repository**  
```bash
git clone https://github.com/mahdirajaee/SmartBolt_IOT_Platform.git
cd SmartBolt_IOT_Platform
```

### **2. Set Up Environment Variables**  
Create a `.env` file in each microservice directory and define necessary configurations such as:  
```ini
MQTT_BROKER=<your_mqtt_broker_url>
DB_HOST=<your_database_host>
TELEGRAM_BOT_TOKEN=<your_bot_token>
```

### **3. Run Services**  
Start individual microservices:  
```bash
python MS_AccountManager/app.py
python MS_Analytics/app.py
python MS_ControlCenter/app.py
# Repeat for other services
```

Or use **Docker Compose** for containerized deployment:  
```bash
docker-compose up --build
```

## **API Endpoints**  
Each microservice exposes RESTful APIs. Example:  

### **MS_TimeSeriesDbConnector**
- **GET /data** → Retrieve latest sensor readings  
- **POST /data** → Store new sensor reading  

### **MS_Analytics**
- **GET /analyze** → Fetch processed insights  
- **POST /trigger** → Manually trigger an action  

### **MS_WebDashboard**
- **GET /dashboard** → Fetch live data for visualization  

## **MQTT Topics**  
| Topic | Description |
|-------|------------|
| `/sensor/temperature` | Publishes real-time temperature data. |
| `/sensor/pressure` | Publishes real-time pressure data. |
| `/actuator/valve` | Commands the valve to open/close. |

## **Contributing**  
🚀 Contributions are welcome! Feel free to fork the repository, create a new branch, and submit a pull request.  

## **License**  
📜 This project is licensed under the **MIT License** – see the [LICENSE](LICENSE) file for details.  

## **Contact**  
For questions or suggestions, reach out via GitHub Issues or Telegram Bot alerts.  
