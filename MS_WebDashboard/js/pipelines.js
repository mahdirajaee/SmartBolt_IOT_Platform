/**
 * Pipeline Management Module for Smart IoT Bolt Dashboard
 * Handles pipeline configuration, visualization, and management
 */

// Pipelines state
let pipelinesState = {
    pipelines: [],
    selectedPipeline: null,
    refreshInterval: null,
    devices: {},
    pipelineDetails: {}
};

/**
 * Initialize the pipelines page
 */
async function initPipelines() {
    // Load user authentication data
    window.authService.initAuth();
    
    // Update user interface with current user data
    window.authService.updateUserInterface();
    
    // Initialize UI elements
    initUIElements();
    
    // Initialize theme switcher
    window.utils.initThemeSwitcher();
    
    // Initialize API service
    await window.apiService.initApiService();
    
    // Load initial data
    await loadPipelinesData();
    
    // Start data refresh interval
    startRefreshInterval();
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
    
    // Search box
    const searchInput = document.getElementById('pipeline-search');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            filterPipelines(this.value);
        });
    }
    
    // Refresh button
    const refreshButton = document.querySelector('.refresh-pipelines');
    if (refreshButton) {
        refreshButton.addEventListener('click', function() {
            loadPipelinesData();
        });
    }
    
    // Add pipeline button
    const addPipelineButton = document.getElementById('add-pipeline');
    if (addPipelineButton) {
        addPipelineButton.addEventListener('click', function() {
            showAddPipelineModal();
        });
    }
    
    // Add bolt button
    const addBoltButton = document.querySelector('.pipeline-detail-actions .btn-secondary');
    if (addBoltButton) {
        addBoltButton.addEventListener('click', function() {
            if (pipelinesState.selectedPipeline) {
                showAddBoltModal(pipelinesState.selectedPipeline);
            } else {
                window.utils.showNotification('Please select a pipeline first', 'warning');
            }
        });
    }
    
    // Save changes button
    const saveChangesButton = document.querySelector('.pipeline-detail-actions .btn-primary');
    if (saveChangesButton) {
        saveChangesButton.addEventListener('click', function() {
            if (pipelinesState.selectedPipeline) {
                savePipelineChanges(pipelinesState.selectedPipeline);
            } else {
                window.utils.showNotification('Please select a pipeline first', 'warning');
            }
        });
    }
    
    // Initialize add pipeline modal handlers
    initAddPipelineModal();
    
    // Initialize edit pipeline modal handlers
    initEditPipelineModal();
    
    // Initialize add bolt modal handlers
    initAddBoltModal();
    
    // Initialize confirmation modal handlers
    initConfirmationModal();
}

/**
 * Initialize add pipeline modal handlers
 */
function initAddPipelineModal() {
    const modal = document.getElementById('add-pipeline-modal');
    const closeButtons = modal.querySelectorAll('.modal-close, .modal-close-button');
    const saveButton = document.getElementById('save-pipeline');
    const form = document.getElementById('add-pipeline-form');
    
    closeButtons.forEach(button => {
        button.addEventListener('click', function() {
            modal.classList.remove('show');
        });
    });
    
    saveButton.addEventListener('click', function() {
        if (form.checkValidity()) {
            const pipelineId = document.getElementById('pipeline-id').value;
            const pipelineName = document.getElementById('pipeline-name').value;
            const description = document.getElementById('pipeline-description').value;
            
            addPipeline(pipelineId, pipelineName, description);
            modal.classList.remove('show');
        } else {
            form.reportValidity();
        }
    });
}

/**
 * Initialize edit pipeline modal handlers
 */
function initEditPipelineModal() {
    const modal = document.getElementById('edit-pipeline-modal');
    const closeButtons = modal.querySelectorAll('.modal-close, .modal-close-button');
    const updateButton = document.getElementById('update-pipeline');
    const form = document.getElementById('edit-pipeline-form');
    
    closeButtons.forEach(button => {
        button.addEventListener('click', function() {
            modal.classList.remove('show');
        });
    });
    
    updateButton.addEventListener('click', function() {
        if (form.checkValidity()) {
            const pipelineId = document.getElementById('edit-pipeline-id').value;
            const pipelineName = document.getElementById('edit-pipeline-name').value;
            const description = document.getElementById('edit-pipeline-description').value;
            
            updatePipeline(pipelineId, pipelineName, description);
            modal.classList.remove('show');
        } else {
            form.reportValidity();
        }
    });
}

/**
 * Initialize add bolt modal handlers
 */
function initAddBoltModal() {
    const modal = document.getElementById('add-bolt-modal');
    const closeButtons = modal.querySelectorAll('.modal-close, .modal-close-button');
    const saveButton = document.getElementById('save-bolt');
    const form = document.getElementById('add-bolt-form');
    
    closeButtons.forEach(button => {
        button.addEventListener('click', function() {
            modal.classList.remove('show');
        });
    });
    
    saveButton.addEventListener('click', function() {
        if (form.checkValidity()) {
            const pipelineId = document.getElementById('bolt-pipeline-id').value;
            const boltId = document.getElementById('bolt-id').value;
            const position = document.getElementById('bolt-position').value;
            const description = document.getElementById('bolt-description').value;
            
            addBolt(pipelineId, boltId, position, description);
            modal.classList.remove('show');
        } else {
            form.reportValidity();
        }
    });
}

/**
 * Initialize confirmation modal handlers
 */
function initConfirmationModal() {
    const modal = document.getElementById('confirmation-modal');
    const closeButtons = modal.querySelectorAll('.modal-close, .modal-close-button');
    const confirmButton = document.getElementById('confirm-action');
    
    closeButtons.forEach(button => {
        button.addEventListener('click', function() {
            modal.classList.remove('show');
        });
    });
    
    // The confirmation action will be set when the modal is shown
}

/**
 * Start data refresh interval
 */
function startRefreshInterval() {
    // Clear existing interval if any
    if (pipelinesState.refreshInterval) {
        clearInterval(pipelinesState.refreshInterval);
    }
    
    // Set up new interval (refresh every 30 seconds)
    pipelinesState.refreshInterval = setInterval(() => {
        refreshPipelinesData();
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
 * Load pipelines data from the API
 */
async function loadPipelinesData() {
    try {
        // Show loading indicator
        showPipelinesLoading(true);
        
        // Fetch pipelines
        const pipelines = await window.apiService.fetchPipelines();
        pipelinesState.pipelines = pipelines;
        
        // Update pipelines table
        updatePipelinesTable(pipelines);
        
        // If a pipeline is selected, load its details
        if (pipelinesState.selectedPipeline) {
            loadPipelineDetails(pipelinesState.selectedPipeline);
        }
        
        // Hide loading indicator
        showPipelinesLoading(false);
        
        // Update last updated time
        updateLastUpdatedTime();
        
    } catch (error) {
        console.error('Error loading pipelines data:', error);
        window.utils.showNotification('Failed to load pipelines data. Please try again.', 'error');
        showPipelinesLoading(false);
    }
}

/**
 * Refresh pipelines data
 */
function refreshPipelinesData() {
    loadPipelinesData();
}

/**
 * Show or hide pipelines loading indicators
 * @param {boolean} show - Whether to show or hide loading indicators
 */
function showPipelinesLoading(show) {
    // Add loading indicators if needed
}

/**
 * Update pipelines table with data
 * @param {Array} pipelines - List of pipelines
 */
function updatePipelinesTable(pipelines) {
    const tableBody = document.getElementById('pipeline-list');
    
    if (!tableBody) {
        return;
    }
    
    // Clear current rows
    tableBody.innerHTML = '';
    
    if (!pipelines || pipelines.length === 0) {
        const emptyRow = document.createElement('tr');
        emptyRow.innerHTML = `
            <td colspan="8" class="empty-table">
                <div class="empty-table-message">
                    <i class="fas fa-info-circle"></i>
                    <span>No pipelines found. Click "Add Pipeline" to create one.</span>
                </div>
            </td>
        `;
        tableBody.appendChild(emptyRow);
        return;
    }
    
    // Sort pipelines by ID
    pipelines.sort((a, b) => a.id.localeCompare(b.id));
    
    // Add rows for each pipeline
    pipelines.forEach(pipeline => {
        const row = document.createElement('tr');
        row.dataset.pipelineId = pipeline.id;
        
        // Get devices for this pipeline
        const devices = pipeline.devices || [];
        const deviceCount = devices.length;
        
        // Calculate average temperature and pressure
        let avgTemp = 0;
        let avgPressure = 0;
        let tempStatus = 'healthy';
        let pressureStatus = 'healthy';
        
        if (deviceCount > 0) {
            // Sum up temperature and pressure values
            devices.forEach(device => {
                avgTemp += device.temperature || 0;
                avgPressure += device.pressure || 0;
                
                // Check for warning/critical status
                const tempStatus = window.utils.getStatusFromValue(device.temperature, {
                    warning: 85,
                    critical: 95
                });
                
                const pressStatus = window.utils.getStatusFromValue(device.pressure, {
                    warning: 8.5,
                    critical: 9.5
                });
                
                // Use the most severe status
                if (tempStatus === 'critical' || pressStatus === 'critical') {
                    tempStatus = 'critical';
                } else if (tempStatus === 'warning' || pressStatus === 'warning' && tempStatus !== 'critical') {
                    tempStatus = 'warning';
                }
            });
            
            // Calculate averages
            avgTemp = avgTemp / deviceCount;
            avgPressure = avgPressure / deviceCount;
        }
        
        // Determine overall status
        let status = 'healthy';
        
        if (tempStatus === 'critical' || pressureStatus === 'critical') {
            status = 'critical';
        } else if (tempStatus === 'warning' || pressureStatus === 'warning') {
            status = 'warning';
        }
        
        // Create row content
        row.innerHTML = `
            <td>${pipeline.id}</td>
            <td>${pipeline.name || pipeline.id}</td>
            <td>${deviceCount} bolt${deviceCount !== 1 ? 's' : ''}</td>
            <td><span class="status-badge ${status}">${status.charAt(0).toUpperCase() + status.slice(1)}</span></td>
            <td>
                <div class="pipeline-value-bar">
                    <div class="pipeline-value">${avgTemp.toFixed(1)}°C</div>
                    <div class="progress-bar">
                        <div class="progress" style="width: ${Math.min(avgTemp, 100)}%; background-color: ${getProgressColor(avgTemp, 'temperature')};"></div>
                    </div>
                </div>
            </td>
            <td>
                <div class="pipeline-value-bar">
                    <div class="pipeline-value">${avgPressure.toFixed(1)} bar</div>
                    <div class="progress-bar">
                        <div class="progress" style="width: ${(avgPressure * 10)}%; background-color: ${getProgressColor(avgPressure, 'pressure')};"></div>
                    </div>
                </div>
            </td>
            <td>${window.utils.formatDate(pipeline.last_update || new Date(), 'relative')}</td>
            <td>
                <div class="action-buttons">
                    <button class="btn-action view" title="View Pipeline" data-pipeline-id="${pipeline.id}">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="btn-action edit" title="Edit Pipeline" data-pipeline-id="${pipeline.id}">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn-action delete" title="Delete Pipeline" data-pipeline-id="${pipeline.id}">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </td>
        `;
        
        tableBody.appendChild(row);
    });
    
    // Add event listeners to action buttons
    addActionButtonListeners();
}

/**
 * Get color for progress bar based on value
 * @param {number} value - Value to check
 * @param {string} type - Type of value ('temperature' or 'pressure')
 * @returns {string} - Color value (hex)
 */
function getProgressColor(value, type) {
    if (type === 'temperature') {
        if (value >= 95) {
            return '#ef4444'; // Critical
        } else if (value >= 85) {
            return '#f59e0b'; // Warning
        } else {
            return '#10b981'; // Healthy
        }
    } else if (type === 'pressure') {
        if (value >= 9.5) {
            return '#ef4444'; // Critical
        } else if (value >= 8.5) {
            return '#f59e0b'; // Warning
        } else {
            return '#10b981'; // Healthy
        }
    }
    
    return '#10b981'; // Default to healthy
}

/**
 * Add event listeners to pipeline action buttons
 */
function addActionButtonListeners() {
    // View pipeline buttons
    const viewButtons = document.querySelectorAll('.btn-action.view');
    viewButtons.forEach(button => {
        button.addEventListener('click', function() {
            const pipelineId = this.dataset.pipelineId;
            loadPipelineDetails(pipelineId);
        });
    });
    
    // Edit pipeline buttons
    const editButtons = document.querySelectorAll('.btn-action.edit');
    editButtons.forEach(button => {
        button.addEventListener('click', function() {
            const pipelineId = this.dataset.pipelineId;
            showEditPipelineModal(pipelineId);
        });
    });
    
    // Delete pipeline buttons
    const deleteButtons = document.querySelectorAll('.btn-action.delete');
    deleteButtons.forEach(button => {
        button.addEventListener('click', function() {
            const pipelineId = this.dataset.pipelineId;
            showDeletePipelineConfirmation(pipelineId);
        });
    });
}

/**
 * Filter pipelines by search term
 * @param {string} searchTerm - Search term
 */
function filterPipelines(searchTerm) {
    const rows = document.querySelectorAll('#pipeline-list tr');
    
    searchTerm = searchTerm.toLowerCase();
    
    rows.forEach(row => {
        const pipelineId = row.querySelector('td:first-child').textContent.toLowerCase();
        const pipelineName = row.querySelector('td:nth-child(2)').textContent.toLowerCase();
        
        if (pipelineId.includes(searchTerm) || pipelineName.includes(searchTerm)) {
            row.style.display = '';
        } else {
            row.style.display = 'none';
        }
    });
}

/**
 * Load details for a specific pipeline
 * @param {string} pipelineId - Pipeline ID
 */
async function loadPipelineDetails(pipelineId) {
    try {
        // Set selected pipeline
        pipelinesState.selectedPipeline = pipelineId;
        
        // Find pipeline details
        const pipeline = pipelinesState.pipelines.find(p => p.id === pipelineId);
        
        if (!pipeline) {
            throw new Error(`Pipeline ${pipelineId} not found`);
        }
        
        // Update pipeline detail header
        const titleElement = document.getElementById('selected-pipeline-title');
        const statusElement = titleElement.nextElementSibling;
        
        if (titleElement) {
            titleElement.textContent = `Pipeline ${pipelineId} - ${pipeline.name || pipelineId}`;
        }
        
        // Fetch devices for this pipeline
        const devices = await window.apiService.fetchPipelineDevices(pipelineId);
        
        // Store in state
        pipelinesState.devices[pipelineId] = devices;
        
        // Get latest status for each device
        const latestStatus = await window.apiService.fetchLatestStatus();
        
        // Combine device info with status
        const deviceData = devices.map(device => {
            const status = latestStatus.data.find(s => s.device_id === device.id);
            
            return {
                device_id: device.id,
                position: parseInt(device.id.slice(-2)),
                temperature: status ? parseFloat(status.temperature || 65) : 65,
                pressure: status ? parseFloat(status.pressure || 7.5) : 7.5,
                valve_status: status ? status.valve_status : 'closed',
                last_update: status ? status.timestamp : new Date().toISOString()
            };
        });
        
        // Store device data
        pipelinesState.pipelineDetails[pipelineId] = deviceData;
        
        // Determine overall status
        let status = 'healthy';
        
        deviceData.forEach(device => {
            const tempStatus = window.utils.getStatusFromValue(device.temperature, {
                warning: 85,
                critical: 95
            });
            
            const pressStatus = window.utils.getStatusFromValue(device.pressure, {
                warning: 8.5,
                critical: 9.5
            });
            
            if (tempStatus === 'critical' || pressStatus === 'critical') {
                status = 'critical';
            } else if ((tempStatus === 'warning' || pressStatus === 'warning') && status !== 'critical') {
                status = 'warning';
            }
        });
        
        // Update status badge
        if (statusElement) {
            statusElement.className = `status-badge ${status}`;
            statusElement.textContent = status.charAt(0).toUpperCase() + status.slice(1);
        }
        
        // Update pipeline visualization
        updatePipelineVisualization(pipelineId, deviceData);
        
        // Update pipeline table
        updatePipelineDevicesTable(pipelineId, deviceData);
        
    } catch (error) {
        console.error(`Error loading pipeline details for ${pipelineId}:`, error);
        window.utils.showNotification(`Failed to load details for pipeline ${pipelineId}. Please try again.`, 'error');
    }
}

/**
 * Update pipeline visualization with device data
 * @param {string} pipelineId - Pipeline ID
 * @param {Array} deviceData - Device data for the pipeline
 */
function updatePipelineVisualization(pipelineId, deviceData) {
    const visualizationContainer = document.querySelector('.pipeline-visualization');
    
    if (!visualizationContainer) {
        return;
    }
    
    // Clear current visualization
    visualizationContainer.innerHTML = '<div class="pipeline-line"></div>';
    
    // Sort devices by position
    deviceData.sort((a, b) => a.position - b.position);
    
    // Create bolts for each device
    deviceData.forEach((device, index) => {
        // Calculate position along pipeline (evenly spaced)
        const position = ((index + 1) / (deviceData.length + 1)) * 100;
        
        // Determine status based on temperature and pressure values
        const tempStatus = window.utils.getStatusFromValue(device.temperature, {
            warning: 85,
            critical: 95
        });
        
        const pressureStatus = window.utils.getStatusFromValue(device.pressure, {
            warning: 8.5,
            critical: 9.5
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
        tempValue.textContent = `${device.temperature}°C`;
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
        pressureValue.textContent = `${device.pressure} bar`;
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
        
        // Add bolt to pipeline
        visualizationContainer.appendChild(bolt);
    });
}

/**
 * Update pipeline devices table
 * @param {string} pipelineId - Pipeline ID
 * @param {Array} deviceData - Device data for the pipeline
 */
function updatePipelineDevicesTable(pipelineId, deviceData) {
    const tableBody = document.querySelector('.table-view table tbody');
    
    if (!tableBody) {
        return;
    }
    
    // Clear current rows
    tableBody.innerHTML = '';
    
    if (!deviceData || deviceData.length === 0) {
        const emptyRow = document.createElement('tr');
        emptyRow.innerHTML = `
            <td colspan="7" class="empty-table">
                <div class="empty-table-message">
                    <i class="fas fa-info-circle"></i>
                    <span>No devices found for this pipeline. Click "Add Bolt" to add one.</span>
                </div>
            </td>
        `;
        tableBody.appendChild(emptyRow);
        return;
    }
    
    // Sort devices by position
    deviceData.sort((a, b) => a.position - b.position);
    
    // Add rows for each device
    deviceData.forEach(device => {
        const row = document.createElement('tr');
        row.dataset.deviceId = device.device_id;
        
        // Determine status classes
        const tempStatus = window.utils.getStatusFromValue(device.temperature, {
            warning: 85,
            critical: 95
        });
        
        const pressureStatus = window.utils.getStatusFromValue(device.pressure, {
            warning: 8.5,
            critical: 9.5
        });
        
        const valveStatus = device.valve_status || 'closed';
        
        // Create row content
        row.innerHTML = `
            <td>${device.device_id}</td>
            <td>${device.position}</td>
            <td><span class="status-badge ${tempStatus}">${device.temperature}°C</span></td>
            <td><span class="status-badge ${pressureStatus}">${device.pressure} bar</span></td>
            <td><span class="status-badge ${valveStatus}">${valveStatus.charAt(0).toUpperCase() + valveStatus.slice(1)}</span></td>
            <td>${window.utils.formatDate(device.last_update, 'relative')}</td>
            <td>
                <div class="action-buttons">
                    <button class="btn-action toggle-valve" data-action="${valveStatus === 'open' ? 'close' : 'open'}" title="${valveStatus === 'open' ? 'Close' : 'Open'} Valve" data-device-id="${device.device_id}">
                        <i class="fas fa-door-${valveStatus === 'open' ? 'closed' : 'open'}"></i>
                    </button>
                    <button class="btn-action edit-bolt" title="Edit Bolt" data-device-id="${device.device_id}">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="btn-action remove-bolt" title="Remove Bolt" data-device-id="${device.device_id}">
                        <i class="fas fa-times"></i>
                    </button>
                </div>
            </td>
        `;
        
        tableBody.appendChild(row);
    });
    
    // Add event listeners to device action buttons
    addDeviceActionButtonListeners();
}

/**
 * Add event listeners to device action buttons
 */
function addDeviceActionButtonListeners() {
    // Toggle valve buttons
    const toggleValveButtons = document.querySelectorAll('.btn-action.toggle-valve');
    toggleValveButtons.forEach(button => {
        button.addEventListener('click', function() {
            const deviceId = this.dataset.deviceId;
            const action = this.dataset.action;
            
            toggleValve(deviceId, action);
        });
    });
    
    // Edit bolt buttons
    const editBoltButtons = document.querySelectorAll('.btn-action.edit-bolt');
    editBoltButtons.forEach(button => {
        button.addEventListener('click', function() {
            const deviceId = this.dataset.deviceId;
            
            // Show edit bolt modal (not implemented in this version)
            window.utils.showNotification('Edit bolt functionality is not implemented in this version', 'info');
        });
    });
    
    // Remove bolt buttons
    const removeBoltButtons = document.querySelectorAll('.btn-action.remove-bolt');
    removeBoltButtons.forEach(button => {
        button.addEventListener('click', function() {
            const deviceId = this.dataset.deviceId;
            
            showRemoveBoltConfirmation(deviceId);
        });
    });
}

/**
 * Toggle valve state
 * @param {string} deviceId - Device ID
 * @param {string} action - Action ('open' or 'close')
 */
async function toggleValve(deviceId, action) {
    try {
        // Send command to API
        await window.apiService.controlValve(deviceId, action);
        
        // Show success notification
        window.utils.showNotification(`Valve ${action}ed successfully`, 'success');
        
        // Reload pipeline details after a short delay
        setTimeout(() => {
            loadPipelineDetails(pipelinesState.selectedPipeline);
        }, 1000);
    } catch (error) {
        console.error(`Error ${action}ing valve for device ${deviceId}:`, error);
        window.utils.showNotification(`Failed to ${action} valve. Please try again.`, 'error');
    }
}

/**
 * Show add pipeline modal
 */
function showAddPipelineModal() {
    const modal = document.getElementById('add-pipeline-modal');
    
    if (modal) {
        // Reset form
        const form = document.getElementById('add-pipeline-form');
        if (form) {
            form.reset();
        }
        
        // Show modal
        modal.classList.add('show');
    }
}

/**
 * Show edit pipeline modal
 * @param {string} pipelineId - Pipeline ID
 */
function showEditPipelineModal(pipelineId) {
    const modal = document.getElementById('edit-pipeline-modal');
    
    if (modal) {
        // Find pipeline details
        const pipeline = pipelinesState.pipelines.find(p => p.id === pipelineId);
        
        if (!pipeline) {
            window.utils.showNotification(`Pipeline ${pipelineId} not found`, 'error');
            return;
        }
        
        // Fill form with pipeline data
        document.getElementById('edit-pipeline-id').value = pipeline.id;
        document.getElementById('edit-pipeline-name').value = pipeline.name || '';
        document.getElementById('edit-pipeline-description').value = pipeline.description || '';
        
        // Show modal
        modal.classList.add('show');
    }
}

/**
 * Show delete pipeline confirmation
 * @param {string} pipelineId - Pipeline ID
 */
function showDeletePipelineConfirmation(pipelineId) {
    const modal = document.getElementById('confirmation-modal');
    
    if (modal) {
        // Find pipeline details
        const pipeline = pipelinesState.pipelines.find(p => p.id === pipelineId);
        
        if (!pipeline) {
            window.utils.showNotification(`Pipeline ${pipelineId} not found`, 'error');
            return;
        }
        
        // Update confirmation message
        const messageElement = modal.querySelector('.confirmation-message');
        if (messageElement) {
            messageElement.innerHTML = `Are you sure you want to delete pipeline <strong>${pipelineId}</strong>?<br>This action cannot be undone.`;
        }
        
        // Set confirmation action
        const confirmButton = document.getElementById('confirm-action');
        if (confirmButton) {
            confirmButton.onclick = function() {
                deletePipeline(pipelineId);
                modal.classList.remove('show');
            };
        }
        
        // Show modal
        modal.classList.add('show');
    }
}

/**
 * Show remove bolt confirmation
 * @param {string} deviceId - Device ID
 */
function showRemoveBoltConfirmation(deviceId) {
    const modal = document.getElementById('confirmation-modal');
    
    if (modal) {
        // Update confirmation message
        const messageElement = modal.querySelector('.confirmation-message');
        if (messageElement) {
            messageElement.innerHTML = `Are you sure you want to remove bolt <strong>${deviceId}</strong>?<br>This action cannot be undone.`;
        }
        
        // Set confirmation action
        const confirmButton = document.getElementById('confirm-action');
        if (confirmButton) {
            confirmButton.onclick = function() {
                removeBolt(deviceId);
                modal.classList.remove('show');
            };
        }
        
        // Show modal
        modal.classList.add('show');
    }
}

/**
 * Show add bolt modal
 * @param {string} pipelineId - Pipeline ID
 */
function showAddBoltModal(pipelineId) {
    const modal = document.getElementById('add-bolt-modal');
    
    if (modal) {
        // Reset form
        const form = document.getElementById('add-bolt-form');
        if (form) {
            form.reset();
        }
        
        // Set pipeline ID
        document.getElementById('bolt-pipeline-id').value = pipelineId;
        
        // Determine next position and device ID
        const devices = pipelinesState.pipelineDetails[pipelineId] || [];
        let nextPosition = 1;
        
        if (devices.length > 0) {
            // Find highest position
            const maxPosition = Math.max(...devices.map(d => d.position));
            nextPosition = maxPosition + 1;
        }
        
        // Set next position
        document.getElementById('bolt-position').value = nextPosition;
        
        // Generate suggested device ID (e.g., dev050)
        const suggestedId = `dev${String(nextPosition * 10).padStart(3, '0')}`;
        document.getElementById('bolt-id').value = suggestedId;
        
        // Show modal
        modal.classList.add('show');
    }
}

/**
 * Add a new pipeline
 * @param {string} pipelineId - Pipeline ID
 * @param {string} pipelineName - Pipeline name
 * @param {string} description - Pipeline description
 */
async function addPipeline(pipelineId, pipelineName, description) {
    try {
        // Create pipeline data
        const pipelineData = {
            id: pipelineId,
            name: pipelineName,
            description: description,
            devices: []
        };
        
        // Send to API
        const response = await window.apiService.post('catalog', '/sectors', pipelineData);
        
        if (response && response.status === 'success') {
            // Show success notification
            window.utils.showNotification(`Pipeline ${pipelineId} created successfully`, 'success');
            
            // Reload pipelines data
            loadPipelinesData();
        } else {
            throw new Error('Failed to create pipeline');
        }
    } catch (error) {
        console.error('Error creating pipeline:', error);
        window.utils.showNotification('Failed to create pipeline. Please try again.', 'error');
    }
}

/**
 * Update an existing pipeline
 * @param {string} pipelineId - Pipeline ID
 * @param {string} pipelineName - Pipeline name
 * @param {string} description - Pipeline description
 */
async function updatePipeline(pipelineId, pipelineName, description) {
    try {
        // Create pipeline data
        const pipelineData = {
            id: pipelineId,
            name: pipelineName,
            description: description
        };
        
        // Send to API
        const response = await window.apiService.put('catalog', `/sectors/${pipelineId}`, pipelineData);
        
        if (response && response.status === 'success') {
            // Show success notification
            window.utils.showNotification(`Pipeline ${pipelineId} updated successfully`, 'success');
            
            // Reload pipelines data
            loadPipelinesData();
        } else {
            throw new Error('Failed to update pipeline');
        }
    } catch (error) {
        console.error('Error updating pipeline:', error);
        window.utils.showNotification('Failed to update pipeline. Please try again.', 'error');
    }
}

/**
 * Delete a pipeline
 * @param {string} pipelineId - Pipeline ID
 */
async function deletePipeline(pipelineId) {
    try {
        // Send to API
        const response = await window.apiService.delete('catalog', `/sectors/${pipelineId}`);
        
        if (response && response.status === 'success') {
            // Show success notification
            window.utils.showNotification(`Pipeline ${pipelineId} deleted successfully`, 'success');
            
            // Clear selected pipeline if it was the deleted one
            if (pipelinesState.selectedPipeline === pipelineId) {
                pipelinesState.selectedPipeline = null;
            }
            
            // Reload pipelines data
            loadPipelinesData();
        } else {
            throw new Error('Failed to delete pipeline');
        }
    } catch (error) {
        console.error('Error deleting pipeline:', error);
        window.utils.showNotification('Failed to delete pipeline. Please try again.', 'error');
    }
}

/**
 * Add a new bolt to a pipeline
 * @param {string} pipelineId - Pipeline ID
 * @param {string} boltId - Bolt ID
 * @param {number} position - Bolt position
 * @param {string} description - Bolt description
 */
async function addBolt(pipelineId, boltId, position, description) {
    try {
        // Create bolt data
        const boltData = {
            id: boltId,
            position: parseInt(position),
            description: description,
            pipeline_id: pipelineId
        };
        
        // Send to API
        const response = await window.apiService.post('catalog', `/sectors/${pipelineId}/devices`, boltData);
        
        if (response && response.status === 'success') {
            // Show success notification
            window.utils.showNotification(`Bolt ${boltId} added successfully`, 'success');
            
            // Reload pipeline details
            loadPipelineDetails(pipelineId);
        } else {
            throw new Error('Failed to add bolt');
        }
    } catch (error) {
        console.error('Error adding bolt:', error);
        window.utils.showNotification('Failed to add bolt. Please try again.', 'error');
    }
}

/**
 * Remove a bolt from a pipeline
 * @param {string} deviceId - Device ID
 */
async function removeBolt(deviceId) {
    try {
        const pipelineId = pipelinesState.selectedPipeline;
        
        if (!pipelineId) {
            throw new Error('No pipeline selected');
        }
        
        // Send to API
        const response = await window.apiService.delete('catalog', `/sectors/${pipelineId}/devices/${deviceId}`);
        
        if (response && response.status === 'success') {
            // Show success notification
            window.utils.showNotification(`Bolt ${deviceId} removed successfully`, 'success');
            
            // Reload pipeline details
            loadPipelineDetails(pipelineId);
        } else {
            throw new Error('Failed to remove bolt');
        }
    } catch (error) {
        console.error('Error removing bolt:', error);
        window.utils.showNotification('Failed to remove bolt. Please try again.', 'error');
    }
}

/**
 * Save pipeline changes
 * @param {string} pipelineId - Pipeline ID
 */
function savePipelineChanges(pipelineId) {
    // In this version, changes are applied immediately
    // This function would be used for batch changes in a more complex implementation
    window.utils.showNotification('Changes saved successfully', 'success');
}

// Export pipelines functions
window.pipelines = {
    initPipelines,
    loadPipelinesData,
    refreshPipelinesData
};
/**
 * Show or hide pipelines loading indicators
 * @param {boolean} show - Whether to show or hide loading indicators
 */
function showPipelinesLoading(show) {
    // Find loading indicators
    const loadingIndicators = document.querySelectorAll('.pipeline-loading');
    
    // Update loading indicators
    loadingIndicators.forEach(indicator => {
        if (show) {
            indicator.classList.add('show');
        } else {
            indicator.classList.remove('show');
        }
    });
    
    // Show/hide loading overlay for the table
    const tableContainer = document.querySelector('.table-responsive');
    if (tableContainer) {
        if (show) {
            // Create loading overlay if it doesn't exist
            let loadingOverlay = tableContainer.querySelector('.loading-overlay');
            if (!loadingOverlay) {
                loadingOverlay = document.createElement('div');
                loadingOverlay.className = 'loading-overlay';
                loadingOverlay.innerHTML = `
                    <div class="spinner">
                        <i class="fas fa-spinner fa-spin"></i>
                    </div>
                `;
                tableContainer.appendChild(loadingOverlay);
            }
            loadingOverlay.style.display = 'flex';
        } else {
            // Hide loading overlay
            const loadingOverlay = tableContainer.querySelector('.loading-overlay');
            if (loadingOverlay) {
                loadingOverlay.style.display = 'none';
            }
        }
    }
}