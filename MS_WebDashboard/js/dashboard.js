/**
 * Dashboard Module for Smart IoT Bolt Dashboard
 * Handles the main dashboard functionality
 */

// Dashboard state
let dashboardState = {
    currentPipeline: 'all',
    refreshInterval: null,
    notificationCount: 0,
    alerts: [],
    pipelines: [],
    devices: {}
};

/**
 * Initialize the dashboard
 */
async function initDashboard() {
    // Load user authentication data
    window.authService.initAuth();
    
    // Update user interface with current user data
    window.authService.updateUserInterface();
    
    // Initialize dashboard UI elements
    initUIElements();
    
    // Initialize theme switcher
    window.utils.initThemeSwitcher();
    
    // Initialize API service
    await window.apiService.initApiService();
    
    // Load initial data
    await loadInitialData();
    
    // Initialize charts
    window.chartService.initCharts();
    
    // Start data refresh interval
    startRefreshInterval();
    
    // Set up socket connection for real-time updates
    // setupRealTimeUpdates();
}

/**
 * Initialize UI elements and event listeners
 */
function initUIElements() {
    // Sidebar toggle
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebar = document.querySelector('.sidebar');
    
    if (sidebarToggle && sidebar) {
        sidebarToggle.addEventListener('click', () => {
            sidebar.classList.toggle('collapsed');
        });
    }
    
    // Pipeline selector
    const pipelineSelect = document.getElementById('pipeline-select');
    
    if (pipelineSelect) {
        pipelineSelect.addEventListener('change', function() {
            dashboardState.currentPipeline = this.value;
            loadPipelineData(this.value);
        });
    }
    
    // Refresh button
    const refreshButton = document.getElementById('refresh-data');
    
    if (refreshButton) {
        refreshButton.addEventListener('click', function() {
            window.chartService.refreshPipelineData();
        });
    }
    
    // View toggles (schematic/table)
    const viewToggles = document.querySelectorAll('.toggle-view');
    
    viewToggles.forEach(toggle => {
        toggle.addEventListener('click', function() {
            // Remove active class from all toggles
            viewToggles.forEach(t => t.classList.remove('active'));
            
            // Add active class to clicked toggle
            this.classList.add('active');
            
            // Show/hide views
            const view = this.dataset.view;
            const views = document.querySelectorAll('.pipeline-view');
            
            views.forEach(v => {
                v.classList.remove('active');
                
                if (v.classList.contains(`${view}-view`)) {
                    v.classList.add('active');
                }
            });
        });
    });
    
    // Valve device selector
    const valveDeviceSelect = document.getElementById('valve-device-select');
    
    if (valveDeviceSelect) {
        valveDeviceSelect.addEventListener('change', function() {
            updateValveControlUI(this.value);
        });
    }
    
    // Valve control buttons
    const openValveBtn = document.getElementById('open-valve');
    const closeValveBtn = document.getElementById('close-valve');
    
    if (openValveBtn && closeValveBtn) {
        openValveBtn.addEventListener('click', function() {
            showValveConfirmation('open');
        });
        
        closeValveBtn.addEventListener('click', function() {
            showValveConfirmation('close');
        });
    }
    
    // Valve confirmation buttons
    const confirmValveActionBtn = document.getElementById('confirm-valve-action');
    const cancelValveActionBtn = document.getElementById('cancel-valve-action');
    
    if (confirmValveActionBtn && cancelValveActionBtn) {
        confirmValveActionBtn.addEventListener('click', function() {
            executeValveAction();
        });
        
        cancelValveActionBtn.addEventListener('click', function() {
            hideValveConfirmation();
        });
    }
    
    // Alert actions
    initAlertActions();
    
    // Notification dropdown content
    initNotifications();
}

/**
 * Load initial dashboard data
 */
async function loadInitialData() {
    try {
        // Show loading indicator
        showDashboardLoading(true);
        
        // Load pipelines
        const pipelines = await window.apiService.fetchPipelines();
        dashboardState.pipelines = pipelines;
        
        // Populate pipeline selector
        populatePipelineSelector(pipelines);
        
        // Load alerts
        await loadAlerts();
        
        // Load data for current pipeline
        await loadPipelineData(dashboardState.currentPipeline);
        
        // Update status cards
        updateStatusCards();
        
        // Hide loading indicator
        showDashboardLoading(false);
        
    } catch (error) {
        console.error('Error loading dashboard data:', error);
        window.utils.showNotification('Failed to load dashboard data. Please try again.', 'error');
        showDashboardLoading(false);
    }
}

/**
 * Show or hide dashboard loading indicators
 * @param {boolean} show - Whether to show or hide loading indicators
 */
function showDashboardLoading(show) {
    const loadingIndicators = document.querySelectorAll('.chart-loading');
    
    loadingIndicators.forEach(indicator => {
        if (show) {
            indicator.classList.add('show');
        } else {
            indicator.classList.remove('show');
        }
    });
}

/**
 * Populate pipeline selector dropdown
 * @param {Array} pipelines - List of pipelines
 */
function populatePipelineSelector(pipelines) {
    const pipelineSelect = document.getElementById('pipeline-select');
    
    if (!pipelineSelect) {
        return;
    }
    
    // Clear current options (except "All Pipelines")
    while (pipelineSelect.options.length > 1) {
        pipelineSelect.remove(1);
    }
    
    // Add pipeline options
    pipelines.forEach(pipeline => {
        const option = document.createElement('option');
        option.value = pipeline.id;
        option.textContent = `Pipeline ${pipeline.id}`;
        pipelineSelect.appendChild(option);
    });
}

/**
 * Load data for a specific pipeline
 * @param {string} pipelineId - Pipeline ID or 'all' for all pipelines
 */
async function loadPipelineData(pipelineId) {
    try {
        // Update charts for selected pipeline
        await Promise.all([
            window.chartService.fetchTemperatureData('day', pipelineId),
            window.chartService.fetchPressureData('day', pipelineId)
        ]);
        
        // If a specific pipeline is selected, fetch its devices
        if (pipelineId !== 'all') {
            await window.chartService.fetchPipelineDevices(pipelineId);
        } else {
            // Clear pipeline visualization for "All Pipelines"
            const pipelineContainer = document.getElementById('pipeline-container');
            if (pipelineContainer) {
                pipelineContainer.innerHTML = `
                    <div class="pipeline-placeholder">
                        <div class="placeholder-icon">
                            <i class="fas fa-project-diagram"></i>
                        </div>
                        <div class="placeholder-text">
                            Please select a specific pipeline to view its devices.
                        </div>
                    </div>
                `;
            }
            
            // Clear pipeline table for "All Pipelines"
            const pipelineTableBody = document.getElementById('pipeline-table-body');
            if (pipelineTableBody) {
                pipelineTableBody.innerHTML = '';
            }
        }
        
        // Update valve device selector
        updateValveDeviceSelector(pipelineId);
        
    } catch (error) {
        console.error('Error loading pipeline data:', error);
        window.utils.showNotification('Failed to load pipeline data. Please try again.', 'error');
    }
}

/**
 * Update valve device selector options based on selected pipeline
 * @param {string} pipelineId - Pipeline ID or 'all' for all pipelines
 */
async function updateValveDeviceSelector(pipelineId) {
    const valveDeviceSelect = document.getElementById('valve-device-select');
    
    if (!valveDeviceSelect) {
        return;
    }
    
    // Clear current options
    valveDeviceSelect.innerHTML = '<option value="">Select device...</option>';
    
    try {
        if (pipelineId === 'all') {
            // Get devices from all pipelines
            for (const pipeline of dashboardState.pipelines) {
                const devices = await window.apiService.fetchPipelineDevices(pipeline.id);
                
                // Create optgroup for this pipeline
                const optgroup = document.createElement('optgroup');
                optgroup.label = `Pipeline ${pipeline.id}`;
                
                // Add device options
                devices.forEach(device => {
                    const option = document.createElement('option');
                    option.value = device.id;
                    option.textContent = `Device ${device.id}`;
                    optgroup.appendChild(option);
                });
                
                valveDeviceSelect.appendChild(optgroup);
            }
        } else {
            // Get devices for specific pipeline
            const devices = await window.apiService.fetchPipelineDevices(pipelineId);
            
            // Add device options
            devices.forEach(device => {
                const option = document.createElement('option');
                option.value = device.id;
                option.textContent = `Device ${device.id}`;
                valveDeviceSelect.appendChild(option);
            });
        }
    } catch (error) {
        console.error('Error updating valve device selector:', error);
    }
}

/**
 * Update valve control UI based on selected device
 * @param {string} deviceId - Device ID
 */
async function updateValveControlUI(deviceId) {
    // Find valve status element
    const valveStatusEl = document.getElementById('valve-status');
    
    if (!valveStatusEl) {
        return;
    }
    
    if (!deviceId) {
        // No device selected
        valveStatusEl.innerHTML = '<span class="status-badge">Not Selected</span>';
        return;
    }
    
    try {
        // Fetch latest status for this device
        const status = await window.apiService.fetchLatestStatus(deviceId);
        
        // Find device status
        const deviceStatus = status.data.find(s => s.device_id === deviceId);
        
        if (deviceStatus) {
            // Update valve status display
            const valveStatus = deviceStatus.valve_status || 'closed';
            valveStatusEl.innerHTML = `<span class="status-badge ${valveStatus}">${valveStatus.charAt(0).toUpperCase() + valveStatus.slice(1)}</span>`;
            
            // Update buttons
            const openValveBtn = document.getElementById('open-valve');
            const closeValveBtn = document.getElementById('close-valve');
            
            if (openValveBtn && closeValveBtn) {
                if (valveStatus === 'open') {
                    openValveBtn.disabled = true;
                    closeValveBtn.disabled = false;
                } else {
                    openValveBtn.disabled = false;
                    closeValveBtn.disabled = true;
                }
            }
        } else {
            // Device not found
            valveStatusEl.innerHTML = '<span class="status-badge">Unknown</span>';
        }
    } catch (error) {
        console.error('Error updating valve status:', error);
        valveStatusEl.innerHTML = '<span class="status-badge">Error</span>';
    }
}

/**
 * Show valve action confirmation
 * @param {string} action - Action type ('open' or 'close')
 */
function showValveConfirmation(action) {
    const valveConfirmation = document.getElementById('valve-confirmation');
    const valveAction = document.getElementById('valve-action');
    
    if (valveConfirmation && valveAction) {
        valveAction.textContent = action;
        valveConfirmation.classList.remove('hidden');
    }
}

/**
 * Hide valve action confirmation
 */
function hideValveConfirmation() {
    const valveConfirmation = document.getElementById('valve-confirmation');
    
    if (valveConfirmation) {
        valveConfirmation.classList.add('hidden');
    }
}

/**
 * Execute valve action based on confirmation
 */
async function executeValveAction() {
    const valveDeviceSelect = document.getElementById('valve-device-select');
    const valveAction = document.getElementById('valve-action');
    
    if (!valveDeviceSelect || !valveAction) {
        return;
    }
    
    const deviceId = valveDeviceSelect.value;
    const action = valveAction.textContent;
    
    if (!deviceId || !action) {
        window.utils.showNotification('No device or action selected', 'error');
        hideValveConfirmation();
        return;
    }
    
    try {
        // Send command to API
        await window.apiService.controlValve(deviceId, action);
        
        // Show success notification
        window.utils.showNotification(`Valve ${action}ed successfully`, 'success');
        
        // Update valve status UI
        setTimeout(() => {
            updateValveControlUI(deviceId);
        }, 1000);
        
        // Refresh pipeline data
        setTimeout(() => {
            window.chartService.refreshPipelineData();
        }, 2000);
        
    } catch (error) {
        console.error('Error controlling valve:', error);
        window.utils.showNotification(`Failed to ${action} valve. Please try again.`, 'error');
    } finally {
        // Hide confirmation
        hideValveConfirmation();
    }
}

/**
 * Start data refresh interval
 */
function startRefreshInterval() {
    // Clear existing interval if any
    if (dashboardState.refreshInterval) {
        clearInterval(dashboardState.refreshInterval);
    }
    
    // Set up new interval (refresh every 30 seconds)
    dashboardState.refreshInterval = setInterval(() => {
        window.chartService.refreshPipelineData();
        loadAlerts();
        updateLastUpdatedTime();
    }, 30000);
}

/**
 * Update the last updated time display
 */
function updateLastUpdatedTime() {
    const lastUpdatedEl = document.getElementById('last-updated');
    
    if (lastUpdatedEl) {
        lastUpdatedEl.textContent = window.utils.formatDate(new Date(), 'relative');
    }
}

/**
 * Load alerts from the API
 */
async function loadAlerts() {
    try {
        // Fetch alerts from API
        const response = await window.apiService.fetchAlerts();
        
        if (response && response.alerts) {
            dashboardState.alerts = response.alerts;
            
            // Update alerts UI
            updateAlertsUI(response.alerts);
            
            // Update notification count
            updateNotificationCount(response.alerts.length);
        }
    } catch (error) {
        console.error('Error loading alerts:', error);
    }
}

/**
 * Update the alerts UI with new alerts
 * @param {Array} alerts - List of alerts
 */
function updateAlertsUI(alerts) {
    const alertList = document.getElementById('alert-list');
    
    if (!alertList) {
        return;
    }
    
    // Clear current alerts
    alertList.innerHTML = '';
    
    if (!alerts || alerts.length === 0) {
        // Show no alerts message
        alertList.innerHTML = `
            <div class="alert-empty">
                <i class="fas fa-check-circle"></i>
                <span>No active alerts</span>
            </div>
        `;
        return;
    }
    
    // Sort alerts by timestamp (newest first)
    alerts.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    
    // Show recent alerts (up to 5)
    const recentAlerts = alerts.slice(0, 5);
    
    recentAlerts.forEach(alert => {
        // Determine alert level class
        let alertClass = 'info';
        let iconClass = 'fa-info-circle';
        
        if (alert.alert_level === 'critical') {
            alertClass = 'critical';
            iconClass = 'fa-exclamation-triangle';
        } else if (alert.alert_level === 'warning') {
            alertClass = 'warning';
            iconClass = 'fa-exclamation-circle';
        }
        
        // Create alert item
        const alertItem = document.createElement('div');
        alertItem.className = `alert-item ${alertClass}`;
        alertItem.dataset.alertId = alert.id || 'alert-' + Date.now();
        
        alertItem.innerHTML = `
            <div class="alert-icon">
                <i class="fas ${iconClass}"></i>
            </div>
            <div class="alert-content">
                <div class="alert-title">${getAlertTitle(alert)}</div>
                <div class="alert-message">${getAlertMessage(alert)}</div>
                <div class="alert-time">${window.utils.formatDate(alert.timestamp, 'relative')}</div>
            </div>
            <div class="alert-actions">
                <button class="btn-alert-action resolve" title="Resolve Alert">
                    <i class="fas fa-check"></i>
                </button>
                <button class="btn-alert-action details" title="View Details">
                    <i class="fas fa-eye"></i>
                </button>
            </div>
        `;
        
        alertList.appendChild(alertItem);
    });
    
    // Init alert actions
    initAlertActions();
}

/**
 * Get alert title based on alert data
 * @param {Object} alert - Alert data
 * @returns {string} - Alert title
 */
function getAlertTitle(alert) {
    if (alert.type === 'temperature') {
        return alert.alert_level === 'critical' ? 'Critical Temperature' : 'High Temperature Warning';
    } else if (alert.type === 'pressure') {
        return alert.alert_level === 'critical' ? 'Critical Pressure' : 'High Pressure Warning';
    } else {
        return 'System Alert';
    }
}

/**
 * Get alert message based on alert data
 * @param {Object} alert - Alert data
 * @returns {string} - Alert message
 */
function getAlertMessage(alert) {
    let message = '';
    
    if (alert.type === 'temperature' || alert.type === 'pressure') {
        const measurement = alert.type.charAt(0).toUpperCase() + alert.type.slice(1);
        const unit = alert.type === 'temperature' ? '°C' : 'bar';
        
        message = `${measurement} ${alert.predicted_value ? 'predicted to reach' : 'reached'} ${alert.predicted_value || alert.value}${unit} on Pipeline ${alert.pipeline_id || 'Unknown'}, Device ${alert.bolt_id || alert.device_id || 'Unknown'}`;
        
        if (alert.hours_until && alert.predicted_value) {
            message += ` in ${alert.hours_until} hour${alert.hours_until === 1 ? '' : 's'}`;
        }
    } else {
        message = alert.message || 'System alert detected';
    }
    
    return message;
}

/**
 * Initialize alert action buttons
 */
function initAlertActions() {
    // Resolve buttons
    const resolveButtons = document.querySelectorAll('.alert-item .resolve');
    
    resolveButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.stopPropagation();
            const alertItem = this.closest('.alert-item');
            
            if (alertItem) {
                const alertId = alertItem.dataset.alertId;
                resolveAlert(alertId, alertItem);
            }
        });
    });
    
    // Details buttons
    const detailsButtons = document.querySelectorAll('.alert-item .details');
    
    detailsButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.stopPropagation();
            const alertItem = this.closest('.alert-item');
            
            if (alertItem) {
                const alertId = alertItem.dataset.alertId;
                showAlertDetails(alertId);
            }
        });
    });
}

/**
 * Resolve an alert
 * @param {string} alertId - Alert ID
 * @param {HTMLElement} alertItem - Alert item element
 */
async function resolveAlert(alertId, alertItem) {
    try {
        // API call to resolve alert (not implemented in this version)
        // await window.apiService.resolveAlert(alertId);
        
        // For now, just remove the alert from UI
        if (alertItem) {
            // Add resolved class for animation
            alertItem.classList.add('resolved');
            
            // Remove after animation
            setTimeout(() => {
                alertItem.remove();
                
                // Remove from dashboard state
                dashboardState.alerts = dashboardState.alerts.filter(alert => alert.id !== alertId);
                
                // Update notification count
                updateNotificationCount(dashboardState.alerts.length);
                
                // Check if all alerts resolved
                const alertList = document.getElementById('alert-list');
                if (alertList && alertList.children.length === 0) {
                    updateAlertsUI([]);
                }
            }, 300);
        }
        
        // Show success notification
        window.utils.showNotification('Alert resolved successfully', 'success');
        
    } catch (error) {
        console.error('Error resolving alert:', error);
        window.utils.showNotification('Failed to resolve alert. Please try again.', 'error');
    }
}

/**
 * Show alert details in a modal
 * @param {string} alertId - Alert ID
 */
function showAlertDetails(alertId) {
    // Find alert in state
    const alert = dashboardState.alerts.find(a => a.id === alertId);
    
    if (!alert) {
        window.utils.showNotification('Alert details not found', 'error');
        return;
    }
    
    // Create modal with alert details
    window.utils.createModal({
        title: getAlertTitle(alert),
        content: `
            <div class="alert-details">
                <div class="detail-row">
                    <div class="detail-label">Alert Level:</div>
                    <div class="detail-value">${alert.alert_level.charAt(0).toUpperCase() + alert.alert_level.slice(1)}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Type:</div>
                    <div class="detail-value">${alert.type.charAt(0).toUpperCase() + alert.type.slice(1)}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Pipeline:</div>
                    <div class="detail-value">${alert.pipeline_id || 'Unknown'}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Device:</div>
                    <div class="detail-value">${alert.bolt_id || alert.device_id || 'Unknown'}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Value:</div>
                    <div class="detail-value">${alert.predicted_value || alert.value} ${alert.type === 'temperature' ? '°C' : 'bar'}</div>
                </div>
                <div class="detail-row">
                    <div class="detail-label">Threshold:</div>
                    <div class="detail-value">${alert.threshold} ${alert.type === 'temperature' ? '°C' : 'bar'}</div>
                </div>
                ${alert.hours_until ? `
                <div class="detail-row">
                    <div class="detail-label">Time Until:</div>
                    <div class="detail-value">${alert.hours_until} hour${alert.hours_until === 1 ? '' : 's'}</div>
                </div>
                ` : ''}
                <div class="detail-row">
                    <div class="detail-label">Timestamp:</div>
                    <div class="detail-value">${window.utils.formatDate(alert.timestamp, 'datetime')}</div>
                </div>
            </div>
        `,
        buttons: [
            {
                text: 'Resolve Alert',
                type: 'primary',
                handler: (e, { close }) => {
                    // Find alert item in DOM
                    const alertItem = document.querySelector(`.alert-item[data-alert-id="${alertId}"]`);
                    
                    // Resolve alert
                    resolveAlert(alertId, alertItem);
                    
                    // Close modal
                    close();
                }
            },
            {
                text: 'Close',
                type: 'secondary'
            }
        ]
    });
}

/**
 * Update notification count in the UI
 * @param {number} count - Number of notifications
 */
function updateNotificationCount(count) {
    const badges = document.querySelectorAll('.notification-badge');
    
    badges.forEach(badge => {
        if (count > 0) {
            badge.textContent = count;
            badge.style.display = 'flex';
        } else {
            badge.style.display = 'none';
        }
    });
    
    // Update dashboard state
    dashboardState.notificationCount = count;
}

/**
 * Initialize notification dropdown
 */
function initNotifications() {
    const notificationBell = document.querySelector('.notification-bell');
    const notificationList = document.querySelector('.notification-list');
    
    if (!notificationBell || !notificationList) {
        return;
    }
    
    // Mark all as read button
    const markAllReadBtn = document.querySelector('.mark-all-read');
    
    if (markAllReadBtn) {
        markAllReadBtn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            
            // Clear all notifications
            dashboardState.alerts.forEach(alert => {
                // API call to resolve alert (not implemented in this version)
                // window.apiService.resolveAlert(alert.id);
            });
            
            // Clear alerts from state
            dashboardState.alerts = [];
            
            // Update UI
            updateAlertsUI([]);
            updateNotificationCount(0);
            
            // Show success notification
            window.utils.showNotification('All alerts marked as read', 'success');
        });
    }
    
    // Populate notification list
    function updateNotificationList() {
        if (!dashboardState.alerts || dashboardState.alerts.length === 0) {
            notificationList.innerHTML = `
                <div class="empty-notifications">
                    <i class="fas fa-check-circle"></i>
                    <span>No notifications</span>
                </div>
            `;
            return;
        }
        
        // Sort alerts by timestamp (newest first)
        const sortedAlerts = [...dashboardState.alerts].sort((a, b) => {
            return new Date(b.timestamp) - new Date(a.timestamp);
        });
        
        // Show only first 5 notifications
        const recentAlerts = sortedAlerts.slice(0, 5);
        
        notificationList.innerHTML = '';
        
        recentAlerts.forEach(alert => {
            const alertLevel = alert.alert_level || 'info';
            const iconClass = alertLevel === 'critical' ? 'fa-exclamation-triangle' :
                            alertLevel === 'warning' ? 'fa-exclamation-circle' : 'fa-info-circle';
            
            const notificationItem = document.createElement('div');
            notificationItem.className = 'notification-item';
            notificationItem.dataset.alertId = alert.id;
            
            notificationItem.innerHTML = `
                <div class="notification-icon ${alertLevel}">
                    <i class="fas ${iconClass}"></i>
                </div>
                <div class="notification-content">
                    <div class="notification-title">${getAlertTitle(alert)}</div>
                    <div class="notification-message">${window.utils.truncateString(getAlertMessage(alert), 60)}</div>
                    <div class="notification-time">${window.utils.formatDate(alert.timestamp, 'relative')}</div>
                </div>
            `;
            
            notificationItem.addEventListener('click', function(e) {
                e.preventDefault();
                showAlertDetails(alert.id);
            });
            
            notificationList.appendChild(notificationItem);
        });
    }
    
    // Update notification list when the bell is clicked
    notificationBell.addEventListener('click', function() {
        updateNotificationList();
    });
}

/**
 * Update status cards with latest data
 */
function updateStatusCards() {
    // Set up auto-refresh for status cards
    setInterval(async () => {
        try {
            // Fetch data for status cards
            const pipelines = await window.apiService.fetchPipelines();
            const deviceCount = pipelines.reduce((count, pipeline) => count + pipeline.devices.length, 0);
            const onlineDeviceCount = pipelines.reduce((count, pipeline) => {
                return count + pipeline.devices.filter(device => device.status === 'online').length;
            }, 0);
            
            // Fetch latest sensor data
            const latestData = await window.apiService.fetchLatestStatus();
            
            // Calculate average temperature
            const temperatures = latestData.data
                .filter(item => item.measurement.includes('temperature'))
                .map(item => parseFloat(item.value));
            
            const avgTemperature = temperatures.length > 0 ?
                temperatures.reduce((sum, value) => sum + value, 0) / temperatures.length :
                0;
            
            // Calculate average pressure
            const pressures = latestData.data
                .filter(item => item.measurement.includes('pressure'))
                .map(item => parseFloat(item.value));
            
            const avgPressure = pressures.length > 0 ?
                pressures.reduce((sum, value) => sum + value, 0) / pressures.length :
                0;
            
            // Count alerts by severity
            const criticalAlerts = dashboardState.alerts.filter(alert => alert.alert_level === 'critical').length;
            const warningAlerts = dashboardState.alerts.filter(alert => alert.alert_level === 'warning').length;
            
            // Update status cards
            updateStatusCard('smart-bolts', deviceCount, onlineDeviceCount);
            updateStatusCard('temperature', avgTemperature.toFixed(1));
            updateStatusCard('pressure', avgPressure.toFixed(1));
            updateStatusCard('alerts', dashboardState.alerts.length, criticalAlerts, warningAlerts);
            
        } catch (error) {
            console.error('Error updating status cards:', error);
        }
    }, 30000); // Update every 30 seconds
}

/**
 * Update a specific status card
 * @param {string} cardType - Card type ('smart-bolts', 'temperature', 'pressure', 'alerts')
 * @param {number|string} value - Main value
 * @param {number|string} secondaryValue - Secondary value (for subtitle)
 * @param {number|string} tertiaryValue - Tertiary value (for alerts)
 */
function updateStatusCard(cardType, value, secondaryValue, tertiaryValue) {
    // Find card
    const cards = document.querySelectorAll('.status-card');
    let card;
    
    for (const c of cards) {
        const title = c.querySelector('h3').textContent.toLowerCase();
        
        if (title.includes(cardType)) {
            card = c;
            break;
        }
    }
    
    if (!card) {
        return;
    }
    
    // Find card elements
    const valueEl = card.querySelector('.card-value');
    const subtitleEl = card.querySelector('.card-subtitle');
    
    if (!valueEl) {
        return;
    }
    
    // Update icon class based on value
    const iconEl = card.querySelector('.card-icon');
    
    if (iconEl) {
        let iconClass = 'healthy';
        
        switch (cardType) {
            case 'temperature':
                if (value >= CHART_DEFAULTS.temperature.critical) {
                    iconClass = 'critical';
                } else if (value >= CHART_DEFAULTS.temperature.warning) {
                    iconClass = 'warning';
                }
                break;
                
            case 'pressure':
                if (value >= CHART_DEFAULTS.pressure.critical) {
                    iconClass = 'critical';
                } else if (value >= CHART_DEFAULTS.pressure.warning) {
                    iconClass = 'warning';
                }
                break;
                
            case 'alerts':
                if (value > 0) {
                    iconClass = value >= 5 ? 'critical' : 'warning';
                }
                break;
        }
        
        // Update icon class
        iconEl.className = `card-icon ${iconClass}`;
    }
    
    // Update value
    switch (cardType) {
        case 'smart-bolts':
            valueEl.textContent = value;
            if (subtitleEl && secondaryValue !== undefined) {
                subtitleEl.textContent = `${secondaryValue} Online`;
            }
            break;
            
        case 'temperature':
            valueEl.textContent = `${value}°C`;
            break;
            
        case 'pressure':
            valueEl.textContent = `${value} bar`;
            break;
            
        case 'alerts':
            valueEl.textContent = value;
            if (subtitleEl && secondaryValue !== undefined && tertiaryValue !== undefined) {
                subtitleEl.textContent = `${secondaryValue} Critical, ${tertiaryValue} Warning`;
            }
            break;
    }
}

// Export dashboard functions
window.dashboard = {
    initDashboard,
    refreshData: window.chartService.refreshPipelineData,
    updateStatusCards
};