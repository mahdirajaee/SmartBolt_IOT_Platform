// Smart IoT Bolt Dashboard JavaScript

// Initialize Feather icons
document.addEventListener('DOMContentLoaded', () => {
    // Initialize Feather icons
    feather.replace();
    
    // Initialize page navigation
    setupNavigation();
    
    // Initialize dashboard
    loadDashboardData();
    
    // Set up refresh intervals
    setupRefreshIntervals();
    
    // Set up valve controls
    setupValveControls();
});

// Page navigation
function setupNavigation() {
    // Dashboard link
    document.getElementById('dashboard-link').addEventListener('click', (e) => {
        e.preventDefault();
        showPage('dashboard');
    });
    
    // Historical data link
    document.getElementById('historical-link').addEventListener('click', (e) => {
        e.preventDefault();
        showPage('historical');
    });
    
    // Analytics link
    document.getElementById('analytics-link').addEventListener('click', (e) => {
        e.preventDefault();
        showPage('analytics');
    });
    
    // Controls link
    document.getElementById('controls-link').addEventListener('click', (e) => {
        e.preventDefault();
        showPage('controls');
    });
    
    // Alerts link
    document.getElementById('alerts-link').addEventListener('click', (e) => {
        e.preventDefault();
        showPage('alerts');
    });
    
    // View all alerts button
    const viewAllAlertsBtn = document.getElementById('view-all-alerts-btn');
    if (viewAllAlertsBtn) {
        viewAllAlertsBtn.addEventListener('click', (e) => {
            e.preventDefault();
            showPage('alerts');
        });
    }
    
    // Historical data fetch button
    const fetchDataBtn = document.getElementById('fetch-data-btn');
    if (fetchDataBtn) {
        fetchDataBtn.addEventListener('click', () => {
            loadHistoricalData();
        });
    }
}

// Show specific page
function showPage(pageId) {
    // Hide all pages
    document.querySelectorAll('.page-content').forEach(page => {
        page.classList.add('d-none');
    });
    
    // Show selected page
    document.getElementById(`${pageId}-page`).classList.remove('d-none');
    
    // Update active link
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.remove('active');
    });
    document.getElementById(`${pageId}-link`).classList.add('active');
    
    // Load page-specific data
    if (pageId === 'historical') {
        loadHistoricalData();
    } else if (pageId === 'analytics') {
        loadAnalyticsData();
    } else if (pageId === 'alerts') {
        loadAlertsData();
    } else if (pageId === 'controls') {
        loadControlsData();
    }
}

// Dashboard data loading
function loadDashboardData() {
    // Get latest sensor data
    fetch('/api/latest_data')
        .then(response => response.json())
        .then(data => {
            updateSensorReadings(data);
            updateDashboardCharts(data);
        })
        .catch(error => {
            console.error('Error fetching sensor data:', error);
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
    
    // Get recent alerts
    fetch('/api/alerts/recent?limit=3')
        .then(response => response.json())
        .then(data => {
            updateRecentAlerts(data);
        })
        .catch(error => {
            console.error('Error fetching alerts:', error);
        });
}

// Update sensor readings on dashboard
function updateSensorReadings(data) {
    if (!data || !data.data) return;
    
    const tempElement = document.getElementById('current-temperature');
    const pressureElement = document.getElementById('current-pressure');
    const valveElement = document.getElementById('current-valve');
    const tempTimestampElement = document.getElementById('temp-timestamp');
    const pressureTimestampElement = document.getElementById('pressure-timestamp');
    const valveTimestampElement = document.getElementById('valve-timestamp');
    
    // Update temperature
    if (data.data.temperature) {
        const temp = parseFloat(data.data.temperature.value).toFixed(1);
        tempElement.innerText = `${temp}°C`;
        tempTimestampElement.innerText = formatTimestamp(data.data.temperature.timestamp);
        
        // Update trend indicator
        const tempTrendElement = document.getElementById('temp-trend');
        if (temp > 35) {
            tempTrendElement.innerHTML = '<small class="text-danger">Above normal <i data-feather="arrow-up"></i></small>';
        } else if (temp < 15) {
            tempTrendElement.innerHTML = '<small class="text-warning">Below normal <i data-feather="arrow-down"></i></small>';
        } else {
            tempTrendElement.innerHTML = '<small class="text-success">Normal <i data-feather="check"></i></small>';
        }
    }
    
    // Update pressure
    if (data.data.pressure) {
        const pressure = parseFloat(data.data.pressure.value).toFixed(1);
        pressureElement.innerText = `${pressure} kPa`;
        pressureTimestampElement.innerText = formatTimestamp(data.data.pressure.timestamp);
        
        // Update trend indicator
        const pressureTrendElement = document.getElementById('pressure-trend');
        if (pressure > 110) {
            pressureTrendElement.innerHTML = '<small class="text-danger">Above normal <i data-feather="arrow-up"></i></small>';
        } else if (pressure < 90) {
            pressureTrendElement.innerHTML = '<small class="text-warning">Below normal <i data-feather="arrow-down"></i></small>';
        } else {
            pressureTrendElement.innerHTML = '<small class="text-success">Normal <i data-feather="check"></i></small>';
        }
    }
    
    // Update valve status
    if (data.data.valve) {
        const valveState = data.data.valve.state;
        valveElement.innerText = valveState.charAt(0).toUpperCase() + valveState.slice(1);
        valveElement.className = valveState === 'open' ? 'valve-open' : 'valve-closed';
        valveTimestampElement.innerText = formatTimestamp(data.data.valve.timestamp);
    }
    
    // Re-initialize Feather icons
    feather.replace();
}

// Update system status
function updateSystemStatus(data) {
    if (!data) return;
    
    const systemStatusElement = document.getElementById('system-status');
    const statusBadgeElement = document.getElementById('status-badge');
    
    if (data.system_state) {
        systemStatusElement.innerText = `System state: ${data.system_state}`;
        
        if (data.system_state === 'normal') {
            statusBadgeElement.innerText = 'Normal';
            statusBadgeElement.className = 'badge bg-success';
        } else if (data.system_state === 'warning') {
            statusBadgeElement.innerText = 'Warning';
            statusBadgeElement.className = 'badge bg-warning';
        } else if (data.system_state === 'critical') {
            statusBadgeElement.innerText = 'Critical';
            statusBadgeElement.className = 'badge bg-danger';
        } else {
            statusBadgeElement.innerText = data.system_state;
            statusBadgeElement.className = 'badge bg-secondary';
        }
    }
}

// Update connection status
function updateConnectionStatus(connected) {
    const statusBadgeElement = document.getElementById('status-badge');
    
    if (connected) {
        statusBadgeElement.innerText = 'Connected';
        statusBadgeElement.className = 'badge bg-success';
    } else {
        statusBadgeElement.innerText = 'Disconnected';
        statusBadgeElement.className = 'badge bg-danger';
    }
}

// Update recent alerts
function updateRecentAlerts(data) {
    const alertsContainer = document.getElementById('recent-alerts');
    const alertBadgeElement = document.getElementById('alert-badge');
    
    if (!data || !data.alerts || data.alerts.length === 0) {
        alertsContainer.innerHTML = '<p class="text-muted">No recent alerts</p>';
        alertBadgeElement.innerText = '0';
        return;
    }
    
    alertBadgeElement.innerText = data.alerts.length.toString();
    
    // Clear container
    alertsContainer.innerHTML = '';
    
    // Add alerts
    data.alerts.slice(0, 3).forEach(alert => {
        const alertItem = document.createElement('div');
        alertItem.className = 'alert-item';
        
        alertItem.innerHTML = `
            <div class="alert-title">${alert.message}</div>
            <div class="alert-time">${formatTimestamp(alert.timestamp)}</div>
        `;
        
        alertsContainer.appendChild(alertItem);
    });
}

// Set up refresh intervals
function setupRefreshIntervals() {
    // Refresh dashboard data every 10 seconds
    setInterval(loadDashboardData, 10000);
}

// Set up valve controls
function setupValveControls() {
    const openValveBtn = document.getElementById('open-valve-btn');
    const closeValveBtn = document.getElementById('close-valve-btn');
    
    if (openValveBtn) {
        openValveBtn.addEventListener('click', () => {
            controlValve('open');
        });
    }
    
    if (closeValveBtn) {
        closeValveBtn.addEventListener('click', () => {
            controlValve('closed');
        });
    }
}

// Control valve
function controlValve(state) {
    fetch('/api/valve/control', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            state: state,
            reason: `Manual control via dashboard button ${state}`
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            // Refresh dashboard data
            loadDashboardData();
        } else {
            alert(`Failed to ${state} valve: ${data.message}`);
        }
    })
    .catch(error => {
        console.error('Error controlling valve:', error);
        alert(`Error controlling valve: ${error.message}`);
    });
}

// Format timestamp
function formatTimestamp(timestamp) {
    if (!timestamp) return '--';
    
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
}

// Update dashboard charts
function updateDashboardCharts(data) {
    // Initialize temperature chart if not exists
    const tempCtx = document.getElementById('temperature-chart');
    if (tempCtx && !tempCtx.chart) {
        tempCtx.chart = new Chart(tempCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Temperature (°C)',
                    data: [],
                    borderColor: '#0dcaf0',
                    backgroundColor: 'rgba(13, 202, 240, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: false
                    }
                }
            }
        });
    }
    
    // Initialize pressure chart if not exists
    const pressureCtx = document.getElementById('pressure-chart');
    if (pressureCtx && !pressureCtx.chart) {
        pressureCtx.chart = new Chart(pressureCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Pressure (kPa)',
                    data: [],
                    borderColor: '#fd7e14',
                    backgroundColor: 'rgba(253, 126, 20, 0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        beginAtZero: false
                    }
                }
            }
        });
    }
    
    // Fetch historical data for charts
    fetch('/api/sensor_data/historical?type=temperature&hours=1&limit=20')
        .then(response => response.json())
        .then(data => {
            updateTemperatureChart(data);
        })
        .catch(error => {
            console.error('Error fetching temperature data:', error);
        });
    
    fetch('/api/sensor_data/historical?type=pressure&hours=1&limit=20')
        .then(response => response.json())
        .then(data => {
            updatePressureChart(data);
        })
        .catch(error => {
            console.error('Error fetching pressure data:', error);
        });
}

// Update temperature chart
function updateTemperatureChart(data) {
    const tempCtx = document.getElementById('temperature-chart');
    if (!tempCtx || !tempCtx.chart || !data || !data.data || data.data.length === 0) return;
    
    const chart = tempCtx.chart;
    const chartData = data.data.map(item => {
        return {
            x: new Date(item.timestamp),
            y: parseFloat(item.value)
        };
    });
    
    // Sort by timestamp
    chartData.sort((a, b) => a.x - b.x);
    
    // Update chart data
    chart.data.labels = chartData.map(item => formatTimestamp(item.x));
    chart.data.datasets[0].data = chartData.map(item => item.y);
    chart.update();
}

// Update pressure chart
function updatePressureChart(data) {
    const pressureCtx = document.getElementById('pressure-chart');
    if (!pressureCtx || !pressureCtx.chart || !data || !data.data || data.data.length === 0) return;
    
    const chart = pressureCtx.chart;
    const chartData = data.data.map(item => {
        return {
            x: new Date(item.timestamp),
            y: parseFloat(item.value)
        };
    });
    
    // Sort by timestamp
    chartData.sort((a, b) => a.x - b.x);
    
    // Update chart data
    chart.data.labels = chartData.map(item => formatTimestamp(item.x));
    chart.data.datasets[0].data = chartData.map(item => item.y);
    chart.update();
}

// Load historical data
function loadHistoricalData() {
    const sensorType = document.getElementById('sensor-select').value;
    const timeRange = document.getElementById('time-range').value;
    
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

// Update historical chart
function updateHistoricalChart(data, sensorType) {
    const histCtx = document.getElementById('historical-chart');
    if (!histCtx) return;
    
    // Destroy existing chart if it exists
    if (histCtx.chart) {
        histCtx.chart.destroy();
    }
    
    if (!data || !data.data || data.data.length === 0) {
        histCtx.getContext('2d').clearRect(0, 0, histCtx.width, histCtx.height);
        return;
    }
    
    const chartData = data.data.map(item => {
        return {
            x: new Date(item.timestamp),
            y: parseFloat(item.value)
        };
    });
    
    // Sort by timestamp
    chartData.sort((a, b) => a.x - b.x);
    
    // Create new chart
    histCtx.chart = new Chart(histCtx, {
        type: 'line',
        data: {
            labels: chartData.map(item => formatTimestamp(item.x)),
            datasets: [{
                label: sensorType === 'temperature' ? 'Temperature (°C)' : 'Pressure (kPa)',
                data: chartData.map(item => item.y),
                borderColor: sensorType === 'temperature' ? '#0dcaf0' : '#fd7e14',
                backgroundColor: sensorType === 'temperature' ? 'rgba(13, 202, 240, 0.1)' : 'rgba(253, 126, 20, 0.1)',
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: false
                }
            }
        }
    });
}

// Update data table
function updateDataTable(data, sensorType) {
    const tableBody = document.getElementById('data-table-body');
    if (!tableBody) return;
    
    // Clear table
    tableBody.innerHTML = '';
    
    if (!data || !data.data || data.data.length === 0) {
        tableBody.innerHTML = '<tr><td colspan="4" class="text-center">No data available</td></tr>';
        return;
    }
    
    // Sort by timestamp (newest first)
    const sortedData = [...data.data].sort((a, b) => {
        return new Date(b.timestamp) - new Date(a.timestamp);
    });
    
    // Add rows to table
    sortedData.forEach(item => {
        const tr = document.createElement('tr');
        
        tr.innerHTML = `
            <td>${formatTimestamp(item.timestamp)}</td>
            <td>${sensorType}</td>
            <td>${parseFloat(item.value).toFixed(2)}</td>
            <td>${sensorType === 'temperature' ? '°C' : 'kPa'}</td>
        `;
        
        tableBody.appendChild(tr);
    });
}