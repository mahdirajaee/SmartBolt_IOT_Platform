/**
 * Charts Module for Smart IoT Bolt Dashboard
 * Creates and updates chart visualizations for sensor data
 */

// Configuration
const CHART_DEFAULTS = {
    temperature: {
        min: 40,
        max: 100,
        warning: 85,
        critical: 95,
        unit: '°C'
    },
    pressure: {
        min: 4,
        max: 12,
        warning: 8.5,
        critical: 9.5,
        unit: 'bar'
    }
};

// Store chart instances for later reference
let charts = {};

/**
 * Initialize charts on the dashboard
 */
function initCharts() {
    // Create temperature chart
    createTemperatureChart();
    
    // Create pressure chart
    createPressureChart();
    
    // Initialize chart timeframe selectors
    initChartTimeframeSelectors();
}

/**
 * Create temperature chart
 */
function createTemperatureChart() {
    const ctx = document.getElementById('temperature-chart');
    
    if (!ctx) {
        console.warn('Temperature chart canvas not found');
        return;
    }
    
    // Show loading indicator
    const loadingIndicator = ctx.parentElement.querySelector('.chart-loading');
    if (loadingIndicator) {
        loadingIndicator.classList.add('show');
    }
    
    // Set up temperature chart
    const temperatureChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Temperature',
                data: [],
                borderColor: '#3b82f6',
                backgroundColor: 'rgba(59, 130, 246, 0.1)',
                borderWidth: 2,
                pointBackgroundColor: '#3b82f6',
                pointRadius: 2,
                pointHoverRadius: 4,
                tension: 0.2,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `Temperature: ${context.parsed.y}${CHART_DEFAULTS.temperature.unit}`;
                        }
                    }
                },
                annotation: {
                    annotations: {
                        warningLine: {
                            type: 'line',
                            yMin: CHART_DEFAULTS.temperature.warning,
                            yMax: CHART_DEFAULTS.temperature.warning,
                            borderColor: '#f59e0b',
                            borderWidth: 1,
                            borderDash: [5, 5],
                            label: {
                                display: true,
                                content: `Warning: ${CHART_DEFAULTS.temperature.warning}${CHART_DEFAULTS.temperature.unit}`,
                                position: 'end',
                                backgroundColor: 'rgba(245, 158, 11, 0.7)',
                                font: {
                                    size: 10
                                },
                                padding: 4
                            }
                        },
                        criticalLine: {
                            type: 'line',
                            yMin: CHART_DEFAULTS.temperature.critical,
                            yMax: CHART_DEFAULTS.temperature.critical,
                            borderColor: '#ef4444',
                            borderWidth: 1,
                            borderDash: [5, 5],
                            label: {
                                display: true,
                                content: `Critical: ${CHART_DEFAULTS.temperature.critical}${CHART_DEFAULTS.temperature.unit}`,
                                position: 'end',
                                backgroundColor: 'rgba(239, 68, 68, 0.7)',
                                font: {
                                    size: 10
                                },
                                padding: 4
                            }
                        }
                    }
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'hour',
                        displayFormats: {
                            hour: 'HH:mm'
                        }
                    },
                    grid: {
                        display: false
                    },
                    title: {
                        display: true,
                        text: 'Time'
                    }
                },
                y: {
                    min: CHART_DEFAULTS.temperature.min,
                    max: CHART_DEFAULTS.temperature.max,
                    grid: {
                        color: 'rgba(160, 174, 192, 0.1)'
                    },
                    title: {
                        display: true,
                        text: `Temperature (${CHART_DEFAULTS.temperature.unit})`
                    }
                }
            }
        }
    });
    
    // Store chart reference
    charts.temperature = temperatureChart;
    
    // Fetch initial data
    fetchTemperatureData('day');
}

/**
 * Create pressure chart
 */
function createPressureChart() {
    const ctx = document.getElementById('pressure-chart');
    
    if (!ctx) {
        console.warn('Pressure chart canvas not found');
        return;
    }
    
    // Show loading indicator
    const loadingIndicator = ctx.parentElement.querySelector('.chart-loading');
    if (loadingIndicator) {
        loadingIndicator.classList.add('show');
    }
    
    // Set up pressure chart
    const pressureChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Pressure',
                data: [],
                borderColor: '#8b5cf6',
                backgroundColor: 'rgba(139, 92, 246, 0.1)',
                borderWidth: 2,
                pointBackgroundColor: '#8b5cf6',
                pointRadius: 2,
                pointHoverRadius: 4,
                tension: 0.2,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false
            },
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `Pressure: ${context.parsed.y}${CHART_DEFAULTS.pressure.unit}`;
                        }
                    }
                },
                annotation: {
                    annotations: {
                        warningLine: {
                            type: 'line',
                            yMin: CHART_DEFAULTS.pressure.warning,
                            yMax: CHART_DEFAULTS.pressure.warning,
                            borderColor: '#f59e0b',
                            borderWidth: 1,
                            borderDash: [5, 5],
                            label: {
                                display: true,
                                content: `Warning: ${CHART_DEFAULTS.pressure.warning}${CHART_DEFAULTS.pressure.unit}`,
                                position: 'end',
                                backgroundColor: 'rgba(245, 158, 11, 0.7)',
                                font: {
                                    size: 10
                                },
                                padding: 4
                            }
                        },
                        criticalLine: {
                            type: 'line',
                            yMin: CHART_DEFAULTS.pressure.critical,
                            yMax: CHART_DEFAULTS.pressure.critical,
                            borderColor: '#ef4444',
                            borderWidth: 1,
                            borderDash: [5, 5],
                            label: {
                                display: true,
                                content: `Critical: ${CHART_DEFAULTS.pressure.critical}${CHART_DEFAULTS.pressure.unit}`,
                                position: 'end',
                                backgroundColor: 'rgba(239, 68, 68, 0.7)',
                                font: {
                                    size: 10
                                },
                                padding: 4
                            }
                        }
                    }
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        unit: 'hour',
                        displayFormats: {
                            hour: 'HH:mm'
                        }
                    },
                    grid: {
                        display: false
                    },
                    title: {
                        display: true,
                        text: 'Time'
                    }
                },
                y: {
                    min: CHART_DEFAULTS.pressure.min,
                    max: CHART_DEFAULTS.pressure.max,
                    grid: {
                        color: 'rgba(160, 174, 192, 0.1)'
                    },
                    title: {
                        display: true,
                        text: `Pressure (${CHART_DEFAULTS.pressure.unit})`
                    }
                }
            }
        }
    });
    
    // Store chart reference
    charts.pressure = pressureChart;
    
    // Fetch initial data
    fetchPressureData('day');
}

/**
 * Initialize chart timeframe selectors
 */
function initChartTimeframeSelectors() {
    // Get all timeframe buttons
    const timeframeButtons = document.querySelectorAll('.chart-card .btn-card-action[data-timeframe]');
    
    timeframeButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Get parent card to determine which chart to update
            const card = this.closest('.chart-card');
            const timeframe = this.dataset.timeframe;
            
            // Remove active class from all buttons in this card
            card.querySelectorAll('.btn-card-action').forEach(btn => {
                btn.classList.remove('active');
            });
            
            // Add active class to clicked button
            this.classList.add('active');
            
            // Update chart based on card type
            if (card.querySelector('h3').textContent.includes('Temperature')) {
                fetchTemperatureData(timeframe);
            } else if (card.querySelector('h3').textContent.includes('Pressure')) {
                fetchPressureData(timeframe);
            }
        });
    });
}

/**
 * Fetch temperature data for the selected timeframe
 * @param {string} timeframe - Timeframe ('hour', 'day', 'week')
 * @param {string} pipelineId - Pipeline ID (optional)
 */
async function fetchTemperatureData(timeframe = 'day', pipelineId = null) {
    // If chart doesn't exist, return
    if (!charts.temperature) {
        return;
    }
    
    // Show loading indicator
    const loadingIndicator = document.querySelector('#temperature-chart').parentElement.querySelector('.chart-loading');
    if (loadingIndicator) {
        loadingIndicator.classList.add('show');
    }
    
    try {
        // Get selected pipeline
        const selectedPipeline = pipelineId || document.querySelector('#pipeline-select')?.value || 'all';
        
        // Determine time range based on timeframe
        const timeRange = getTimeRangeForTimeframe(timeframe);
        
        // Fetch data
        let data;
        
        if (selectedPipeline === 'all') {
            // Fetch all pipelines
            data = await window.apiService.fetchSensorData('all', 'temperature', timeRange);
        } else {
            // Fetch specific pipeline
            data = await window.apiService.fetchSensorData(selectedPipeline, 'temperature', timeRange);
        }
        
        // Process and update chart data
        const chartData = processDataForChart(data, 'temperature');
        updateTemperatureChart(chartData, timeframe);
        
    } catch (error) {
        console.error('Error fetching temperature data:', error);
        // Show error notification
        window.utils.showNotification('Failed to load temperature data. Please try again.', 'error');
    } finally {
        // Hide loading indicator
        if (loadingIndicator) {
            loadingIndicator.classList.remove('show');
        }
    }
}

/**
 * Fetch pressure data for the selected timeframe
 * @param {string} timeframe - Timeframe ('hour', 'day', 'week')
 * @param {string} pipelineId - Pipeline ID (optional)
 */
async function fetchPressureData(timeframe = 'day', pipelineId = null) {
    // If chart doesn't exist, return
    if (!charts.pressure) {
        return;
    }
    
    // Show loading indicator
    const loadingIndicator = document.querySelector('#pressure-chart').parentElement.querySelector('.chart-loading');
    if (loadingIndicator) {
        loadingIndicator.classList.add('show');
    }
    
    try {
        // Get selected pipeline
        const selectedPipeline = pipelineId || document.querySelector('#pipeline-select')?.value || 'all';
        
        // Determine time range based on timeframe
        const timeRange = getTimeRangeForTimeframe(timeframe);
        
        // Fetch data
        let data;
        
        if (selectedPipeline === 'all') {
            // Fetch all pipelines
            data = await window.apiService.fetchSensorData('all', 'pressure', timeRange);
        } else {
            // Fetch specific pipeline
            data = await window.apiService.fetchSensorData(selectedPipeline, 'pressure', timeRange);
        }
        
        // Process and update chart data
        const chartData = processDataForChart(data, 'pressure');
        updatePressureChart(chartData, timeframe);
        
    } catch (error) {
        console.error('Error fetching pressure data:', error);
        // Show error notification
        window.utils.showNotification('Failed to load pressure data. Please try again.', 'error');
    } finally {
        // Hide loading indicator
        if (loadingIndicator) {
            loadingIndicator.classList.remove('show');
        }
    }
}

/**
 * Get time range object for a timeframe
 * @param {string} timeframe - Timeframe ('hour', 'day', 'week')
 * @returns {Object} - Time range object with start and end properties
 */
function getTimeRangeForTimeframe(timeframe) {
    const now = new Date();
    let start;
    
    switch (timeframe) {
        case 'hour':
            start = new Date(now);
            start.setHours(now.getHours() - 1);
            break;
        
        case 'day':
            start = new Date(now);
            start.setDate(now.getDate() - 1);
            break;
        
        case 'week':
            start = new Date(now);
            start.setDate(now.getDate() - 7);
            break;
        
        default:
            // Default to day
            start = new Date(now);
            start.setDate(now.getDate() - 1);
    }
    
    return {
        start: start.toISOString(),
        end: now.toISOString()
    };
}

/**
 * Process API data for chart display
 * @param {Object} data - API response data
 * @param {string} type - Data type ('temperature' or 'pressure')
 * @returns {Array} - Processed data for chart
 */
function processDataForChart(data, type) {
    if (!data || !data.data || !Array.isArray(data.data)) {
        return [];
    }
    
    // Map data to chart format
    return data.data.map(item => ({
        x: new Date(item.time),
        y: parseFloat(item.value)
    }));
}

/**
 * Update temperature chart with new data
 * @param {Array} data - Processed chart data
 * @param {string} timeframe - Timeframe ('hour', 'day', 'week')
 */
function updateTemperatureChart(data, timeframe) {
    if (!charts.temperature) {
        return;
    }
    
    // Update time unit based on timeframe
    let timeUnit = 'hour';
    
    if (timeframe === 'week') {
        timeUnit = 'day';
    } else if (timeframe === 'day') {
        timeUnit = 'hour';
    } else {
        timeUnit = 'minute';
    }
    
    // Update x-axis time unit
    charts.temperature.options.scales.x.time.unit = timeUnit;
    
    // Update chart data
    charts.temperature.data.datasets[0].data = data;
    
    // Update chart
    charts.temperature.update();
}

/**
 * Update pressure chart with new data
 * @param {Array} data - Processed chart data
 * @param {string} timeframe - Timeframe ('hour', 'day', 'week')
 */
function updatePressureChart(data, timeframe) {
    if (!charts.pressure) {
        return;
    }
    
    // Update time unit based on timeframe
    let timeUnit = 'hour';
    
    if (timeframe === 'week') {
        timeUnit = 'day';
    } else if (timeframe === 'day') {
        timeUnit = 'hour';
    } else {
        timeUnit = 'minute';
    }
    
    // Update x-axis time unit
    charts.pressure.options.scales.x.time.unit = timeUnit;
    
    // Update chart data
    charts.pressure.data.datasets[0].data = data;
    
    // Update chart
    charts.pressure.update();
}

/**
 * Create and update pipeline visualization
 * @param {string} pipelineId - Pipeline ID
 * @param {Array} deviceData - Device data for the pipeline
 */
function createPipelineVisualization(pipelineId, deviceData) {
    const container = document.getElementById('pipeline-container');
    
    if (!container) {
        console.warn('Pipeline container not found');
        return;
    }
    
    // Create HTML for pipeline visualization
    const pipeline = document.createElement('div');
    pipeline.className = 'pipeline-visualization';
    
    // Create pipeline line
    const pipelineLine = document.createElement('div');
    pipelineLine.className = 'pipeline-line';
    pipeline.appendChild(pipelineLine);
    
    // Sort devices by position
    deviceData.sort((a, b) => {
        // Extract position from device ID (last two digits)
        const posA = parseInt(a.device_id.slice(-2));
        const posB = parseInt(b.device_id.slice(-2));
        return posA - posB;
    });
    
    // Create bolts for each device
    deviceData.forEach((device, index) => {
        // Calculate position along pipeline (evenly spaced)
        const position = ((index + 1) / (deviceData.length + 1)) * 100;
        
        // Determine status based on temperature and pressure values
        const tempStatus = window.utils.getStatusFromValue(device.temperature, {
            warning: CHART_DEFAULTS.temperature.warning,
            critical: CHART_DEFAULTS.temperature.critical
        });
        
        const pressureStatus = window.utils.getStatusFromValue(device.pressure, {
            warning: CHART_DEFAULTS.pressure.warning,
            critical: CHART_DEFAULTS.pressure.critical
        });
        
        // Use the most severe status
        const status = tempStatus === 'critical' || pressureStatus === 'critical' ? 'critical' :
                      tempStatus === 'warning' || pressureStatus === 'warning' ? 'warning' : 'healthy';
        
        // Create bolt element
        const bolt = document.createElement('div');
        bolt.className = `pipeline-bolt ${status}`;
        bolt.style.left = `${position}%`;
        
        // Add bolt icon
        const icon = document.createElement('i');
        icon.className = 'fas fa-bolt';
        bolt.appendChild(icon);
        
        // Add bolt label
        const label = document.createElement('div');
        label.className = 'bolt-label';
        label.textContent = device.device_id;
        bolt.appendChild(label);
        
        // Add valve indicator
        const valveIndicator = document.createElement('div');
        valveIndicator.className = `valve-indicator ${device.valve_status || 'closed'}`;
        valveIndicator.innerHTML = device.valve_status === 'open' ? 
            '<i class="fas fa-door-open"></i> Open' : 
            '<i class="fas fa-door-closed"></i> Closed';
        bolt.appendChild(valveIndicator);
        
        // Add tooltip with device details
        const tooltip = document.createElement('div');
        tooltip.className = 'bolt-tooltip';
        
        // Temperature row
        const tempRow = document.createElement('div');
        tempRow.className = 'bolt-tooltip-row';
        const tempLabel = document.createElement('span');
        tempLabel.className = 'bolt-tooltip-label';
        tempLabel.textContent = 'Temperature:';
        const tempValue = document.createElement('span');
        tempValue.className = `bolt-tooltip-value ${tempStatus}`;
        tempValue.textContent = `${device.temperature}${CHART_DEFAULTS.temperature.unit}`;
        tempRow.appendChild(tempLabel);
        tempRow.appendChild(tempValue);
        tooltip.appendChild(tempRow);
        
        // Pressure row
        const pressureRow = document.createElement('div');
        pressureRow.className = 'bolt-tooltip-row';
        const pressureLabel = document.createElement('span');
        pressureLabel.className = 'bolt-tooltip-label';
        pressureLabel.textContent = 'Pressure:';
        const pressureValue = document.createElement('span');
        pressureValue.className = `bolt-tooltip-value ${pressureStatus}`;
        pressureValue.textContent = `${device.pressure}${CHART_DEFAULTS.pressure.unit}`;
        pressureRow.appendChild(pressureLabel);
        pressureRow.appendChild(pressureValue);
        tooltip.appendChild(pressureRow);
        
        // Valve row
        const valveRow = document.createElement('div');
        valveRow.className = 'bolt-tooltip-row';
        const valveLabel = document.createElement('span');
        valveLabel.className = 'bolt-tooltip-label';
        valveLabel.textContent = 'Valve:';
        const valveValue = document.createElement('span');
        valveValue.className = `bolt-tooltip-value ${device.valve_status || 'closed'}`;
        valveValue.textContent = device.valve_status === 'open' ? 'Open' : 'Closed';
        valveRow.appendChild(valveLabel);
        valveRow.appendChild(valveValue);
        tooltip.appendChild(valveRow);
        
        // Last update row
        const updateRow = document.createElement('div');
        updateRow.className = 'bolt-tooltip-row';
        const updateLabel = document.createElement('span');
        updateLabel.className = 'bolt-tooltip-label';
        updateLabel.textContent = 'Last Update:';
        const updateValue = document.createElement('span');
        updateValue.className = 'bolt-tooltip-value';
        updateValue.textContent = window.utils.formatDate(device.last_update, 'relative');
        updateRow.appendChild(updateLabel);
        updateRow.appendChild(updateValue);
        tooltip.appendChild(updateRow);
        
        bolt.appendChild(tooltip);
        
        // Add click handler for bolt
        bolt.addEventListener('click', () => {
            // Select this device in the valve control
            const valveSelect = document.getElementById('valve-device-select');
            if (valveSelect) {
                valveSelect.value = device.device_id;
                
                // Trigger change event to update valve status display
                const event = new Event('change');
                valveSelect.dispatchEvent(event);
            }
        });
        
        // Add bolt to pipeline
        pipeline.appendChild(bolt);
    });
    
    // Clear container and add new pipeline
    container.innerHTML = '';
    container.appendChild(pipeline);
}

/**
 * Update the pipeline table view
 * @param {string} pipelineId - Pipeline ID
 * @param {Array} deviceData - Device data for the pipeline
 */
function updatePipelineTable(pipelineId, deviceData) {
    const tableBody = document.getElementById('pipeline-table-body');
    
    if (!tableBody) {
        console.warn('Pipeline table body not found');
        return;
    }
    
    // Clear table body
    tableBody.innerHTML = '';
    
    // Sort devices by position
    deviceData.sort((a, b) => {
        // Extract position from device ID (last two digits)
        const posA = parseInt(a.device_id.slice(-2));
        const posB = parseInt(b.device_id.slice(-2));
        return posA - posB;
    });
    
    // Create rows for each device
    deviceData.forEach(device => {
        // Determine status classes
        const tempStatus = window.utils.getStatusFromValue(device.temperature, {
            warning: CHART_DEFAULTS.temperature.warning,
            critical: CHART_DEFAULTS.temperature.critical
        });
        
        const pressureStatus = window.utils.getStatusFromValue(device.pressure, {
            warning: CHART_DEFAULTS.pressure.warning,
            critical: CHART_DEFAULTS.pressure.critical
        });
        
        // Create row
        const row = document.createElement('tr');
        
        // Device ID cell
        const deviceIdCell = document.createElement('td');
        deviceIdCell.textContent = device.device_id;
        row.appendChild(deviceIdCell);
        
        // Temperature cell
        const tempCell = document.createElement('td');
        const tempBadge = document.createElement('span');
        tempBadge.className = `status-badge ${tempStatus}`;
        tempBadge.textContent = `${device.temperature}${CHART_DEFAULTS.temperature.unit}`;
        tempCell.appendChild(tempBadge);
        row.appendChild(tempCell);
        
        // Pressure cell
        const pressureCell = document.createElement('td');
        const pressureBadge = document.createElement('span');
        pressureBadge.className = `status-badge ${pressureStatus}`;
        pressureBadge.textContent = `${device.pressure}${CHART_DEFAULTS.pressure.unit}`;
        pressureCell.appendChild(pressureBadge);
        row.appendChild(pressureCell);
        
        // Valve status cell
        const valveCell = document.createElement('td');
        const valveBadge = document.createElement('span');
        valveBadge.className = `status-badge ${device.valve_status === 'open' ? 'open' : 'closed'}`;
        valveBadge.textContent = device.valve_status === 'open' ? 'Open' : 'Closed';
        valveCell.appendChild(valveBadge);
        row.appendChild(valveCell);
        
        // Last update cell
        const updateCell = document.createElement('td');
        updateCell.textContent = window.utils.formatDate(device.last_update, 'relative');
        row.appendChild(updateCell);
        
        // Actions cell
        const actionsCell = document.createElement('td');
        
        // Create toggle button
        const toggleButton = document.createElement('button');
        toggleButton.className = `btn-valve ${device.valve_status === 'open' ? 'close' : 'open'}`;
        toggleButton.innerHTML = device.valve_status === 'open' ? 
            '<i class="fas fa-door-closed"></i>' : 
            '<i class="fas fa-door-open"></i>';
        toggleButton.title = device.valve_status === 'open' ? 'Close Valve' : 'Open Valve';
        
        // Add click handler for toggle button
        toggleButton.addEventListener('click', async () => {
            try {
                const command = device.valve_status === 'open' ? 'close' : 'open';
                
                // Show confirmation
                window.utils.createModal({
                    title: `Confirm Valve Action`,
                    content: `Are you sure you want to <strong>${command}</strong> the valve for device <strong>${device.device_id}</strong>?`,
                    buttons: [
                        {
                            text: 'Cancel',
                            type: 'secondary'
                        },
                        {
                            text: 'Confirm',
                            type: 'primary',
                            handler: async (e, { close }) => {
                                try {
                                    // Send command to API
                                    await window.apiService.controlValve(device.device_id, command);
                                    
                                    // Show success notification
                                    window.utils.showNotification(`Valve ${command}ed successfully`, 'success');
                                    
                                    // Refresh data
                                    refreshPipelineData();
                                    
                                    // Close modal
                                    close();
                                } catch (error) {
                                    console.error('Error controlling valve:', error);
                                    window.utils.showNotification(`Failed to ${command} valve. Please try again.`, 'error');
                                }
                            }
                        }
                    ]
                });
            } catch (error) {
                console.error('Error controlling valve:', error);
                window.utils.showNotification(`Failed to control valve. Please try again.`, 'error');
            }
        });
        
        actionsCell.appendChild(toggleButton);
        
        // Create view details button
        const detailsButton = document.createElement('button');
        detailsButton.className = 'btn-valve';
        detailsButton.innerHTML = '<i class="fas fa-info-circle"></i>';
        detailsButton.title = 'View Details';
        detailsButton.style.marginLeft = '8px';
        
        // Add click handler for details button
        detailsButton.addEventListener('click', () => {
            // Show device details modal
            window.utils.createModal({
                title: `Device ${device.device_id} Details`,
                content: `
                    <div class="device-details">
                        <div class="detail-row">
                            <div class="detail-label">Device ID:</div>
                            <div class="detail-value">${device.device_id}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-label">Pipeline:</div>
                            <div class="detail-value">${pipelineId}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-label">Temperature:</div>
                            <div class="detail-value ${tempStatus}">${device.temperature}${CHART_DEFAULTS.temperature.unit}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-label">Pressure:</div>
                            <div class="detail-value ${pressureStatus}">${device.pressure}${CHART_DEFAULTS.pressure.unit}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-label">Valve Status:</div>
                            <div class="detail-value ${device.valve_status === 'open' ? 'open' : 'closed'}">${device.valve_status === 'open' ? 'Open' : 'Closed'}</div>
                        </div>
                        <div class="detail-row">
                            <div class="detail-label">Last Update:</div>
                            <div class="detail-value">${window.utils.formatDate(device.last_update, 'datetime')}</div>
                        </div>
                    </div>
                `
            });
        });
        
        actionsCell.appendChild(detailsButton);
        row.appendChild(actionsCell);
        
        // Add row to table
        tableBody.appendChild(row);
    });
}

/**
 * Refresh pipeline data
 */
async function refreshPipelineData() {
    const pipelineSelect = document.getElementById('pipeline-select');
    
    if (!pipelineSelect) {
        return;
    }
    
    const selectedPipeline = pipelineSelect.value;
    
    // Show refresh animation
    const refreshButton = document.getElementById('refresh-data');
    if (refreshButton) {
        refreshButton.classList.add('spinning');
    }
    
    try {
        // Fetch data
        if (selectedPipeline === 'all') {
            // Fetch all pipelines
            await Promise.all([
                fetchTemperatureData('day'),
                fetchPressureData('day')
            ]);
        } else {
            // Fetch specific pipeline
            await Promise.all([
                fetchTemperatureData('day', selectedPipeline),
                fetchPressureData('day', selectedPipeline),
                fetchPipelineDevices(selectedPipeline)
            ]);
        }
        
        // Update last updated time
        const lastUpdatedEl = document.getElementById('last-updated');
        if (lastUpdatedEl) {
            lastUpdatedEl.textContent = 'Just now';
        }
        
    } catch (error) {
        console.error('Error refreshing data:', error);
        window.utils.showNotification('Failed to refresh data. Please try again.', 'error');
    } finally {
        // Remove refresh animation
        if (refreshButton) {
            refreshButton.classList.remove('spinning');
        }
    }
}

/**
 * Fetch devices for a pipeline and update visualization
 * @param {string} pipelineId - Pipeline ID
 */
async function fetchPipelineDevices(pipelineId) {
    try {
        // Show loading indicator
        const loadingIndicator = document.querySelector('.pipeline-loading');
        if (loadingIndicator) {
            loadingIndicator.classList.add('show');
        }
        
        // Fetch devices
        const devices = await window.apiService.fetchPipelineDevices(pipelineId);
        
        if (!devices || !Array.isArray(devices)) {
            throw new Error('Invalid device data');
        }
        
        // Get latest status for each device
        const deviceStatus = await window.apiService.fetchLatestStatus();
        
        // Combine device info with status
        const deviceData = devices.map(device => {
            const status = deviceStatus.data.find(s => s.device_id === device.id);
            
            return {
                device_id: device.id,
                temperature: status ? parseFloat(status.temperature) : 65,
                pressure: status ? parseFloat(status.pressure) : 7.5,
                valve_status: status ? status.valve_status : 'closed',
                last_update: status ? status.timestamp : new Date().toISOString()
            };
        });
        
        // Update pipeline visualization
        createPipelineVisualization(pipelineId, deviceData);
        
        // Update pipeline table
        updatePipelineTable(pipelineId, deviceData);
        
    } catch (error) {
        console.error('Error fetching pipeline devices:', error);
        window.utils.showNotification('Failed to load pipeline devices. Please try again.', 'error');
    } finally {
        // Hide loading indicator
        const loadingIndicator = document.querySelector('.pipeline-loading');
        if (loadingIndicator) {
            loadingIndicator.classList.remove('show');
        }
    }
}

// Export charts functions
window.chartService = {
    initCharts,
    createTemperatureChart,
    createPressureChart,
    fetchTemperatureData,
    fetchPressureData,
    fetchPipelineDevices,
    refreshPipelineData
};