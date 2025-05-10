#!/usr/bin/env python3
"""
Web Dashboard Microservice
- Provides a web interface for system monitoring
- Displays real-time and historical sensor data
- Allows valve control
"""
import os
import sys
import json
import cherrypy
import logging
import requests
from datetime import datetime
import argparse

# Add parent directory to path to import common_utils
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(parent_dir)
import common_utils

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Service configuration
SERVICE_NAME = os.environ.get("SERVICE_NAME", "Web Dashboard")
SERVICE_TYPE = os.environ.get("SERVICE_TYPE", "web_dashboard")
SERVICE_PORT = int(os.environ.get("SERVICE_PORT", 8008))
SERVICE_HOST = os.environ.get("SERVICE_HOST", "0.0.0.0")
SERVICE_BASE_URL = os.environ.get("SERVICE_BASE_URL", f"http://localhost:{SERVICE_PORT}")

# Static directory for web assets
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

# Backend Service URLs - can be configured via environment variables
RESOURCE_CATALOG_URL = os.environ.get("RESOURCE_CATALOG_URL", "http://localhost:8001")
TIME_SERIES_DB_URL = os.environ.get("TIME_SERIES_DB_URL", "http://localhost:8003")
ANALYTICS_URL = os.environ.get("ANALYTICS_URL", "http://localhost:8004")
CONTROL_CENTER_URL = os.environ.get("CONTROL_CENTER_URL", "http://localhost:8005")

# Request timeout in seconds
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", 5))

# Default service ports for service discovery
DEFAULT_SERVICE_PORTS = {
    "resource_catalog": int(os.environ.get("RESOURCE_CATALOG_PORT", 8001)),
    "raspberry_pi": int(os.environ.get("RASPBERRY_PI_PORT", 8002)),
    "time_series_db": int(os.environ.get("TIME_SERIES_DB_PORT", 8003)),
    "analytics": int(os.environ.get("ANALYTICS_PORT", 8004)),
    "control_center": int(os.environ.get("CONTROL_CENTER_PORT", 8005)),
    "account_manager": int(os.environ.get("ACCOUNT_MANAGER_PORT", 8006)),
    "telegram_bot": int(os.environ.get("TELEGRAM_BOT_PORT", 8007))
}

class Dashboard:
    """Web Dashboard for system monitoring"""
    
    def __init__(self):
        """Initialize the dashboard"""
        # Create directories if they don't exist
        os.makedirs(STATIC_DIR, exist_ok=True)
        os.makedirs(TEMPLATE_DIR, exist_ok=True)
        os.makedirs(os.path.join(STATIC_DIR, "js"), exist_ok=True)
        os.makedirs(os.path.join(STATIC_DIR, "css"), exist_ok=True)
        
        # Service cache
        self.service_cache = {}
        
        # Generate static files if they don't exist
        self._generate_static_files()
        
        # Register with Resource Catalog
        try:
            common_utils.register_service(
                SERVICE_NAME,
                SERVICE_TYPE,
                SERVICE_BASE_URL,
                "Web dashboard for monitoring and control"
            )
            logger.info(f"Registered with Resource Catalog: {SERVICE_NAME}")
        except Exception as e:
            logger.warning(f"Failed to register with Resource Catalog: {e}")
        
        logger.info(f"Web Dashboard initialized on {SERVICE_HOST}:{SERVICE_PORT}")
    
    def _generate_static_files(self):
        """Generate static files for the dashboard if they don't exist"""
        # Dashboard HTML template
        index_html = os.path.join(TEMPLATE_DIR, "index.html")
        if not os.path.exists(index_html):
            with open(index_html, "w") as f:
                f.write("""<!DOCTYPE html>
<html lang="en" data-bs-theme="dark">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Smart IoT Bolt Dashboard</title>
    <link rel="stylesheet" href="https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css">
    <link rel="stylesheet" href="/static/css/dashboard.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/moment"></script>
</head>
<body>
    <header class="navbar navbar-expand-lg navbar-dark bg-dark mb-4">
        <div class="container-fluid">
            <a class="navbar-brand" href="#">Smart IoT Bolt</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav">
                    <li class="nav-item">
                        <a class="nav-link" href="#" data-page="dashboard">Dashboard</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="#" data-page="historical">Historical Data</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="#" data-page="analytics">Analytics</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="#" data-page="controls">Controls</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="#" data-page="alerts">Alerts</a>
                    </li>
                </ul>
                <div class="d-flex ms-auto">
                    <span class="navbar-text me-3">
                        <span id="connection-status" class="badge bg-success">Connected</span>
                    </span>
                    <a href="/logout" class="btn btn-outline-light btn-sm">Logout</a>
                </div>
            </div>
        </div>
    </header>

    <div class="container" id="main-content">
        <!-- Dashboard Page -->
        <div class="page" id="dashboard-page">
            <h2>System Dashboard</h2>
            <div class="row mt-4">
                <div class="col-md-6">
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="card-title">Current Readings</h5>
                        </div>
                        <div class="card-body">
                            <div class="row">
                                <div class="col-6">
                                    <div class="sensor-card">
                                        <h6>Temperature</h6>
                                        <div class="reading" id="temperature-reading">-- °C</div>
                                        <div class="trend" id="temperature-trend"></div>
                                    </div>
                                </div>
                                <div class="col-6">
                                    <div class="sensor-card">
                                        <h6>Pressure</h6>
                                        <div class="reading" id="pressure-reading">-- kPa</div>
                                        <div class="trend" id="pressure-trend"></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    <div class="card">
                        <div class="card-header">
                            <h5 class="card-title">System Status</h5>
                        </div>
                        <div class="card-body">
                            <div class="row">
                                <div class="col-6">
                                    <div class="status-item">
                                        <h6>Valve</h6>
                                        <span class="badge" id="valve-status">Unknown</span>
                                    </div>
                                </div>
                                <div class="col-6">
                                    <div class="status-item">
                                        <h6>System State</h6>
                                        <span class="badge" id="system-state">Unknown</span>
                                    </div>
                                </div>
                            </div>
                            <div class="mt-3">
                                <h6>Services</h6>
                                <div class="service-grid">
                                    <div class="service-item">
                                        <span>Resource Catalog</span>
                                        <span class="badge" id="service-resource_catalog">Unknown</span>
                                    </div>
                                    <div class="service-item">
                                        <span>Raspberry Pi</span>
                                        <span class="badge" id="service-raspberry_pi">Unknown</span>
                                    </div>
                                    <div class="service-item">
                                        <span>Time Series DB</span>
                                        <span class="badge" id="service-time_series_db">Unknown</span>
                                    </div>
                                    <div class="service-item">
                                        <span>Analytics</span>
                                        <span class="badge" id="service-analytics">Unknown</span>
                                    </div>
                                    <div class="service-item">
                                        <span>Control Center</span>
                                        <span class="badge" id="service-control_center">Unknown</span>
                                    </div>
                                    <div class="service-item">
                                        <span>Account Manager</span>
                                        <span class="badge" id="service-account_manager">Unknown</span>
                                    </div>
                                    <div class="service-item">
                                        <span>Telegram Bot</span>
                                        <span class="badge" id="service-telegram_bot">Unknown</span>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="card-title">Temperature Trend (Last Hour)</h5>
                        </div>
                        <div class="card-body">
                            <canvas id="temperature-chart" height="200"></canvas>
                        </div>
                    </div>
                    <div class="card">
                        <div class="card-header">
                            <h5 class="card-title">Pressure Trend (Last Hour)</h5>
                        </div>
                        <div class="card-body">
                            <canvas id="pressure-chart" height="200"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Historical Data Page -->
        <div class="page" id="historical-page" style="display: none;">
            <h2>Historical Data</h2>
            <div class="card mb-4">
                <div class="card-header">
                    <div class="d-flex justify-content-between align-items-center">
                        <h5 class="card-title mb-0">Sensor Data</h5>
                        <div class="d-flex">
                            <select class="form-select me-2" id="sensor-type-select">
                                <option value="temperature">Temperature</option>
                                <option value="pressure">Pressure</option>
                            </select>
                            <select class="form-select me-2" id="time-range-select">
                                <option value="1">Last Hour</option>
                                <option value="6">Last 6 Hours</option>
                                <option value="24">Last 24 Hours</option>
                            </select>
                            <button class="btn btn-outline-secondary" id="refresh-historical-btn">Refresh</button>
                        </div>
                    </div>
                </div>
                <div class="card-body">
                    <canvas id="historical-chart" height="250"></canvas>
                </div>
            </div>
            <div class="card">
                <div class="card-header">
                    <h5 class="card-title">Data Table</h5>
                </div>
                <div class="card-body">
                    <div class="table-responsive">
                        <table class="table table-striped" id="data-table">
                            <thead>
                                <tr>
                                    <th>Timestamp</th>
                                    <th>Value</th>
                                    <th>Sensor ID</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td colspan="3" class="text-center">No data available</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <!-- Analytics Page -->
        <div class="page" id="analytics-page" style="display: none;">
            <h2>Analytics & Predictions</h2>
            <div class="row">
                <div class="col-md-6">
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="card-title">Temperature Analysis</h5>
                        </div>
                        <div class="card-body">
                            <div class="status-item mb-3">
                                <h6>Current Value</h6>
                                <span id="temp-analytics-current">-- °C</span>
                            </div>
                            <div class="status-item mb-3">
                                <h6>Status</h6>
                                <span class="badge" id="temp-analytics-status">Unknown</span>
                            </div>
                            <div class="status-item mb-3">
                                <h6>Thresholds</h6>
                                <div>High: <span id="temp-high-threshold">--</span> °C</div>
                                <div>Low: <span id="temp-low-threshold">--</span> °C</div>
                            </div>
                        </div>
                    </div>
                    <div class="card">
                        <div class="card-header">
                            <h5 class="card-title">Temperature Predictions</h5>
                        </div>
                        <div class="card-body">
                            <canvas id="temp-prediction-chart" height="200"></canvas>
                        </div>
                    </div>
                </div>
                <div class="col-md-6">
                    <div class="card mb-4">
                        <div class="card-header">
                            <h5 class="card-title">Pressure Analysis</h5>
                        </div>
                        <div class="card-body">
                            <div class="status-item mb-3">
                                <h6>Current Value</h6>
                                <span id="pressure-analytics-current">-- kPa</span>
                            </div>
                            <div class="status-item mb-3">
                                <h6>Status</h6>
                                <span class="badge" id="pressure-analytics-status">Unknown</span>
                            </div>
                            <div class="status-item mb-3">
                                <h6>Thresholds</h6>
                                <div>High: <span id="pressure-high-threshold">--</span> kPa</div>
                                <div>Low: <span id="pressure-low-threshold">--</span> kPa</div>
                            </div>
                        </div>
                    </div>
                    <div class="card">
                        <div class="card-header">
                            <h5 class="card-title">Pressure Predictions</h5>
                        </div>
                        <div class="card-body">
                            <canvas id="pressure-prediction-chart" height="200"></canvas>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Controls Page -->
        <div class="page" id="controls-page" style="display: none;">
            <h2>System Controls</h2>
            <div class="card mb-4">
                <div class="card-header">
                    <h5 class="card-title">Valve Control</h5>
                </div>
                <div class="card-body">
                    <div class="row align-items-center mb-4">
                        <div class="col-md-4">
                            <h6>Current Valve State:</h6>
                            <span class="badge" id="control-valve-status">Unknown</span>
                        </div>
                        <div class="col-md-8">
                            <div class="d-flex">
                                <button class="btn btn-success me-2" id="open-valve-btn">Open Valve</button>
                                <button class="btn btn-danger" id="close-valve-btn">Close Valve</button>
                            </div>
                        </div>
                    </div>
                    <div class="mb-3">
                        <label for="valve-reason" class="form-label">Reason for change (optional):</label>
                        <input type="text" class="form-control" id="valve-reason" placeholder="Enter reason for valve state change">
                    </div>
                    <div class="alert alert-info">
                        <strong>Note:</strong> Changing the valve state may affect the flow in the pipeline. Make sure to check the current sensor readings before changing the valve state.
                    </div>
                </div>
            </div>
            
            <div class="card">
                <div class="card-header">
                    <h5 class="card-title">System Status</h5>
                </div>
                <div class="card-body">
                    <div class="row">
                        <div class="col-md-6">
                            <div class="status-item mb-3">
                                <h6>Overall System State</h6>
                                <span class="badge" id="controls-system-state">Unknown</span>
                            </div>
                            <div class="status-item mb-3">
                                <h6>Last Updated</h6>
                                <span id="controls-last-updated">Unknown</span>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="status-item mb-3">
                                <h6>Temperature</h6>
                                <span id="controls-temperature">-- °C</span>
                            </div>
                            <div class="status-item mb-3">
                                <h6>Pressure</h6>
                                <span id="controls-pressure">-- kPa</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Alerts Page -->
        <div class="page" id="alerts-page" style="display: none;">
            <h2>System Alerts</h2>
            <div class="card">
                <div class="card-header">
                    <div class="d-flex justify-content-between align-items-center">
                        <h5 class="card-title mb-0">Recent Alerts</h5>
                        <button class="btn btn-outline-secondary" id="refresh-alerts-btn">Refresh</button>
                    </div>
                </div>
                <div class="card-body">
                    <div class="table-responsive">
                        <table class="table table-striped" id="alerts-table">
                            <thead>
                                <tr>
                                    <th>Time</th>
                                    <th>Type</th>
                                    <th>Message</th>
                                    <th>Details</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr>
                                    <td colspan="4" class="text-center">No alerts found</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                    <div class="d-flex justify-content-between mt-3">
                        <button class="btn btn-sm btn-outline-secondary" id="prev-alerts-btn" disabled>Previous</button>
                        <button class="btn btn-sm btn-outline-secondary" id="next-alerts-btn" disabled>Next</button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <footer class="footer mt-5 py-3 bg-dark">
        <div class="container text-center">
            <span class="text-muted">Smart IoT Bolt Pipeline Monitoring System &copy; 2025</span>
        </div>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script src="/static/js/dashboard.js"></script>
</body>
</html>
""")
        
        # Dashboard CSS
        dashboard_css = os.path.join(STATIC_DIR, "css", "dashboard.css")
        if not os.path.exists(dashboard_css):
            with open(dashboard_css, "w") as f:
                f.write("""/* Dashboard Styles */
body {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
}

.navbar-brand {
    font-weight: bold;
}

.card {
    margin-bottom: 1.5rem;
    border: 1px solid rgba(255, 255, 255, 0.1);
}

.card-header {
    background-color: rgba(255, 255, 255, 0.05);
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.sensor-card {
    text-align: center;
    padding: 1rem;
    background-color: rgba(255, 255, 255, 0.03);
    border-radius: 0.5rem;
    height: 100%;
}

.reading {
    font-size: 2rem;
    font-weight: bold;
    margin: 0.5rem 0;
}

.trend {
    font-size: 1.2rem;
    height: 1.5rem;
}

.status-item {
    margin-bottom: 0.5rem;
}

.service-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 0.5rem;
}

.service-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background-color: rgba(255, 255, 255, 0.03);
    padding: 0.5rem;
    border-radius: 0.25rem;
}

.footer {
    margin-top: auto;
}

/* Badge status styles */
.badge-normal {
    background-color: var(--bs-success);
}

.badge-warning {
    background-color: var(--bs-warning);
    color: #000;
}

.badge-critical {
    background-color: var(--bs-danger);
}

.badge-running {
    background-color: var(--bs-success);
}

.badge-error {
    background-color: var(--bs-danger);
}

.badge-not_running {
    background-color: var(--bs-secondary);
}

.badge-open {
    background-color: var(--bs-success);
}

.badge-closed {
    background-color: var(--bs-danger);
}

.badge-high {
    background-color: var(--bs-danger);
}

.badge-low {
    background-color: var(--bs-warning);
    color: #000;
}

/* Charts */
canvas {
    width: 100% !important;
}

/* Media queries for responsiveness */
@media (max-width: 768px) {
    .service-grid {
        grid-template-columns: 1fr 1fr;
    }
    
    .reading {
        font-size: 1.5rem;
    }
}

@media (max-width: 576px) {
    .service-grid {
        grid-template-columns: 1fr;
    }
}
""")
        
        # Dashboard JS
        dashboard_js = os.path.join(STATIC_DIR, "js", "dashboard.js")
        if not os.path.exists(dashboard_js):
            with open(dashboard_js, "w") as f:
                f.write("""// Dashboard JavaScript

// Charts
let temperatureChart;
let pressureChart;
let historicalChart;
let temperaturePredictionChart;
let pressurePredictionChart;

// Current page
let currentPage = 'dashboard';

// Pagination for alerts
let alertsOffset = 0;
let alertsLimit = 10;
let totalAlerts = 0;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Initialize charts
    initializeCharts();
    
    // Set up navigation
    setupNavigation();
    
    // Set up data refresh
    setupDataRefresh();
    
    // Set up valve controls
    setupValveControls();
    
    // Load initial data
    loadDashboardData();
});

function initializeCharts() {
    // Temperature chart
    const tempCtx = document.getElementById('temperature-chart').getContext('2d');
    temperatureChart = new Chart(tempCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Temperature (°C)',
                data: [],
                borderColor: '#0dcaf0',
                backgroundColor: 'rgba(13, 202, 240, 0.1)',
                borderWidth: 2,
                tension: 0.3,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: false
                },
                x: {
                    reverse: true
                }
            }
        }
    });
    
    // Pressure chart
    const pressureCtx = document.getElementById('pressure-chart').getContext('2d');
    pressureChart = new Chart(pressureCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Pressure (kPa)',
                data: [],
                borderColor: '#fd7e14',
                backgroundColor: 'rgba(253, 126, 20, 0.1)',
                borderWidth: 2,
                tension: 0.3,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: false
                },
                x: {
                    reverse: true
                }
            }
        }
    });
    
    // Historical chart (will be configured when loaded)
    const histCtx = document.getElementById('historical-chart').getContext('2d');
    historicalChart = new Chart(histCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Sensor Data',
                data: [],
                borderColor: '#0dcaf0',
                backgroundColor: 'rgba(13, 202, 240, 0.1)',
                borderWidth: 2,
                tension: 0.3,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: false
                },
                x: {
                    reverse: true
                }
            }
        }
    });
    
    // Temperature prediction chart
    const tempPredictionCtx = document.getElementById('temp-prediction-chart').getContext('2d');
    temperaturePredictionChart = new Chart(tempPredictionCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Historical',
                    data: [],
                    borderColor: '#0dcaf0',
                    backgroundColor: 'rgba(13, 202, 240, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: false
                },
                {
                    label: 'Predictions',
                    data: [],
                    borderColor: '#20c997',
                    backgroundColor: 'rgba(32, 201, 151, 0.1)',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    tension: 0.3,
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });
    
    // Pressure prediction chart
    const pressurePredictionCtx = document.getElementById('pressure-prediction-chart').getContext('2d');
    pressurePredictionChart = new Chart(pressurePredictionCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [
                {
                    label: 'Historical',
                    data: [],
                    borderColor: '#fd7e14',
                    backgroundColor: 'rgba(253, 126, 20, 0.1)',
                    borderWidth: 2,
                    tension: 0.3,
                    fill: false
                },
                {
                    label: 'Predictions',
                    data: [],
                    borderColor: '#ffc107',
                    backgroundColor: 'rgba(255, 193, 7, 0.1)',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    tension: 0.3,
                    fill: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false
        }
    });
}

function setupNavigation() {
    // Handle navigation clicks
    document.querySelectorAll('[data-page]').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const page = e.target.getAttribute('data-page');
            showPage(page);
        });
    });
    
    // Historical data controls
    document.getElementById('refresh-historical-btn').addEventListener('click', () => {
        loadHistoricalData();
    });
    
    // Alerts controls
    document.getElementById('refresh-alerts-btn').addEventListener('click', () => {
        alertsOffset = 0;
        loadAlertsData();
    });
    
    document.getElementById('prev-alerts-btn').addEventListener('click', () => {
        if (alertsOffset >= alertsLimit) {
            alertsOffset -= alertsLimit;
            loadAlertsData(alertsOffset);
        }
    });
    
    document.getElementById('next-alerts-btn').addEventListener('click', () => {
        if (alertsOffset + alertsLimit < totalAlerts) {
            alertsOffset += alertsLimit;
            loadAlertsData(alertsOffset);
        }
    });
}

function showPage(pageName) {
    // Hide all pages
    document.querySelectorAll('.page').forEach(page => {
        page.style.display = 'none';
    });
    
    // Show selected page
    document.getElementById(`${pageName}-page`).style.display = 'block';
    
    // Highlight active nav link
    document.querySelectorAll('[data-page]').forEach(link => {
        link.classList.remove('active');
    });
    document.querySelector(`[data-page="${pageName}"]`).classList.add('active');
    
    // Set current page
    currentPage = pageName;
    
    // Load page-specific data
    if (pageName === 'dashboard') {
        loadDashboardData();
    } else if (pageName === 'historical') {
        loadHistoricalData();
    } else if (pageName === 'analytics') {
        loadAnalyticsData();
    } else if (pageName === 'controls') {
        loadControlsData();
    } else if (pageName === 'alerts') {
        loadAlertsData();
    }
}

function setupDataRefresh() {
    // Refresh data every 10 seconds
    setInterval(() => {
        if (currentPage === 'dashboard') {
            loadDashboardData();
        } else if (currentPage === 'controls') {
            loadControlsData();
        }
    }, 10000);
}

function setupValveControls() {
    // Open valve button
    document.getElementById('open-valve-btn').addEventListener('click', () => {
        const reason = document.getElementById('valve-reason').value || 'Manual control via dashboard';
        controlValve('open', reason);
    });
    
    // Close valve button
    document.getElementById('close-valve-btn').addEventListener('click', () => {
        const reason = document.getElementById('valve-reason').value || 'Manual control via dashboard';
        controlValve('closed', reason);
    });
}

function loadDashboardData() {
    // Get latest sensor data
    fetch('/api/sensor_data/latest')
        .then(response => response.json())
        .then(data => {
            updateCurrentReadings(data);
        })
        .catch(error => {
            console.error('Error fetching latest sensor data:', error);
            updateConnectionStatus(false);
        });
    
    // Get system status
    fetch('/api/system_status')
        .then(response => response.json())
        .then(data => {
            updateSystemStatus(data);
            updateConnectionStatus(true);
        })
        .catch(error => {
            console.error('Error fetching system status:', error);
            updateConnectionStatus(false);
        });
    
    // Get temperature data for chart
    fetch('/api/sensor_data/historical?type=temperature&hours=1&limit=30')
        .then(response => response.json())
        .then(data => {
            updateTemperatureChart(data);
        })
        .catch(error => {
            console.error('Error fetching temperature data:', error);
        });
    
    // Get pressure data for chart
    fetch('/api/sensor_data/historical?type=pressure&hours=1&limit=30')
        .then(response => response.json())
        .then(data => {
            updatePressureChart(data);
        })
        .catch(error => {
            console.error('Error fetching pressure data:', error);
        });
}

function updateCurrentReadings(data) {
    if (!data || !data.data) return;
    
    // Update temperature reading
    const tempData = data.data.temperature;
    if (tempData && tempData.value !== undefined) {
        const tempValue = parseFloat(tempData.value).toFixed(1);
        document.getElementById('temperature-reading').textContent = `${tempValue} °C`;
        
        // Update trend indicator based on thresholds
        updateTrendIndicator('temperature-trend', tempValue, 35, 15);
    }
    
    // Update pressure reading
    const pressureData = data.data.pressure;
    if (pressureData && pressureData.value !== undefined) {
        const pressureValue = parseFloat(pressureData.value).toFixed(1);
        document.getElementById('pressure-reading').textContent = `${pressureValue} kPa`;
        
        // Update trend indicator based on thresholds
        updateTrendIndicator('pressure-trend', pressureValue, 110, 90);
    }
}

function updateTrendIndicator(elementId, value, highThreshold, lowThreshold) {
    const element = document.getElementById(elementId);
    
    if (value > highThreshold) {
        element.innerHTML = '&#9650;'; // Up arrow
        element.style.color = 'var(--bs-danger)';
    } else if (value < lowThreshold) {
        element.innerHTML = '&#9660;'; // Down arrow
        element.style.color = 'var(--bs-warning)';
    } else {
        element.innerHTML = '&#9679;'; // Circle (normal)
        element.style.color = 'var(--bs-success)';
    }
}

function updateSystemStatus(data) {
    if (!data) return;
    
    // Update valve status
    const valveState = data.valve_state || 'unknown';
    const valveElement = document.getElementById('valve-status');
    valveElement.textContent = valveState;
    valveElement.className = `badge badge-${valveState.toLowerCase()}`;
    
    // Update system state
    const systemState = data.system_state || 'unknown';
    const systemElement = document.getElementById('system-state');
    systemElement.textContent = systemState;
    systemElement.className = `badge badge-${systemState.toLowerCase()}`;
    
    // Update services status
    if (data.services) {
        for (const [service, status] of Object.entries(data.services)) {
            updateServiceStatus(`service-${service}`, status);
        }
    }
}

function updateServiceStatus(elementId, status) {
    const element = document.getElementById(elementId);
    if (element) {
        element.textContent = status;
        element.className = `badge badge-${status.toLowerCase()}`;
    }
}

function updateConnectionStatus(connected) {
    const element = document.getElementById('connection-status');
    
    if (connected) {
        element.textContent = 'Connected';
        element.className = 'badge bg-success';
    } else {
        element.textContent = 'Disconnected';
        element.className = 'badge bg-danger';
    }
}

function updateTemperatureChart(data) {
    if (!data || !data.data) return;
    
    const chartData = data.data.map(item => ({
        x: new Date(item.timestamp),
        y: parseFloat(item.value)
    }));
    
    // Sort by timestamp (oldest first for proper display)
    chartData.sort((a, b) => a.x - b.x);
    
    // Extract labels and values
    const labels = chartData.map(item => {
        const date = new Date(item.x);
        return date.toLocaleTimeString();
    });
    
    const values = chartData.map(item => item.y);
    
    // Update chart
    temperatureChart.data.labels = labels;
    temperatureChart.data.datasets[0].data = values;
    temperatureChart.update();
}

function updatePressureChart(data) {
    if (!data || !data.data) return;
    
    const chartData = data.data.map(item => ({
        x: new Date(item.timestamp),
        y: parseFloat(item.value)
    }));
    
    // Sort by timestamp (oldest first for proper display)
    chartData.sort((a, b) => a.x - b.x);
    
    // Extract labels and values
    const labels = chartData.map(item => {
        const date = new Date(item.x);
        return date.toLocaleTimeString();
    });
    
    const values = chartData.map(item => item.y);
    
    // Update chart
    pressureChart.data.labels = labels;
    pressureChart.data.datasets[0].data = values;
    pressureChart.update();
}

function loadHistoricalData() {
    const sensorType = document.getElementById('sensor-type-select').value;
    const timeRange = document.getElementById('time-range-select').value;
    
    fetch(`/api/sensor_data/historical?type=${sensorType}&hours=${timeRange}&limit=100`)
        .then(response => response.json())
        .then(data => {
            updateHistoricalChart(data, sensorType);
            updateDataTable(data, sensorType);
        })
        .catch(error => {
            console.error(`Error fetching historical ${sensorType} data:`, error);
        });
}

function updateHistoricalChart(data, sensorType) {
    if (!data || !data.data) return;
    
    const chartData = data.data.map(item => ({
        x: new Date(item.timestamp),
        y: parseFloat(item.value)
    }));
    
    // Sort by timestamp (oldest first for proper display)
    chartData.sort((a, b) => a.x - b.x);
    
    // Extract labels and values
    const labels = chartData.map(item => {
        const date = new Date(item.x);
        return date.toLocaleTimeString();
    });
    
    const values = chartData.map(item => item.y);
    
    // Configure chart appearance based on sensor type
    let borderColor = '#0dcaf0';
    let backgroundColor = 'rgba(13, 202, 240, 0.1)';
    let label = 'Temperature (°C)';
    
    if (sensorType === 'pressure') {
        borderColor = '#fd7e14';
        backgroundColor = 'rgba(253, 126, 20, 0.1)';
        label = 'Pressure (kPa)';
    }
    
    // Update chart
    historicalChart.data.labels = labels;
    historicalChart.data.datasets[0].data = values;
    historicalChart.data.datasets[0].label = label;
    historicalChart.data.datasets[0].borderColor = borderColor;
    historicalChart.data.datasets[0].backgroundColor = backgroundColor;
    historicalChart.update();
}

function updateDataTable(data, sensorType) {
    if (!data || !data.data) return;
    
    const tableBody = document.querySelector('#data-table tbody');
    
    // Clear existing rows
    tableBody.innerHTML = '';
    
    if (data.data.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = `<td colspan="3" class="text-center">No data available</td>`;
        tableBody.appendChild(row);
        return;
    }
    
    // Sort data by timestamp (newest first)
    const sortedData = [...data.data].sort((a, b) => {
        const dateA = new Date(a.timestamp);
        const dateB = new Date(b.timestamp);
        return dateB - dateA;
    });
    
    // Add rows for each data point
    sortedData.forEach(item => {
        const timestamp = new Date(item.timestamp);
        const value = parseFloat(item.value).toFixed(2);
        const sensorId = item.tags?.sensor_id || 'unknown';
        const unit = sensorType === 'temperature' ? '°C' : 'kPa';
        
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${timestamp.toLocaleString()}</td>
            <td>${value} ${unit}</td>
            <td>${sensorId}</td>
        `;
        
        tableBody.appendChild(row);
    });
}

function loadAnalyticsData() {
    fetch('/api/analytics')
        .then(response => response.json())
        .then(data => {
            updateAnalyticsDisplay(data);
        })
        .catch(error => {
            console.error('Error fetching analytics data:', error);
        });
}

function updateAnalyticsDisplay(data) {
    if (!data) return;
    
    // Update temperature analytics
    if (data.temperature) {
        const temp = data.temperature;
        document.getElementById('temp-analytics-current').textContent = `${parseFloat(temp.current_value).toFixed(1)} °C`;
        
        const tempStatus = document.getElementById('temp-analytics-status');
        tempStatus.textContent = temp.status || 'normal';
        tempStatus.className = `badge badge-${temp.status || 'normal'}`;
        
        document.getElementById('temp-high-threshold').textContent = temp.high_threshold || '--';
        document.getElementById('temp-low-threshold').textContent = temp.low_threshold || '--';
    }
    
    // Update pressure analytics
    if (data.pressure) {
        const pressure = data.pressure;
        document.getElementById('pressure-analytics-current').textContent = `${parseFloat(pressure.current_value).toFixed(1)} kPa`;
        
        const pressureStatus = document.getElementById('pressure-analytics-status');
        pressureStatus.textContent = pressure.status || 'normal';
        pressureStatus.className = `badge badge-${pressure.status || 'normal'}`;
        
        document.getElementById('pressure-high-threshold').textContent = pressure.high_threshold || '--';
        document.getElementById('pressure-low-threshold').textContent = pressure.low_threshold || '--';
    }
    
    // Update prediction charts
    if (data.predictions) {
        // Temperature predictions
        if (data.predictions.temperature) {
            const tempPredictions = data.predictions.temperature;
            
            // Generate labels
            const labels = [];
            for (let i = 0; i < tempPredictions.length; i++) {
                labels.push(`Pred ${i+1}`);
            }
            
            // Update chart with existing data and predictions
            updatePredictionChart(
                temperaturePredictionChart, 
                data.temperature?.recent_data || [], 
                tempPredictions,
                'temperature'
            );
        }
        
        // Pressure predictions
        if (data.predictions.pressure) {
            const pressurePredictions = data.predictions.pressure;
            
            // Update chart with existing data and predictions
            updatePredictionChart(
                pressurePredictionChart, 
                data.pressure?.recent_data || [], 
                pressurePredictions,
                'pressure'
            );
        }
    }
}

function updatePredictionChart(chart, historicalData, predictions, sensorType) {
    // Create labels for historical data (times)
    const historicalLabels = [];
    for (let i = 0; i < historicalData.length; i++) {
        historicalLabels.push(`t-${historicalData.length - i}`);
    }
    
    // Create labels for predictions
    const predictionLabels = [];
    for (let i = 0; i < predictions.length; i++) {
        predictionLabels.push(`t+${i+1}`);
    }
    
    // Combine labels
    const labels = [...historicalLabels, ...predictionLabels];
    
    // Set up data for the datasets
    const historicalValues = historicalData;
    const predictionValues = new Array(historicalData.length).fill(null).concat(predictions);
    
    // Update chart
    chart.data.labels = labels;
    chart.data.datasets[0].data = [...historicalValues, ...new Array(predictions.length).fill(null)];
    chart.data.datasets[1].data = predictionValues;
    
    // Update title based on sensor type
    chart.options.plugins = chart.options.plugins || {};
    chart.options.plugins.title = chart.options.plugins.title || {};
    chart.options.plugins.title.text = sensorType === 'temperature' ? 'Temperature Forecast' : 'Pressure Forecast';
    
    chart.update();
}

function loadControlsData() {
    fetch('/api/system_status')
        .then(response => response.json())
        .then(data => {
            // Update valve status
            const valveState = data.valve_state || 'unknown';
            const valveElement = document.getElementById('control-valve-status');
            valveElement.textContent = valveState;
            valveElement.className = `badge badge-${valveState.toLowerCase()}`;
            
            // Update system state
            const systemState = data.system_state || 'unknown';
            const systemElement = document.getElementById('controls-system-state');
            systemElement.textContent = systemState;
            systemElement.className = `badge badge-${systemState.toLowerCase()}`;
            
            // Update last updated timestamp
            const lastUpdated = new Date(data.timestamp);
            document.getElementById('controls-last-updated').textContent = lastUpdated.toLocaleString();
            
            // Update sensor readings
            if (data.sensors) {
                if (data.sensors.temperature) {
                    document.getElementById('controls-temperature').textContent = 
                        `${parseFloat(data.sensors.temperature.value).toFixed(1)} °C`;
                }
                
                if (data.sensors.pressure) {
                    document.getElementById('controls-pressure').textContent = 
                        `${parseFloat(data.sensors.pressure.value).toFixed(1)} kPa`;
                }
            }
        })
        .catch(error => {
            console.error('Error fetching control data:', error);
        });
}

function loadAlertsData(offset = 0) {
    fetch(`/api/alerts/recent?limit=${alertsLimit}&offset=${offset}`)
        .then(response => response.json())
        .then(data => {
            updateAlertsTable(data.alerts || []);
            
            // Update pagination
            totalAlerts = data.total || data.alerts.length;
            document.getElementById('prev-alerts-btn').disabled = offset === 0;
            document.getElementById('next-alerts-btn').disabled = offset + alertsLimit >= totalAlerts;
        })
        .catch(error => {
            console.error('Error fetching alerts:', error);
        });
}

function updateAlertsTable(alerts) {
    const tableBody = document.querySelector('#alerts-table tbody');
    
    // Clear existing rows
    tableBody.innerHTML = '';
    
    if (!alerts || alerts.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = `<td colspan="4" class="text-center">No alerts found</td>`;
        tableBody.appendChild(row);
        return;
    }
    
    // Add rows for each alert
    alerts.forEach(alert => {
        const timestamp = new Date(alert.timestamp);
        const type = alert.type || 'unknown';
        const message = alert.message || 'No message';
        const details = alert.data ? JSON.stringify(alert.data) : 'No details';
        
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${timestamp.toLocaleString()}</td>
            <td><span class="badge bg-danger">${type}</span></td>
            <td>${message}</td>
            <td><pre class="m-0 small">${details}</pre></td>
        `;
        
        tableBody.appendChild(row);
    });
}

function controlValve(state, reason) {
    const data = {
        state: state,
        reason: reason
    };
    
    fetch('/api/valve/control', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    .then(response => response.json())
    .then(data => {
        // Reload controls data
        loadControlsData();
        
        // Clear reason field
        document.getElementById('valve-reason').value = '';
        
        // Alert success
        alert(`Valve ${state} successfully`);
    })
    .catch(error => {
        console.error('Error controlling valve:', error);
        alert(`Error: Failed to ${state} valve. Please try again.`);
    });
}""")
    
    def get_service_url(self, service_type, service_name=None):
        """Get the service URL from the Resource Catalog with fallback options"""
        # Check cache first
        cache_key = f"{service_type}:{service_name}" if service_name else service_type
        cache_ttl = 60  # Cache TTL in seconds
        current_time = datetime.now().timestamp()
        
        # Return from cache if valid
        if cache_key in self.service_cache:
            cache_data = self.service_cache[cache_key]
            if current_time - cache_data["timestamp"] < cache_ttl:
                return cache_data["url"]
            else:
                # Expired cache entry
                logger.debug(f"Cache expired for {cache_key}")
        
        # Option 1: Try direct environment variable
        env_var_name = f"{service_type.upper()}_URL"
        env_url = os.environ.get(env_var_name)
        if env_url:
            logger.debug(f"Using environment variable for {service_type}: {env_url}")
            self.service_cache[cache_key] = {
                "url": env_url,
                "timestamp": current_time
            }
            return env_url
        
        # Option 2: Get from Resource Catalog
        try:
            service = common_utils.discover_service(service_type)
            
            if service and service.get("base_url"):
                url = service.get("base_url")
                logger.debug(f"Discovered {service_type} from Resource Catalog: {url}")
                self.service_cache[cache_key] = {
                    "url": url,
                    "timestamp": current_time
                }
                return url
        except Exception as e:
            logger.warning(f"Error discovering service {service_type}: {e}")
        
        # Option 3: Return default URL if service not found
        default_port = DEFAULT_SERVICE_PORTS.get(service_type, 8000)
        default_url = f"http://localhost:{default_port}"
        logger.warning(f"Using default URL for {service_type}: {default_url}")
        self.service_cache[cache_key] = {
            "url": default_url,
            "timestamp": current_time
        }
        return default_url
    
    def get_latest_data(self):
        """Get the latest sensor data with robust error handling"""
        try:
            # Get Time Series DB service URL
            service_url = self.get_service_url("time_series_db")
            
            # Get latest data
            logger.debug(f"Requesting latest data from {service_url}/latest")
            response = requests.get(f"{service_url}/latest", timeout=REQUEST_TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                logger.debug("Successfully retrieved latest sensor data")
                return data
            else:
                logger.error(f"Failed to get latest data: {response.status_code} - {response.text}")
                return {
                    "status": "error",
                    "message": f"Failed to get latest data: HTTP {response.status_code}",
                    "timestamp": datetime.now().isoformat(),
                    "data": {}
                }
        
        except requests.exceptions.Timeout:
            logger.error("Timeout getting latest data")
            return {
                "status": "error",
                "message": "Request timeout",
                "timestamp": datetime.now().isoformat(),
                "data": {}
            }
        except requests.exceptions.ConnectionError:
            logger.error("Connection error getting latest data")
            return {
                "status": "error", 
                "message": "Connection error - service may be unavailable",
                "timestamp": datetime.now().isoformat(),
                "data": {}
            }
        except Exception as e:
            logger.error(f"Error getting latest data: {e}")
            return {
                "status": "error",
                "message": str(e),
                "timestamp": datetime.now().isoformat(),
                "data": {}
            }
    
    def get_historical_data(self, sensor_type, hours=1, limit=100):
        """Get historical sensor data"""
        try:
            # Get Time Series DB service URL
            service_url = self.get_service_url("time_series_db")
            
            # Get historical data
            response = requests.get(
                f"{service_url}/{sensor_type}?hours={hours}&limit={limit}",
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get historical data: {response.text}")
                return {
                    "timestamp": datetime.now().isoformat(),
                    "data": []
                }
        
        except Exception as e:
            logger.error(f"Error getting historical data: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "data": []
            }
    
    def get_system_status(self):
        """Get the overall system status"""
        try:
            # Get Control Center service URL
            service_url = self.get_service_url("control_center")
            
            # Get system status
            response = requests.get(f"{service_url}/status", timeout=5)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get system status: {response.text}")
                return {
                    "timestamp": datetime.now().isoformat(),
                    "valve_state": "unknown",
                    "system_state": "unknown",
                    "services": {}
                }
        
        except Exception as e:
            logger.error(f"Error getting system status: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "valve_state": "unknown",
                "system_state": "unknown",
                "services": {}
            }
    
    def get_analytics_data(self):
        """Get analytics and predictions"""
        try:
            # Get Analytics service URL
            service_url = self.get_service_url("analytics")
            
            # Get analytics data
            response = requests.get(f"{service_url}/analysis", timeout=5)
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to get analytics data: {response.text}")
                return {
                    "timestamp": datetime.now().isoformat(),
                    "temperature": {},
                    "pressure": {},
                    "predictions": {
                        "temperature": [],
                        "pressure": []
                    }
                }
        
        except Exception as e:
            logger.error(f"Error getting analytics data: {e}")
            return {
                "timestamp": datetime.now().isoformat(),
                "temperature": {},
                "pressure": {},
                "predictions": {
                    "temperature": [],
                    "pressure": []
                }
            }
    
    def control_valve(self, state, reason="Manual control via dashboard"):
        """Control the valve state"""
        try:
            # Get Control Center service URL
            service_url = self.get_service_url("control_center")
            
            # Send control command
            response = requests.post(
                f"{service_url}/valve",
                json={
                    "state": state,
                    "reason": reason
                },
                timeout=5
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Failed to control valve: {response.text}")
                return {
                    "status": "error",
                    "message": "Failed to control valve"
                }
        
        except Exception as e:
            logger.error(f"Error controlling valve: {e}")
            return {
                "status": "error",
                "message": str(e)
            }

class DashboardAPI:
    """CherryPy handler for Dashboard API endpoints"""
    
    def __init__(self, dashboard):
        """Initialize with dashboard instance"""
        self.dashboard = dashboard
    
    def _check_auth(self):
        """Check if user is authenticated"""
        if not cherrypy.session.get('authenticated', False):
            cherrypy.response.status = 401
            return False
        return True
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def index(self):
        """GET /api - API documentation"""
        if cherrypy.request.method != 'GET':
            cherrypy.response.status = 405
            return {"status": "error", "message": "Method not allowed"}
        
        return {
            "name": SERVICE_NAME,
            "version": "1.0.0",
            "description": "Web Dashboard API for monitoring and control",
            "endpoints": [
                {"path": "/api", "methods": ["GET"], "description": "API documentation"},
                {"path": "/api/health", "methods": ["GET"], "description": "Health check endpoint"},
                {"path": "/api/sensor_data", "methods": ["GET"], "description": "Get historical sensor data", "auth_required": True},
                {"path": "/api/sensor_data/latest", "methods": ["GET"], "description": "Get latest sensor data", "auth_required": True},
                {"path": "/api/system_status", "methods": ["GET"], "description": "Get system status", "auth_required": True},
                {"path": "/api/analytics", "methods": ["GET"], "description": "Get analytics data", "auth_required": True},
                {"path": "/api/valve", "methods": ["POST", "PUT"], "description": "Control valve", "auth_required": True},
                {"path": "/api/alerts", "methods": ["GET"], "description": "Get system alerts", "auth_required": True},
                {"path": "/api/user", "methods": ["GET"], "description": "Get current user information", "auth_required": True}
            ]
        }
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def health(self):
        """GET /api/health - Health check endpoint"""
        if cherrypy.request.method != 'GET':
            cherrypy.response.status = 405
            return {"status": "error", "message": "Method not allowed"}
        
        # Check connections to required services
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "services": {}
        }
        
        # Check Time Series DB connection
        try:
            service_url = self.dashboard.get_service_url("time_series_db")
            response = requests.get(f"{service_url}/health", timeout=2)
            if response.status_code == 200:
                health_status["services"]["time_series_db"] = "available"
            else:
                health_status["services"]["time_series_db"] = f"error: HTTP {response.status_code}"
                health_status["status"] = "degraded"
        except Exception as e:
            health_status["services"]["time_series_db"] = f"error: {str(e)}"
            health_status["status"] = "degraded"
        
        # Check Control Center connection
        try:
            service_url = self.dashboard.get_service_url("control_center")
            response = requests.get(f"{service_url}/health", timeout=2)
            if response.status_code == 200:
                health_status["services"]["control_center"] = "available"
            else:
                health_status["services"]["control_center"] = f"error: HTTP {response.status_code}"
                health_status["status"] = "degraded"
        except Exception as e:
            health_status["services"]["control_center"] = f"error: {str(e)}"
            health_status["status"] = "degraded"
        
        return health_status
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def sensor_data(self, **kwargs):
        """
        GET /api/sensor_data - Get sensor data
        Options:
          - latest: bool - Get latest data only
          - type: string - Sensor type (temperature, pressure)
          - hours: int - Hours of historical data
          - limit: int - Maximum number of data points
        """
        if cherrypy.request.method != 'GET':
            cherrypy.response.status = 405
            return {"status": "error", "message": "Method not allowed"}
        
        # Check authentication
        if not self._check_auth():
            return {"status": "error", "message": "Unauthorized"}
        
        # Check for latest flag
        if kwargs.get('latest', False) or cherrypy.request.path_info.endswith('/latest'):
            return self.dashboard.get_latest_data()
        
        # Handle historical data request
        sensor_type = kwargs.get('type', 'temperature')
        try:
            hours = int(kwargs.get('hours', 1))
            limit = int(kwargs.get('limit', 100))
        except ValueError:
            cherrypy.response.status = 400
            return {"status": "error", "message": "Invalid parameters"}
        
        return self.dashboard.get_historical_data(sensor_type, hours, limit)
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def system_status(self):
        """GET /api/system_status - Get system status"""
        if cherrypy.request.method != 'GET':
            cherrypy.response.status = 405
            return {"status": "error", "message": "Method not allowed"}
        
        return self.dashboard.get_system_status()
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def analytics(self):
        """GET /api/analytics - Get analytics data"""
        if cherrypy.request.method != 'GET':
            cherrypy.response.status = 405
            return {"status": "error", "message": "Method not allowed"}
        
        return self.dashboard.get_analytics_data()
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def valve(self):
        """
        POST /api/valve - Control the valve
        PUT /api/valve - Control the valve (alternative)
        """
        allowed_methods = ['POST', 'PUT']
        if cherrypy.request.method not in allowed_methods:
            cherrypy.response.status = 405
            return {"status": "error", "message": "Method not allowed"}
        
        try:
            data = json.loads(cherrypy.request.body.read().decode('utf-8'))
            state = data.get('state')
            reason = data.get('reason', 'Manual control via dashboard')
            
            if not state:
                cherrypy.response.status = 400
                return {"status": "error", "message": "Missing valve state"}
            
            if state not in ['open', 'closed']:
                cherrypy.response.status = 400
                return {"status": "error", "message": "Invalid valve state. Use 'open' or 'closed'"}
            
            result = self.dashboard.control_valve(state, reason)
            return result
        
        except json.JSONDecodeError:
            cherrypy.response.status = 400
            return {"status": "error", "message": "Invalid JSON payload"}
        
        except Exception as e:
            cherrypy.response.status = 500
            return {"status": "error", "message": str(e)}
    
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def alerts(self, **kwargs):
        """
        GET /api/alerts - Get system alerts
        Options:
          - limit: int - Maximum number of alerts
          - offset: int - Pagination offset
        """
        if cherrypy.request.method != 'GET':
            cherrypy.response.status = 405
            return {"status": "error", "message": "Method not allowed"}
        
        try:
            limit = int(kwargs.get('limit', 10))
            offset = int(kwargs.get('offset', 0))
        except ValueError:
            cherrypy.response.status = 400
            return {"status": "error", "message": "Invalid parameters"}
            
        # Demo data for alerts
        # In a real implementation, this would fetch from a backend service
        alerts = [
            {
                "timestamp": datetime.now().isoformat(),
                "type": "system",
                "message": "Demo alert",
                "data": {"value": 42}
            }
        ]
        
        return {
            "status": "success",
            "total": len(alerts),
            "limit": limit,
            "offset": offset,
            "alerts": alerts
        }

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def user(self):
        """GET /api/user - Get current user information"""
        if cherrypy.request.method != 'GET':
            cherrypy.response.status = 405
            return {"status": "error", "message": "Method not allowed"}
        
        # Check authentication
        if not self._check_auth():
            return {"status": "error", "message": "Unauthorized"}
        
        # Return user information from session
        return {
            "status": "success",
            "user": {
                "id": cherrypy.session.get('user_id'),
                "username": cherrypy.session.get('username'),
                "authenticated": True
            }
        }

class DashboardWeb:
    """CherryPy handler for Dashboard web interface"""
    
    def __init__(self, dashboard):
        """Initialize with dashboard instance"""
        self.dashboard = dashboard
    
    @cherrypy.expose
    def index(self, page=None):
        """Main dashboard page"""
        # Check if user is logged in
        if not self._check_auth():
            raise cherrypy.HTTPRedirect("/login")
            
        # Read HTML template
        try:
            with open(os.path.join(TEMPLATE_DIR, "index.html"), "r") as f:
                html = f.read()
                # Replace template variables with actual values
                html = html.replace("{{ page_title }}", "Smart IoT Bolt Dashboard")
                return html
        except Exception as e:
            return f"Error loading dashboard: {str(e)}"
            
    def _check_auth(self):
        """Check if user is authenticated"""
        return cherrypy.session.get('authenticated', False)
            
    @cherrypy.expose
    def dashboard(self, page=None):
        """Dashboard route - redirects to index"""
        return self.index(page)
    
    @cherrypy.expose
    def login(self, username=None, password=None, **kwargs):
        """Login page"""
        error_msg = None
        
        # Process login form submission
        if username and password:
            try:
                # Get Account Manager service URL
                account_manager_url = self.dashboard.get_service_url("account_manager")
                
                # Attempt to authenticate
                response = requests.post(
                    f"{account_manager_url}/auth/login",
                    json={"username": username, "password": password},
                    timeout=REQUEST_TIMEOUT
                )
                
                if response.status_code == 200:
                    # Authentication successful
                    auth_data = response.json()
                    
                    # Store authentication data in session
                    cherrypy.session['authenticated'] = True
                    cherrypy.session['user_id'] = auth_data.get('user_id')
                    cherrypy.session['username'] = username
                    cherrypy.session['auth_token'] = auth_data.get('token')
                    
                    # Redirect to dashboard
                    raise cherrypy.HTTPRedirect("/")
                else:
                    # Authentication failed
                    error_msg = "Invalid username or password"
                    logger.warning(f"Failed login attempt for user {username}")
            except requests.exceptions.RequestException as e:
                error_msg = "Authentication service unavailable"
                logger.error(f"Error connecting to Account Manager: {e}")
        
        # Render login page
        return f"""
        <html data-bs-theme="dark">
        <head>
            <title>Login - Smart IoT Bolt</title>
            <link rel="stylesheet" href="https://cdn.replit.com/agent/bootstrap-agent-dark-theme.min.css">
            <style>
                body {{
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    height: 100vh;
                    background-color: #1c1e22;
                }}
                .login-container {{
                    max-width: 400px;
                    width: 100%;
                    padding: 20px;
                }}
                .login-logo {{
                    text-align: center;
                    margin-bottom: 30px;
                }}
                .login-logo h1 {{
                    font-weight: bold;
                    color: #0dcaf0;
                }}
                .error-message {{
                    color: #dc3545;
                    margin-bottom: 15px;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <div class="login-container">
                <div class="login-logo">
                    <h1>Smart IoT Bolt</h1>
                    <p class="text-muted">Pipeline Monitoring System</p>
                </div>
                <div class="card">
                    <div class="card-body">
                        <h5 class="card-title">Log In</h5>
                        {f'<div class="error-message">{error_msg}</div>' if error_msg else ''}
                        <form method="post" action="/login">
                            <div class="mb-3">
                                <label for="username" class="form-label">Username</label>
                                <input type="text" class="form-control" id="username" name="username" required>
                            </div>
                            <div class="mb-3">
                                <label for="password" class="form-label">Password</label>
                                <input type="password" class="form-control" id="password" name="password" required>
                            </div>
                            <div class="d-grid">
                                <button type="submit" class="btn btn-primary">Login</button>
                            </div>
                        </form>
                    </div>
                </div>
                <div class="text-center mt-3">
                    <p class="text-muted small">Default login: admin / admin</p>
                </div>
            </div>
        </body>
        </html>
        """
    
    @cherrypy.expose
    def logout(self):
        """Logout and redirect to login page"""
        # Clear session
        cherrypy.session.pop('authenticated', None)
        cherrypy.session.pop('user_id', None)
        cherrypy.session.pop('username', None)
        cherrypy.session.pop('auth_token', None)
        
        # Redirect to login page
        raise cherrypy.HTTPRedirect("/login")

def main():
    """Main function with command line argument support"""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Web Dashboard Microservice")
    parser.add_argument("--host", dest="host", default=SERVICE_HOST,
                        help=f"Host to bind to (default: {SERVICE_HOST})")
    parser.add_argument("--port", dest="port", type=int, default=SERVICE_PORT,
                        help=f"Port to bind to (default: {SERVICE_PORT})")
    parser.add_argument("--debug", dest="debug", action="store_true",
                        help="Enable debug logging")
    args = parser.parse_args()
    
    # Configure logging level
    if args.debug:
        logger.setLevel(logging.DEBUG)
        cherrypy.log.error_log.setLevel(logging.DEBUG)
        logger.debug("Debug logging enabled")
    
    # Create dashboard
    dashboard = Dashboard()
    
    # Configure CherryPy
    cherrypy.config.update({
        'server.socket_host': args.host,
        'server.socket_port': args.port,
        'engine.autoreload.on': False,
        'log.screen': True
    })
    
    # Configure cherrypy with application settings
    app_config = {
        '/': {
            'tools.sessions.on': True,
            'tools.sessions.timeout': 60,
            'tools.staticdir.root': os.path.dirname(os.path.abspath(__file__))
        },
        '/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': 'static'
        }
    }
    
    # Create dashboard instances
    dashboard_web = DashboardWeb(dashboard)
    dashboard_api = DashboardAPI(dashboard)
    
    # Configure the application to mount different paths
    cherrypy.tree.mount(dashboard_web, '/', app_config)
    
    # Mount the API separately
    api_config = {
        '/': {
            'tools.sessions.on': True,
            'tools.sessions.timeout': 60,
            'request.dispatch': cherrypy.dispatch.MethodDispatcher()
        }
    }
    cherrypy.tree.mount(dashboard_api, '/api', api_config)
    
    # Start application
    logger.info(f"Starting Web Dashboard on {args.host}:{args.port}")
    cherrypy.engine.start()
    cherrypy.engine.block()

if __name__ == "__main__":
    main()
