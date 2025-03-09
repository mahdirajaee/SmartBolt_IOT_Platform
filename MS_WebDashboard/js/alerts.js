/**
 * Alerts Module for Smart IoT Bolt Dashboard
 * Handles alert management, filtering, and display
 */

// Alerts state
let alertsState = {
    alerts: [],
    activeAlerts: [],
    historyAlerts: [],
    filters: {
        status: 'all',
        severity: 'all',
        type: 'all',
        time: '24h',
        search: ''
    },
    refreshInterval: null
};

/**
 * Initialize the alerts module
 */
function initAlerts() {
    // Load user authentication data
    window.authService.initAuth();
    
    // Update user interface with current user data
    window.authService.updateUserInterface();
    
    // Initialize UI elements
    initUIElements();
    
    // Initialize theme switcher
    window.utils.initThemeSwitcher();
    
    // Initialize API service
    window.apiService.initApiService().then(() => {
        // Load alerts data
        loadAlertsData();
        
        // Start refresh interval
        startRefreshInterval();
    });
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
    
    // Alert Filter buttons
    const filterButtons = document.querySelectorAll('.filter-btn');
    
    filterButtons.forEach(button => {
        button.addEventListener('click', function() {
            const filterType = this.dataset.filter;
            const filterValue = this.dataset.value;
            
            // Update filter in state
            alertsState.filters[filterType] = filterValue;
            
            // Remove active class from all buttons in this filter group
            const filterGroup = this.closest('.filter-buttons');
            filterGroup.querySelectorAll('.filter-btn').forEach(btn => {
                btn.classList.remove('active');
            });
            
            // Add active class to clicked button
            this.classList.add('active');
            
            // Apply filters
            applyFilters();
        });
    });
    
    // Search box
    const searchInput = document.getElementById('alert-search');
    
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            alertsState.filters.search = this.value;
            applyFilters();
        });
    }
    
    // Initialize select all checkbox
    const selectAllCheckbox = document.getElementById('select-all-alerts');
    
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            const alertCheckboxes = document.querySelectorAll('.alert-select');
            
            alertCheckboxes.forEach(checkbox => {
                checkbox.checked = this.checked;
            });
            
            // Update bulk action button state
            updateBulkActionButtonState();
        });
    }
    
    // Initialize refresh button
    const refreshButton = document.querySelector('.refresh-alerts');
    
    if (refreshButton) {
        refreshButton.addEventListener('click', function() {
            loadAlertsData();
        });
    }
    
    // Initialize resolve all button
    const resolveAllButton = document.querySelector('.resolve-all-btn');
    
    if (resolveAllButton) {
        resolveAllButton.addEventListener('click', function() {
            // Show confirmation dialog
            showBulkActionModal('resolve');
        });
    }
    
    // Initialize alert checkboxes
    initAlertCheckboxes();
    
    // Initialize modal handlers
    initAlertDetailsModal();
    initResolveAlertModal();
    initBulkActionModal();
}

/**
 * Initialize alert checkboxes
 */
function initAlertCheckboxes() {
    const alertCheckboxes = document.querySelectorAll('.alert-select');
    
    alertCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            // Update bulk action button state
            updateBulkActionButtonState();
        });
    });
}

/**
 * Initialize alert details modal
 */
function initAlertDetailsModal() {
    const modal = document.getElementById('alert-details-modal');
    
    if (!modal) return;
    
    const closeButtons = modal.querySelectorAll('.modal-close, .modal-close-button');
    const resolveButton = document.getElementById('resolve-alert-btn');
    
    closeButtons.forEach(button => {
        button.addEventListener('click', function() {
            modal.classList.remove('show');
        });
    });
    
    if (resolveButton) {
        resolveButton.addEventListener('click', function() {
            const alertId = this.dataset.alertId;
            showResolveAlertModal(alertId);
            modal.classList.remove('show');
        });
    }
}

/**
 * Initialize resolve alert modal
 */
function initResolveAlertModal() {
    const modal = document.getElementById('resolve-alert-modal');
    
    if (!modal) return;
    
    const closeButtons = modal.querySelectorAll('.modal-close, .modal-close-button');
    const confirmButton = document.getElementById('confirm-resolve-btn');
    
    closeButtons.forEach(button => {
        button.addEventListener('click', function() {
            modal.classList.remove('show');
        });
    });
    
    if (confirmButton) {
        confirmButton.addEventListener('click', function() {
            const alertId = this.dataset.alertId;
            const resolutionNote = document.getElementById('resolution-note').value;
            const resolutionAction = document.getElementById('resolution-action').value;
            
            resolveAlert(alertId, resolutionNote, resolutionAction);
            modal.classList.remove('show');
        });
    }
}

/**
 * Initialize bulk action modal
 */
function initBulkActionModal() {
    const modal = document.getElementById('bulk-action-modal');
    
    if (!modal) return;
    
    const closeButtons = modal.querySelectorAll('.modal-close, .modal-close-button');
    const confirmButton = document.getElementById('confirm-bulk-action-btn');
    const bulkActionSelect = document.getElementById('bulk-action');
    const resolutionNoteGroup = document.getElementById('bulk-resolution-note-group');
    
    closeButtons.forEach(button => {
        button.addEventListener('click', function() {
            modal.classList.remove('show');
        });
    });
    
    if (bulkActionSelect) {
        bulkActionSelect.addEventListener('change', function() {
            // Show/hide resolution note field based on action
            if (this.value === 'resolve' && resolutionNoteGroup) {
                resolutionNoteGroup.style.display = 'block';
            } else if (resolutionNoteGroup) {
                resolutionNoteGroup.style.display = 'none';
            }
        });
    }
    
    if (confirmButton) {
        confirmButton.addEventListener('click', function() {
            const action = bulkActionSelect.value;
            
            if (!action) {
                window.utils.showNotification('Please select an action', 'warning');
                return;
            }
            
            // Get selected alert IDs
            const selectedAlerts = getSelectedAlerts();
            
            if (selectedAlerts.length === 0) {
                window.utils.showNotification('No alerts selected', 'warning');
                return;
            }
            
            // Perform bulk action
            if (action === 'resolve') {
                const resolutionNote = document.getElementById('bulk-resolution-note').value;
                resolveBulkAlerts(selectedAlerts, resolutionNote);
            } else if (action === 'delete') {
                deleteBulkAlerts(selectedAlerts);
            } else if (action === 'export') {
                exportAlerts(selectedAlerts);
            }
            
            // Close modal
            modal.classList.remove('show');
        });
    }
}

/**
 * Start data refresh interval
 */
function startRefreshInterval() {
    // Clear existing interval if any
    if (alertsState.refreshInterval) {
        clearInterval(alertsState.refreshInterval);
    }
    
    // Set up new interval (refresh every 60 seconds)
    alertsState.refreshInterval = setInterval(() => {
        loadAlertsData();
    }, 60000);
}

/**
 * Load alerts data from API
 */
async function loadAlertsData() {
    try {
        // Show loading state
        showAlertsLoading(true);
        
        // Fetch alerts from API
        const alerts = await window.apiService.fetchAlerts();
        
        if (alerts && alerts.alerts) {
            // Store in state
            alertsState.alerts = alerts.alerts;
            
            // Separate active and resolved alerts
            const active = alerts.alerts.filter(alert => alert.status !== 'resolved');
            const history = alerts.alerts.filter(alert => alert.status === 'resolved');
            
            alertsState.activeAlerts = active;
            alertsState.historyAlerts = history;
            
            // Update alert counts
            updateAlertCounts(active.length, history.length);
            
            // Render alerts
            renderActiveAlerts(active);
            renderAlertHistory(history);
            
            // Initialize alert action buttons
            initAlertActionButtons();
            
            // Initialize alert checkboxes
            initAlertCheckboxes();
        }
        
        // Hide loading state
        showAlertsLoading(false);
        
        // Update last updated time
        updateLastUpdatedTime();
        
    } catch (error) {
        console.error('Error loading alerts data:', error);
        window.utils.showNotification('Failed to load alerts data. Please try again.', 'error');
        showAlertsLoading(false);
    }
}

/**
 * Show or hide alerts loading indicators
 * @param {boolean} show - Whether to show or hide loading indicators
 */
function showAlertsLoading(show) {
    // Find table containers
    const tableContainers = document.querySelectorAll('.alerts-table-container');
    
    tableContainers.forEach(container => {
        if (show) {
            // Create loading overlay if it doesn't exist
            let loadingOverlay = container.querySelector('.loading-overlay');
            if (!loadingOverlay) {
                loadingOverlay = document.createElement('div');
                loadingOverlay.className = 'loading-overlay';
                loadingOverlay.innerHTML = `
                    <div class="spinner">
                        <i class="fas fa-spinner fa-spin"></i>
                    </div>
                `;
                container.appendChild(loadingOverlay);
            }
            loadingOverlay.style.display = 'flex';
        } else {
            // Hide loading overlay
            const loadingOverlay = container.querySelector('.loading-overlay');
            if (loadingOverlay) {
                loadingOverlay.style.display = 'none';
            }
        }
    });
}

/**
 * Update alert counts in the UI
 * @param {number} activeCount - Number of active alerts
 * @param {number} historyCount - Number of resolved alerts
 */
function updateAlertCounts(activeCount, historyCount) {
    const activeCountEl = document.getElementById('active-alert-count');
    const historyCountEl = document.getElementById('history-alert-count');
    
    if (activeCountEl) {
        activeCountEl.textContent = activeCount;
    }
    
    if (historyCountEl) {
        historyCountEl.textContent = historyCount;
    }
    
    // Update summary cards
    const criticalAlerts = alertsState.activeAlerts.filter(alert => alert.alert_level === 'critical').length;
    const warningAlerts = alertsState.activeAlerts.filter(alert => alert.alert_level === 'warning').length;
    const infoAlerts = alertsState.activeAlerts.filter(alert => alert.alert_level === 'info').length;
    
    const criticalCard = document.querySelector('.alert-summary-card:nth-child(1) .card-value');
    const warningCard = document.querySelector('.alert-summary-card:nth-child(2) .card-value');
    const infoCard = document.querySelector('.alert-summary-card:nth-child(3) .card-value');
    const resolvedCard = document.querySelector('.alert-summary-card:nth-child(4) .card-value');
    
    if (criticalCard) criticalCard.textContent = criticalAlerts;
    if (warningCard) warningCard.textContent = warningAlerts;
    if (infoCard) infoCard.textContent = infoAlerts;
    if (resolvedCard) resolvedCard.textContent = historyCount;
    
    // Update notification badge
    const alertBadges = document.querySelectorAll('.alert-badge');
    
    alertBadges.forEach(badge => {
        badge.textContent = activeCount;
        
        if (activeCount > 0) {
            badge.style.display = 'flex';
        } else {
            badge.style.display = 'none';
        }
    });
}

/**
 * Render active alerts in the table
 * @param {Array} alerts - List of active alerts
 */
function renderActiveAlerts(alerts) {
    const tableBody = document.querySelector('.alerts-table:first-of-type tbody');
    
    if (!tableBody) return;
    
    // Clear current rows
    tableBody.innerHTML = '';
    
    if (alerts.length === 0) {
        // Show empty state
        tableBody.innerHTML = `
            <tr>
                <td colspan="9" class="empty-state">
                    <div class="empty-state-icon">
                        <i class="fas fa-check-circle"></i>
                    </div>
                    <div class="empty-state-text">No active alerts</div>
                </td>
            </tr>
        `;
        return;
    }
    
    // Sort alerts by timestamp (newest first)
    alerts.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    
    // Apply filters
    const filteredAlerts = applyFiltersToAlerts(alerts);
    
    if (filteredAlerts.length === 0) {
        // Show empty state for filtered results
        tableBody.innerHTML = `
            <tr>
                <td colspan="9" class="empty-state">
                    <div class="empty-state-icon">
                        <i class="fas fa-filter"></i>
                    </div>
                    <div class="empty-state-text">No alerts match your filters</div>
                </td>
            </tr>
        `;
        return;
    }
    
    // Create rows for each alert
    filteredAlerts.forEach(alert => {
        const row = document.createElement('tr');
        row.className = 'alert-row';
        row.dataset.alertId = alert.id;
        
        // Format severity class
        const severityClass = alert.alert_level || 'info';
        const severityIcon = severityClass === 'critical' ? 'fa-exclamation-triangle' : 
                          severityClass === 'warning' ? 'fa-exclamation-circle' : 'fa-info-circle';
        
        row.innerHTML = `
            <td>
                <div class="alert-checkbox">
                    <input type="checkbox" id="alert-${alert.id}" class="alert-select" data-alert-id="${alert.id}">
                    <label for="alert-${alert.id}"></label>
                </div>
            </td>
            <td>${alert.id}</td>
            <td>
                <span class="alert-severity ${severityClass}">
                    <i class="fas ${severityIcon}"></i> ${capitalize(severityClass)}
                </span>
            </td>
            <td>${capitalize(alert.type || 'System')}</td>
            <td class="alert-message">${alert.message || formatAlertMessage(alert)}</td>
            <td>${alert.pipeline_id || 'N/A'}</td>
            <td>${alert.device_id || alert.bolt_id || 'N/A'}</td>
            <td>${window.utils.formatDate(alert.timestamp, 'relative')}</td>
            <td>
                <div class="action-buttons">
                    <button class="btn-action view-alert" title="View Details" data-alert-id="${alert.id}">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="btn-action resolve-alert" title="Resolve Alert" data-alert-id="${alert.id}">
                        <i class="fas fa-check"></i>
                    </button>
                </div>
            </td>
        `;
        
        tableBody.appendChild(row);
    });
    
    // Update pagination
    updateActivePagination(filteredAlerts.length);
}

/**
 * Render alert history in the table
 * @param {Array} alerts - List of resolved alerts
 */
function renderAlertHistory(alerts) {
    const tableBody = document.querySelector('.alerts-table:last-of-type tbody');
    
    if (!tableBody) return;
    
    // Clear current rows
    tableBody.innerHTML = '';
    
    if (alerts.length === 0) {
        // Show empty state
        tableBody.innerHTML = `
            <tr>
                <td colspan="9" class="empty-state">
                    <div class="empty-state-icon">
                        <i class="fas fa-history"></i>
                    </div>
                    <div class="empty-state-text">No alert history</div>
                </td>
            </tr>
        `;
        return;
    }
    
    // Sort alerts by timestamp (newest first)
    alerts.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
    
    // Apply filters
    const filteredAlerts = applyFiltersToAlerts(alerts);
    
    if (filteredAlerts.length === 0) {
        // Show empty state for filtered results
        tableBody.innerHTML = `
            <tr>
                <td colspan="9" class="empty-state">
                    <div class="empty-state-icon">
                        <i class="fas fa-filter"></i>
                    </div>
                    <div class="empty-state-text">No alerts match your filters</div>
                </td>
            </tr>
        `;
        return;
    }
    
    // Create rows for each alert
    filteredAlerts.forEach(alert => {
        const row = document.createElement('tr');
        row.className = 'alert-row';
        row.dataset.alertId = alert.id;
        
        // Format severity class
        const severityClass = alert.alert_level || 'info';
        const severityIcon = severityClass === 'critical' ? 'fa-exclamation-triangle' : 
                          severityClass === 'warning' ? 'fa-exclamation-circle' : 'fa-info-circle';
        
        row.innerHTML = `
            <td>
                <div class="alert-checkbox">
                    <input type="checkbox" id="hist-${alert.id}" class="alert-select" data-alert-id="${alert.id}">
                    <label for="hist-${alert.id}"></label>
                </div>
            </td>
            <td>${alert.id}</td>
            <td>
                <span class="alert-severity ${severityClass}">
                    <i class="fas ${severityIcon}"></i> ${capitalize(severityClass)}
                </span>
            </td>
            <td>${capitalize(alert.type || 'System')}</td>
            <td class="alert-message">${alert.message || formatAlertMessage(alert)}</td>
            <td>${alert.pipeline_id || 'N/A'}</td>
            <td>${alert.device_id || alert.bolt_id || 'N/A'}</td>
            <td>${window.utils.formatDate(alert.timestamp, 'relative')}</td>
            <td>
                <span class="alert-status resolved">
                    <i class="fas fa-check"></i> Resolved
                </span>
            </td>
        `;
        
        tableBody.appendChild(row);
    });
    
    // Update pagination
    updateHistoryPagination(filteredAlerts.length);
}

/**
 * Initialize alert action buttons
 */
function initAlertActionButtons() {
    // View alert buttons
    const viewButtons = document.querySelectorAll('.view-alert');
    
    viewButtons.forEach(button => {
        button.addEventListener('click', function() {
            const alertId = this.dataset.alertId;
            showAlertDetails(alertId);
        });
    });
    
    // Resolve alert buttons
    const resolveButtons = document.querySelectorAll('.resolve-alert');
    
    resolveButtons.forEach(button => {
        button.addEventListener('click', function() {
            const alertId = this.dataset.alertId;
            showResolveAlertModal(alertId);
        });
    });
}

/**
 * Show alert details modal
 * @param {string} alertId - Alert ID
 */
function showAlertDetails(alertId) {
    // Find the alert in state
    const alert = findAlertById(alertId);
    
    if (!alert) {
        window.utils.showNotification('Alert not found', 'error');
        return;
    }
    
    // Get the modal
    const modal = document.getElementById('alert-details-modal');
    
    if (!modal) return;
    
    // Get alert elements
    const severityEl = modal.querySelector('.alert-details-severity');
    const idEl = modal.querySelector('.alert-details-id span');
    const typeEl = modal.querySelector('.detail-value:nth-of-type(1)');
    const messageEl = modal.querySelector('.detail-value:nth-of-type(2)');
    const pipelineEl = modal.querySelector('.detail-value:nth-of-type(3)');
    const deviceEl = modal.querySelector('.detail-value:nth-of-type(4)');
    const thresholdEl = modal.querySelector('.detail-value:nth-of-type(5)');
    const valueEl = modal.querySelector('.detail-value:nth-of-type(6)');
    const timeEl = modal.querySelector('.detail-value:nth-of-type(7)');
    const statusEl = modal.querySelector('.detail-value:nth-of-type(8)');
    const resolveBtn = modal.querySelector('#resolve-alert-btn');
    
    // Update severity class
    if (severityEl) {
        const severityClass = alert.alert_level || 'info';
        const severityIcon = severityClass === 'critical' ? 'fa-exclamation-triangle' : 
                          severityClass === 'warning' ? 'fa-exclamation-circle' : 'fa-info-circle';
        
        severityEl.className = `alert-details-severity ${severityClass}`;
        severityEl.innerHTML = `
            <i class="fas ${severityIcon}"></i>
            <span>${capitalize(severityClass)}</span>
        `;
    }
    
    // Update alert details
    if (idEl) idEl.textContent = alert.id;
    if (typeEl) typeEl.textContent = capitalize(alert.type || 'System');
    if (messageEl) messageEl.textContent = alert.message || formatAlertMessage(alert);
    if (pipelineEl) pipelineEl.textContent = alert.pipeline_id || 'N/A';
    if (deviceEl) deviceEl.textContent = alert.device_id || alert.bolt_id || 'N/A';
    if (thresholdEl) thresholdEl.textContent = formatThreshold(alert);
    if (valueEl) {
        valueEl.textContent = formatValue(alert);
        valueEl.className = `detail-value ${alert.alert_level || 'info'}`;
    }
    if (timeEl) timeEl.textContent = window.utils.formatDate(alert.timestamp, 'datetime');
    if (statusEl) statusEl.textContent = capitalize(alert.status || 'Active');
    
    // Update resolve button
    if (resolveBtn) {
        resolveBtn.dataset.alertId = alert.id;
        
        // Hide resolve button for resolved alerts
        if (alert.status === 'resolved') {
            resolveBtn.style.display = 'none';
        } else {
            resolveBtn.style.display = 'inline-flex';
        }
    }
    
    // Show modal
    modal.classList.add('show');
}

/**
 * Show resolve alert modal
 * @param {string} alertId - Alert ID
 */
function showResolveAlertModal(alertId) {
    // Find the alert in state
    const alert = findAlertById(alertId);
    
    if (!alert) {
        window.utils.showNotification('Alert not found', 'error');
        return;
    }
    
    // Get the modal
    const modal = document.getElementById('resolve-alert-modal');
    
    if (!modal) return;
    
    // Get message element
    const messageEl = modal.querySelector('.resolve-alert-message strong');
    
    // Get confirm button
    const confirmBtn = modal.querySelector('#confirm-resolve-btn');
    
    // Update message
    if (messageEl) messageEl.textContent = alertId;
    
    // Update confirm button
    if (confirmBtn) confirmBtn.dataset.alertId = alertId;
    
    // Reset form
    const noteEl = modal.querySelector('#resolution-note');
    const actionEl = modal.querySelector('#resolution-action');
    
    if (noteEl) noteEl.value = '';
    if (actionEl) actionEl.selectedIndex = 0;
    
    // Show modal
    modal.classList.add('show');
}

/**
 * Show bulk action modal
 * @param {string} defaultAction - Default action to select
 */
function showBulkActionModal(defaultAction = '') {
    // Get selected alerts
    const selectedAlerts = getSelectedAlerts();
    
    if (selectedAlerts.length === 0) {
        window.utils.showNotification('No alerts selected', 'warning');
        return;
    }
    
    // Get the modal
    const modal = document.getElementById('bulk-action-modal');
    
    if (!modal) return;
    
    // Get count element
    const countEl = modal.querySelector('#selected-count');
    
    // Get action select
    const actionSelect = modal.querySelector('#bulk-action');
    
    // Get resolution note group
    const resolutionNoteGroup = modal.querySelector('#bulk-resolution-note-group');
    
    // Update count
    if (countEl) countEl.textContent = selectedAlerts.length;
    
    // Set default action
    if (actionSelect && defaultAction) {
        actionSelect.value = defaultAction;
        
        // Show/hide resolution note field based on action
        if (defaultAction === 'resolve' && resolutionNoteGroup) {
            resolutionNoteGroup.style.display = 'block';
        } else if (resolutionNoteGroup) {
            resolutionNoteGroup.style.display = 'none';
        }
    } else if (actionSelect) {
        actionSelect.selectedIndex = 0;
        
        // Hide resolution note field
        if (resolutionNoteGroup) {
            resolutionNoteGroup.style.display = 'none';
        }
    }
    
    // Reset form
    const noteEl = modal.querySelector('#bulk-resolution-note');
    
    if (noteEl) noteEl.value = '';
    
    // Show modal
    modal.classList.add('show');
}

/**
 * Resolve an alert
 * @param {string} alertId - Alert ID
 * @param {string} resolutionNote - Resolution note
 * @param {string} resolutionAction - Resolution action
 */
async function resolveAlert(alertId, resolutionNote, resolutionAction) {
    try {
        // Find the alert
        const alert = findAlertById(alertId);
        
        if (!alert) {
            throw new Error('Alert not found');
        }
        
        // Prepare resolution data
        const resolutionData = {
            alert_id: alertId,
            resolution_note: resolutionNote,
            resolution_action: resolutionAction
        };
        
        // In a real implementation, this would call the API to resolve the alert
        // await window.apiService.resolveAlert(resolutionData);
        
        // For this implementation, update the alert in state
        alert.status = 'resolved';
        alert.resolution_note = resolutionNote;
        alert.resolution_action = resolutionAction;
        alert.resolution_time = new Date().toISOString();
        
        // Move from active to history
        alertsState.activeAlerts = alertsState.activeAlerts.filter(a => a.id !== alertId);
        alertsState.historyAlerts.push(alert);
        
        // Show success notification
        window.utils.showNotification('Alert resolved successfully', 'success');
        
        // Refresh alerts
        renderActiveAlerts(alertsState.activeAlerts);
        renderAlertHistory(alertsState.historyAlerts);
        
        // Update counts
        updateAlertCounts(alertsState.activeAlerts.length, alertsState.historyAlerts.length);
        
        // Re-initialize alert action buttons
        initAlertActionButtons();
        
        // Re-initialize alert checkboxes
        initAlertCheckboxes();
        
    } catch (error) {
        console.error('Error resolving alert:', error);
        window.utils.showNotification('Failed to resolve alert. Please try again.', 'error');
    }
}

/**
 * Resolve multiple alerts in bulk
 * @param {Array} alertIds - List of alert IDs
 * @param {string} resolutionNote - Resolution note
 */
async function resolveBulkAlerts(alertIds, resolutionNote) {
    try {
        // Prepare resolution data
        const resolutionData = {
            alert_ids: alertIds,
            resolution_note: resolutionNote
        };
        
        // In a real implementation, this would call the API to resolve the alerts
        // await window.apiService.resolveBulkAlerts(resolutionData);
        
        // For this implementation, update the alerts in state
        const resolvedAlerts = [];
        
        alertIds.forEach(id => {
            const alert = findAlertById(id);
            
            if (alert && alert.status !== 'resolved') {
                alert.status = 'resolved';
                alert.resolution_note = resolutionNote;
                alert.resolution_time = new Date().toISOString();
                
                resolvedAlerts.push(alert);
            }
        });
        
        // Move from active to history
        alertsState.activeAlerts = alertsState.activeAlerts.filter(a => !alertIds.includes(a.id));
        alertsState.historyAlerts = [...alertsState.historyAlerts, ...resolvedAlerts];
        
        // Show success notification
        window.utils.showNotification(`${resolvedAlerts.length} alerts resolved successfully`, 'success');
        
        // Refresh alerts
        renderActiveAlerts(alertsState.activeAlerts);
        renderAlertHistory(alertsState.historyAlerts);
        
        // Update counts
        updateAlertCounts(alertsState.activeAlerts.length, alertsState.historyAlerts.length);
        
        // Re-initialize alert action buttons
        initAlertActionButtons();
        
        // Re-initialize alert checkboxes
        initAlertCheckboxes();
        
    } catch (error) {
        console.error('Error resolving alerts:', error);
        window.utils.showNotification('Failed to resolve alerts. Please try again.', 'error');
    }
}

/**
 * Delete multiple alerts in bulk
 * @param {Array} alertIds - List of alert IDs
 */
async function deleteBulkAlerts(alertIds) {
    try {
        // In a real implementation, this would call the API to delete the alerts
        // await window.apiService.deleteBulkAlerts(alertIds);
        
        // For this implementation, remove the alerts from state
        alertsState.activeAlerts = alertsState.activeAlerts.filter(a => !alertIds.includes(a.id));
        alertsState.historyAlerts = alertsState.historyAlerts.filter(a => !alertIds.includes(a.id));
        alertsState.alerts = [...alertsState.activeAlerts, ...alertsState.historyAlerts];
        
        // Show success notification
        window.utils.showNotification(`${alertIds.length} alerts deleted successfully`, 'success');
        
        // Refresh alerts
        renderActiveAlerts(alertsState.activeAlerts);
        renderAlertHistory(alertsState.historyAlerts);
        
        // Update counts
        updateAlertCounts(alertsState.activeAlerts.length, alertsState.historyAlerts.length);
        
        // Re-initialize alert action buttons
        initAlertActionButtons();
        
        // Re-initialize alert checkboxes
        initAlertCheckboxes();
        
    } catch (error) {
        console.error('Error deleting alerts:', error);
        window.utils.showNotification('Failed to delete alerts. Please try again.', 'error');
    }
}

/**
 * Export alerts to CSV
 * @param {Array} alertIds - List of alert IDs to export
 */
function exportAlerts(alertIds) {
    try {
        // Find all selected alerts
        const alerts = alertsState.alerts.filter(a => alertIds.includes(a.id));
        
        if (alerts.length === 0) {
            throw new Error('No alerts found');
        }
        
        // Prepare CSV data
        const headers = [
            'Alert ID',
            'Severity',
            'Type',
            'Message',
            'Pipeline',
            'Device',
            'Value',
            'Threshold',
            'Status',
            'Timestamp'
        ];
        
        const rows = alerts.map(alert => [
            alert.id,
            alert.alert_level || 'info',
            alert.type || 'System',
            alert.message || formatAlertMessage(alert),
            alert.pipeline_id || 'N/A',
            alert.device_id || alert.bolt_id || 'N/A',
            alert.value || alert.predicted_value || 'N/A',
            alert.threshold || 'N/A',
            alert.status || 'Active',
            alert.timestamp
        ]);
        
        // Create CSV content
        const csvContent = [
            headers.join(','),
            ...rows.map(row => row.join(','))
        ].join('\n');
        
        // Create download link
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `smart-bolt-alerts-${new Date().toISOString().slice(0, 10)}.csv`);
        link.style.display = 'none';
        
        // Add to document, click, and remove
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        // Show success notification
        window.utils.showNotification(`${alerts.length} alerts exported successfully`, 'success');
        
    } catch (error) {
        console.error('Error exporting alerts:', error);
        window.utils.showNotification('Failed to export alerts. Please try again.', 'error');
    }
}

/**
 * Apply filters to the alerts tables
 */
function applyFilters() {
    // Apply filters to active alerts
    renderActiveAlerts(alertsState.activeAlerts);
    
    // Apply filters to history alerts
    renderAlertHistory(alertsState.historyAlerts);
}

/**
 * Apply filters to a list of alerts
 * @param {Array} alerts - List of alerts
 * @returns {Array} - Filtered alerts
 */
function applyFiltersToAlerts(alerts) {
    return alerts.filter(alert => {
        // Filter by status
        if (alertsState.filters.status !== 'all') {
            const isActive = alert.status !== 'resolved';
            if (alertsState.filters.status === 'active' && !isActive) return false;
            if (alertsState.filters.status === 'resolved' && isActive) return false;
        }
        
        // Filter by severity
        if (alertsState.filters.severity !== 'all') {
            if (alert.alert_level !== alertsState.filters.severity) return false;
        }
        
        // Filter by type
        if (alertsState.filters.type !== 'all') {
            if (alert.type !== alertsState.filters.type) return false;
        }
        
        // Filter by time
        if (alertsState.filters.time !== 'all') {
            const alertTime = new Date(alert.timestamp);
            const now = new Date();
            
            if (alertsState.filters.time === '24h') {
                const oneDayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);
                if (alertTime < oneDayAgo) return false;
            } else if (alertsState.filters.time === '7d') {
                const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
                if (alertTime < sevenDaysAgo) return false;
            } else if (alertsState.filters.time === '30d') {
                const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
                if (alertTime < thirtyDaysAgo) return false;
            }
        }
        
        // Filter by search
        if (alertsState.filters.search) {
            const searchTerm = alertsState.filters.search.toLowerCase();
            const alertId = alert.id.toLowerCase();
            const alertType = (alert.type || 'System').toLowerCase();
            const alertMessage = (alert.message || formatAlertMessage(alert)).toLowerCase();
            const pipelineId = (alert.pipeline_id || '').toLowerCase();
            const deviceId = (alert.device_id || alert.bolt_id || '').toLowerCase();
            
            // Check if search term appears in any of these fields
            if (!alertId.includes(searchTerm) && 
                !alertType.includes(searchTerm) && 
                !alertMessage.includes(searchTerm) &&
                !pipelineId.includes(searchTerm) &&
                !deviceId.includes(searchTerm)) {
                return false;
            }
        }
        
        // If all filters pass, include the alert
        return true;
    });
}

/**
 * Update the active alerts pagination
 * @param {number} count - Number of alerts
 */
function updateActivePagination(count) {
    const paginationInfo = document.querySelector('.alerts-pagination:first-of-type .pagination-info span:first-child');
    const paginationTotal = document.querySelector('.alerts-pagination:first-of-type .pagination-info span:last-child');
    const currentPage = document.querySelector('.alerts-pagination:first-of-type .current-page');
    const totalPages = document.querySelector('.alerts-pagination:first-of-type .total-pages');
    
    if (paginationInfo) paginationInfo.textContent = count > 0 ? `1-${count}` : '0-0';
    if (paginationTotal) paginationTotal.textContent = count;
    if (currentPage) currentPage.textContent = count > 0 ? '1' : '0';
    if (totalPages) totalPages.textContent = Math.ceil(count / 10) || '1';
}

/**
 * Update the alert history pagination
 * @param {number} count - Number of alerts
 */
function updateHistoryPagination(count) {
    const paginationInfo = document.querySelector('.alerts-pagination:last-of-type .pagination-info span:first-child');
    const paginationTotal = document.querySelector('.alerts-pagination:last-of-type .pagination-info span:last-child');
    const currentPage = document.querySelector('.alerts-pagination:last-of-type .current-page');
    const totalPages = document.querySelector('.alerts-pagination:last-of-type .total-pages');
    
    if (paginationInfo) paginationInfo.textContent = count > 0 ? `1-${Math.min(count, 5)}` : '0-0';
    if (paginationTotal) paginationTotal.textContent = count;
    if (currentPage) currentPage.textContent = count > 0 ? '1' : '0';
    if (totalPages) totalPages.textContent = Math.ceil(count / 5) || '1';
}

/**
 * Update the bulk action button state
 */
function updateBulkActionButtonState() {
    const selectedAlerts = getSelectedAlerts();
    const resolveAllBtn = document.querySelector('.resolve-all-btn');
    
    if (resolveAllBtn) {
        resolveAllBtn.disabled = selectedAlerts.length === 0;
    }
}

/**
 * Get the IDs of all selected alerts
 * @returns {Array} - List of selected alert IDs
 */
function getSelectedAlerts() {
    const selectedCheckboxes = document.querySelectorAll('.alert-select:checked');
    return Array.from(selectedCheckboxes).map(checkbox => checkbox.dataset.alertId);
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
 * Find an alert by ID
 * @param {string} alertId - Alert ID
 * @returns {Object|null} - Alert object or null if not found
 */
function findAlertById(alertId) {
    return alertsState.alerts.find(alert => alert.id === alertId) || null;
}

/**
 * Format an alert message based on alert data
 * @param {Object} alert - Alert data
 * @returns {string} - Formatted message
 */
function formatAlertMessage(alert) {
    let message = '';
    
    if (alert.type === 'temperature' || alert.type === 'pressure') {
        const measurement = capitalize(alert.type);
        const unit = alert.type === 'temperature' ? '°C' : 'bar';
        
        message = `${measurement} ${alert.predicted_value ? 'predicted to reach' : 'reached'} ${alert.value || alert.predicted_value}${unit} on Pipeline ${alert.pipeline_id || 'Unknown'}, Device ${alert.device_id || alert.bolt_id || 'Unknown'}`;
        
        if (alert.hours_until && alert.predicted_value) {
            message += ` in ${alert.hours_until} hour${alert.hours_until === 1 ? '' : 's'}`;
        }
    } else if (alert.type === 'system') {
        message = alert.message || 'System alert detected';
    } else {
        message = alert.message || 'Alert detected';
    }
    
    return message;
}

/**
 * Format threshold value based on alert data
 * @param {Object} alert - Alert data
 * @returns {string} - Formatted threshold
 */
function formatThreshold(alert) {
    if (alert.threshold) {
        const unit = alert.type === 'temperature' ? '°C' : alert.type === 'pressure' ? 'bar' : '';
        return `${alert.threshold}${unit}`;
    }
    
    return 'N/A';
}

/**
 * Format value based on alert data
 * @param {Object} alert - Alert data
 * @returns {string} - Formatted value
 */
function formatValue(alert) {
    const value = alert.value || alert.predicted_value;
    
    if (value) {
        const unit = alert.type === 'temperature' ? '°C' : alert.type === 'pressure' ? 'bar' : '';
        return `${value}${unit}`;
    }
    
    return 'N/A';
}

/**
 * Capitalize the first letter of a string
 * @param {string} str - String to capitalize
 * @returns {string} - Capitalized string
 */
function capitalize(str) {
    if (!str) return '';
    return str.charAt(0).toUpperCase() + str.slice(1);
}

// Export alerts functions
window.alerts = {
    initAlerts,
    loadAlertsData,
    showAlertDetails,
    resolveAlert
};