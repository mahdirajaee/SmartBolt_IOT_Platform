/**
 * Settings Module for Smart IoT Bolt Dashboard
 * Handles user settings, system configuration, and preferences
 */

// Settings state
let settingsState = {
    activeSection: 'account-settings',
    themePreference: 'light',
    thresholds: {
        temperature: {
            warning: 85,
            critical: 95
        },
        pressure: {
            warning: 8.5,
            critical: 9.5
        }
    },
    connectionStatus: {
        mqtt: 'unknown',
        catalog: 'unknown',
        timeseries: 'unknown',
        analytics: 'unknown'
    },
    userProfile: {}
};

/**
 * Initialize the settings page
 */
function initSettings() {
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
        // Load settings data
        loadSettingsData();
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
    
    // Settings navigation
    initSettingsNavigation();
    
    // Password toggle buttons
    initPasswordToggles();
    
    // Theme toggle
    initThemeToggle();
    
    // Password strength meter
    initPasswordStrengthMeter();
    
    // Do not disturb toggle
    initDoNotDisturbToggle();
    
    // Threshold sliders
    initThresholdSliders();
    
    // Pipeline-specific thresholds toggle
    initPipelineThresholdsToggle();
    
    // Connection test button
    initConnectionTestButton();
    
    // Form submissions
    initFormSubmissions();
    
    // User management buttons
    initUserManagementButtons();
}

/**
 * Initialize settings navigation
 */
function initSettingsNavigation() {
    const navItems = document.querySelectorAll('.settings-nav-item');
    
    navItems.forEach(item => {
        item.addEventListener('click', function() {
            // Get target section
            const targetSection = this.dataset.target;
            
            // Update active nav item
            navItems.forEach(navItem => navItem.classList.remove('active'));
            this.classList.add('active');
            
            // Update active section
            const sections = document.querySelectorAll('.settings-section');
            sections.forEach(section => {
                section.classList.remove('active');
                
                if (section.id === targetSection) {
                    section.classList.add('active');
                }
            });
            
            // Update state
            settingsState.activeSection = targetSection;
        });
    });
}

/**
 * Initialize password toggle buttons
 */
function initPasswordToggles() {
    const toggleButtons = document.querySelectorAll('.toggle-password');
    
    toggleButtons.forEach(button => {
        button.addEventListener('click', function() {
            const passwordField = this.previousElementSibling;
            
            // Toggle password visibility
            if (passwordField.type === 'password') {
                passwordField.type = 'text';
                this.classList.remove('fa-eye-slash');
                this.classList.add('fa-eye');
            } else {
                passwordField.type = 'password';
                this.classList.remove('fa-eye');
                this.classList.add('fa-eye-slash');
            }
        });
    });
}

/**
 * Initialize theme toggle
 */
function initThemeToggle() {
    const themeToggle = document.getElementById('theme-toggle-setting');
    
    if (themeToggle) {
        // Set initial state based on current theme
        const currentTheme = document.documentElement.getAttribute('data-theme');
        themeToggle.checked = currentTheme === 'dark';
        
        // Add change listener
        themeToggle.addEventListener('change', function() {
            const theme = this.checked ? 'dark' : 'light';
            window.utils.setTheme(theme);
            settingsState.themePreference = theme;
        });
    }
    
    // System theme toggle
    const systemThemeToggle = document.getElementById('system-theme');
    
    if (systemThemeToggle) {
        systemThemeToggle.addEventListener('change', function() {
            if (this.checked) {
                // Use system theme
                const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
                window.utils.setTheme(prefersDark ? 'dark' : 'light');
                
                // Disable manual toggle
                if (themeToggle) {
                    themeToggle.disabled = true;
                }
            } else {
                // Re-enable manual toggle
                if (themeToggle) {
                    themeToggle.disabled = false;
                    
                    // Use manual theme
                    window.utils.setTheme(themeToggle.checked ? 'dark' : 'light');
                }
            }
        });
    }
}

/**
 * Initialize password strength meter
 */
function initPasswordStrengthMeter() {
    const passwordField = document.getElementById('new-password');
    const strengthBar = document.querySelector('.strength-level');
    const strengthText = document.querySelector('.strength-text');
    
    if (passwordField && strengthBar && strengthText) {
        passwordField.addEventListener('input', function() {
            const password = this.value;
            const strength = calculatePasswordStrength(password);
            
            // Update strength bar
            strengthBar.style.width = `${strength.percentage}%`;
            
            // Update strength class
            strengthBar.classList.remove('weak', 'medium', 'strong');
            strengthBar.classList.add(strength.level);
            
            // Update strength text
            strengthText.textContent = `Password strength: ${strength.level}`;
            
            // Set text color
            strengthText.classList.remove('text-danger', 'text-warning', 'text-success');
            
            if (strength.level === 'weak') {
                strengthText.classList.add('text-danger');
            } else if (strength.level === 'medium') {
                strengthText.classList.add('text-warning');
            } else {
                strengthText.classList.add('text-success');
            }
        });
    }
}

/**
 * Calculate password strength
 * @param {string} password - Password to evaluate
 * @returns {Object} - Strength object with level and percentage
 */
function calculatePasswordStrength(password) {
    if (!password) {
        return { level: 'weak', percentage: 0 };
    }
    
    let score = 0;
    
    // Length check
    if (password.length >= 8) score += 1;
    if (password.length >= 12) score += 1;
    
    // Complexity checks
    if (/[a-z]/.test(password)) score += 1;  // lowercase
    if (/[A-Z]/.test(password)) score += 1;  // uppercase
    if (/[0-9]/.test(password)) score += 1;  // numbers
    if (/[^a-zA-Z0-9]/.test(password)) score += 1;  // special characters
    
    // Determine level
    let level, percentage;
    
    if (score <= 2) {
        level = 'weak';
        percentage = 25;
    } else if (score <= 4) {
        level = 'medium';
        percentage = 50;
    } else {
        level = 'strong';
        percentage = 100;
    }
    
    return { level, percentage };
}

/**
 * Initialize Do Not Disturb toggle
 */
function initDoNotDisturbToggle() {
    const dndToggle = document.getElementById('do-not-disturb');
    const dndSchedule = document.querySelector('.dnd-schedule');
    
    if (dndToggle && dndSchedule) {
        dndToggle.addEventListener('change', function() {
            if (this.checked) {
                dndSchedule.style.display = 'block';
            } else {
                dndSchedule.style.display = 'none';
            }
        });
    }
}

/**
 * Initialize threshold sliders
 */
function initThresholdSliders() {
    // Temperature warning threshold
    const tempWarningSlider = document.getElementById('temp-warning-threshold');
    const tempWarningValue = document.getElementById('temp-warning-value');
    
    if (tempWarningSlider && tempWarningValue) {
        // Set initial value from state
        tempWarningSlider.value = settingsState.thresholds.temperature.warning;
        tempWarningValue.textContent = settingsState.thresholds.temperature.warning;
        
        // Add input listener
        tempWarningSlider.addEventListener('input', function() {
            tempWarningValue.textContent = this.value;
            
            // Ensure warning is less than critical
            const criticalSlider = document.getElementById('temp-critical-threshold');
            if (criticalSlider && parseInt(this.value) >= parseInt(criticalSlider.value)) {
                criticalSlider.value = parseInt(this.value) + 5;
                document.getElementById('temp-critical-value').textContent = criticalSlider.value;
            }
        });
    }
    
    // Temperature critical threshold
    const tempCriticalSlider = document.getElementById('temp-critical-threshold');
    const tempCriticalValue = document.getElementById('temp-critical-value');
    
    if (tempCriticalSlider && tempCriticalValue) {
        // Set initial value from state
        tempCriticalSlider.value = settingsState.thresholds.temperature.critical;
        tempCriticalValue.textContent = settingsState.thresholds.temperature.critical;
        
        // Add input listener
        tempCriticalSlider.addEventListener('input', function() {
            tempCriticalValue.textContent = this.value;
            
            // Ensure critical is greater than warning
            const warningSlider = document.getElementById('temp-warning-threshold');
            if (warningSlider && parseInt(this.value) <= parseInt(warningSlider.value)) {
                warningSlider.value = parseInt(this.value) - 5;
                document.getElementById('temp-warning-value').textContent = warningSlider.value;
            }
        });
    }
    
    // Pressure warning threshold
    const pressureWarningSlider = document.getElementById('pressure-warning-threshold');
    const pressureWarningValue = document.getElementById('pressure-warning-value');
    
    if (pressureWarningSlider && pressureWarningValue) {
        // Set initial value from state
        pressureWarningSlider.value = settingsState.thresholds.pressure.warning;
        pressureWarningValue.textContent = settingsState.thresholds.pressure.warning;
        
        // Add input listener
        pressureWarningSlider.addEventListener('input', function() {
            pressureWarningValue.textContent = this.value;
            
            // Ensure warning is less than critical
            const criticalSlider = document.getElementById('pressure-critical-threshold');
            if (criticalSlider && parseFloat(this.value) >= parseFloat(criticalSlider.value)) {
                criticalSlider.value = parseFloat(this.value) + 0.5;
                document.getElementById('pressure-critical-value').textContent = criticalSlider.value;
            }
        });
    }
    
    // Pressure critical threshold
    const pressureCriticalSlider = document.getElementById('pressure-critical-threshold');
    const pressureCriticalValue = document.getElementById('pressure-critical-value');
    
    if (pressureCriticalSlider && pressureCriticalValue) {
        // Set initial value from state
        pressureCriticalSlider.value = settingsState.thresholds.pressure.critical;
        pressureCriticalValue.textContent = settingsState.thresholds.pressure.critical;
        
        // Add input listener
        pressureCriticalSlider.addEventListener('input', function() {
            pressureCriticalValue.textContent = this.value;
            
            // Ensure critical is greater than warning
            const warningSlider = document.getElementById('pressure-warning-threshold');
            if (warningSlider && parseFloat(this.value) <= parseFloat(warningSlider.value)) {
                warningSlider.value = parseFloat(this.value) - 0.5;
                document.getElementById('pressure-warning-value').textContent = warningSlider.value;
            }
        });
    }
}

/**
 * Initialize pipeline-specific thresholds toggle
 */
function initPipelineThresholdsToggle() {
    const pipelineThresholdsToggle = document.getElementById('pipeline-specific-thresholds');
    const pipelineThresholdsContainer = document.querySelector('.pipeline-thresholds-container');
    
    if (pipelineThresholdsToggle && pipelineThresholdsContainer) {
        pipelineThresholdsToggle.addEventListener('change', function() {
            if (this.checked) {
                pipelineThresholdsContainer.style.display = 'block';
                
                // Load pipelines for the selector
                loadPipelinesForThresholds();
            } else {
                pipelineThresholdsContainer.style.display = 'none';
            }
        });
    }
    
    // Pipeline selector
    const pipelineSelect = document.getElementById('pipeline-select');
    
    if (pipelineSelect) {
        pipelineSelect.addEventListener('change', function() {
            const pipelineId = this.value;
            
            if (pipelineId) {
                // Load pipeline-specific thresholds
                loadPipelineThresholds(pipelineId);
            } else {
                // Clear pipeline thresholds
                const pipelineThresholds = document.querySelector('.pipeline-thresholds');
                
                if (pipelineThresholds) {
                    pipelineThresholds.innerHTML = `
                        <div class="threshold-placeholder">
                            <i class="fas fa-info-circle"></i>
                            <span>Select a pipeline to configure specific thresholds</span>
                        </div>
                    `;
                }
            }
        });
    }
}

/**
 * Initialize connection test button
 */
function initConnectionTestButton() {
    const testButton = document.querySelector('.test-connection-btn');
    
    if (testButton) {
        testButton.addEventListener('click', function() {
            testConnections();
        });
    }
}

/**
 * Initialize form submissions
 */
function initFormSubmissions() {
    // Account settings form
    const accountForm = document.querySelector('#account-settings form');
    
    if (accountForm) {
        accountForm.addEventListener('submit', function(e) {
            e.preventDefault();
            saveAccountSettings();
        });
    }
    
    // Notification settings form
    const notificationSaveBtn = document.querySelector('.notification-save-btn');
    
    if (notificationSaveBtn) {
        notificationSaveBtn.addEventListener('click', function() {
            saveNotificationSettings();
        });
    }
    
    // Thresholds settings form
    const thresholdSaveBtn = document.querySelector('.threshold-save-btn');
    
    if (thresholdSaveBtn) {
        thresholdSaveBtn.addEventListener('click', function() {
            saveThresholdSettings();
        });
    }
    
    // Display settings form
    const displaySaveBtn = document.querySelector('.display-save-btn');
    
    if (displaySaveBtn) {
        displaySaveBtn.addEventListener('click', function() {
            saveDisplaySettings();
        });
    }
    
    // Connection settings form
    const connectionSaveBtn = document.querySelector('.connection-save-btn');
    
    if (connectionSaveBtn) {
        connectionSaveBtn.addEventListener('click', function() {
            saveConnectionSettings();
        });
    }
    
    // System settings form
    const systemSaveBtn = document.querySelector('.system-save-btn');
    
    if (systemSaveBtn) {
        systemSaveBtn.addEventListener('click', function() {
            saveSystemSettings();
        });
    }
}

/**
 * Initialize user management buttons
 */
function initUserManagementButtons() {
    // Add user button
    const addUserBtn = document.querySelector('.add-user-btn');
    
    if (addUserBtn) {
        addUserBtn.addEventListener('click', function() {
            showAddUserModal();
        });
    }
    
    // Save user button
    const saveUserBtn = document.getElementById('save-user-btn');
    
    if (saveUserBtn) {
        saveUserBtn.addEventListener('click', function() {
            saveNewUser();
        });
    }
    
    // Edit user buttons
    initActionButtons('.edit-user', editUser);
    
    // Reset password buttons
    initActionButtons('.reset-password', resetUserPassword);
    
    // Deactivate user buttons
    initActionButtons('.deactivate-user', deactivateUser);
    
    // Activate user buttons
    initActionButtons('.activate-user', activateUser);
}

/**
 * Initialize action buttons with handler
 * @param {string} selector - Button selector
 * @param {Function} handler - Click handler function
 */
function initActionButtons(selector, handler) {
    const buttons = document.querySelectorAll(selector);
    
    buttons.forEach(button => {
        button.addEventListener('click', function() {
            // Get user identifier from parent row
            const row = this.closest('tr');
            const email = row.cells[1].textContent;
            
            // Call handler with email
            handler(email);
        });
    });
}

/**
 * Load settings data from the server
 */
async function loadSettingsData() {
    try {
        // Load user profile
        const user = window.authService.getCurrentUser();
        
        if (user) {
            settingsState.userProfile = user;
            
            // Update form fields
            populateUserProfile(user);
        }
        
        // Load thresholds
        // In a real implementation, this would come from an API call
        // For now, use default values from state
        
        // Load connection status
        await testConnections();
        
    } catch (error) {
        console.error('Error loading settings data:', error);
        window.utils.showNotification('Failed to load settings data. Please try again.', 'error');
    }
}

/**
 * Populate user profile form fields
 * @param {Object} user - User profile data
 */
function populateUserProfile(user) {
    // Basic user info
    const firstNameInput = document.getElementById('first-name');
    const lastNameInput = document.getElementById('last-name');
    const emailInput = document.getElementById('email');
    const phoneInput = document.getElementById('phone');
    
    if (firstNameInput) firstNameInput.value = user.firstName || '';
    if (lastNameInput) lastNameInput.value = user.lastName || '';
    if (emailInput) emailInput.value = user.email || '';
    if (phoneInput) phoneInput.value = user.phone || '';
    
    // Display name in the UI
    const userNameElements = document.querySelectorAll('.user-name');
    
    userNameElements.forEach(element => {
        if (user.firstName && user.lastName) {
            element.textContent = `${user.firstName} ${user.lastName}`;
        } else {
            element.textContent = user.email;
        }
    });
}

/**
 * Load pipelines for thresholds configuration
 */
async function loadPipelinesForThresholds() {
    try {
        // Get pipeline select element
        const pipelineSelect = document.getElementById('pipeline-select');
        
        if (!pipelineSelect) return;
        
        // Fetch pipelines
        const pipelines = await window.apiService.fetchPipelines();
        
        // Clear options (except first)
        while (pipelineSelect.options.length > 1) {
            pipelineSelect.remove(1);
        }
        
        // Add pipeline options
        pipelines.forEach(pipeline => {
            const option = document.createElement('option');
            option.value = pipeline.id;
            option.textContent = pipeline.name || `Pipeline ${pipeline.id}`;
            pipelineSelect.appendChild(option);
        });
        
    } catch (error) {
        console.error('Error loading pipelines for thresholds:', error);
        window.utils.showNotification('Failed to load pipelines. Please try again.', 'error');
    }
}

/**
 * Load pipeline-specific thresholds
 * @param {string} pipelineId - Pipeline ID
 */
function loadPipelineThresholds(pipelineId) {
    // In a real implementation, this would fetch pipeline-specific thresholds from an API
    // For now, display a form with default values
    
    const pipelineThresholds = document.querySelector('.pipeline-thresholds');
    
    if (!pipelineThresholds) return;
    
    // Create pipeline thresholds form
    pipelineThresholds.innerHTML = `
        <div class="threshold-setting">
            <div class="threshold-info">
                <div class="threshold-title">Temperature Warning Threshold</div>
                <div class="threshold-description">Temperature level for warning alerts</div>
            </div>
            <div class="threshold-control">
                <div class="threshold-slider-container">
                    <input type="range" min="50" max="100" value="85" class="threshold-slider" id="pipeline-temp-warning">
                    <div class="threshold-value">
                        <span id="pipeline-temp-warning-value">85</span>°C
                    </div>
                </div>
            </div>
        </div>
        
        <div class="threshold-setting">
            <div class="threshold-info">
                <div class="threshold-title">Temperature Critical Threshold</div>
                <div class="threshold-description">Temperature level for critical alerts</div>
            </div>
            <div class="threshold-control">
                <div class="threshold-slider-container">
                    <input type="range" min="50" max="100" value="95" class="threshold-slider" id="pipeline-temp-critical">
                    <div class="threshold-value">
                        <span id="pipeline-temp-critical-value">95</span>°C
                    </div>
                </div>
            </div>
        </div>
        
        <div class="threshold-setting">
            <div class="threshold-info">
                <div class="threshold-title">Pressure Warning Threshold</div>
                <div class="threshold-description">Pressure level for warning alerts</div>
            </div>
            <div class="threshold-control">
                <div class="threshold-slider-container">
                    <input type="range" min="5" max="12" step="0.1" value="8.5" class="threshold-slider" id="pipeline-pressure-warning">
                    <div class="threshold-value">
                        <span id="pipeline-pressure-warning-value">8.5</span> bar
                    </div>
                </div>
            </div>
        </div>
        
        <div class="threshold-setting">
            <div class="threshold-info">
                <div class="threshold-title">Pressure Critical Threshold</div>
                <div class="threshold-description">Pressure level for critical alerts</div>
            </div>
            <div class="threshold-control">
                <div class="threshold-slider-container">
                    <input type="range" min="5" max="12" step="0.1" value="9.5" class="threshold-slider" id="pipeline-pressure-critical">
                    <div class="threshold-value">
                        <span id="pipeline-pressure-critical-value">9.5</span> bar
                    </div>
                </div>
            </div>
        </div>
    `;
    
    // Initialize pipeline threshold sliders
    initPipelineThresholdSliders();
}

/**
 * Initialize pipeline threshold sliders
 */
function initPipelineThresholdSliders() {
    // Temperature warning threshold
    const tempWarningSlider = document.getElementById('pipeline-temp-warning');
    const tempWarningValue = document.getElementById('pipeline-temp-warning-value');
    
    if (tempWarningSlider && tempWarningValue) {
        tempWarningSlider.addEventListener('input', function() {
            tempWarningValue.textContent = this.value;
            
            // Ensure warning is less than critical
            const criticalSlider = document.getElementById('pipeline-temp-critical');
            if (criticalSlider && parseInt(this.value) >= parseInt(criticalSlider.value)) {
                criticalSlider.value = parseInt(this.value) + 5;
                document.getElementById('pipeline-temp-critical-value').textContent = criticalSlider.value;
            }
        });
    }
    
    // Temperature critical threshold
    const tempCriticalSlider = document.getElementById('pipeline-temp-critical');
    const tempCriticalValue = document.getElementById('pipeline-temp-critical-value');
    
    if (tempCriticalSlider && tempCriticalValue) {
        tempCriticalSlider.addEventListener('input', function() {
            tempCriticalValue.textContent = this.value;
            
            // Ensure critical is greater than warning
            const warningSlider = document.getElementById('pipeline-temp-warning');
            if (warningSlider && parseInt(this.value) <= parseInt(warningSlider.value)) {
                warningSlider.value = parseInt(this.value) - 5;
                document.getElementById('pipeline-temp-warning-value').textContent = warningSlider.value;
            }
        });
    }
    
    // Pressure warning threshold
    const pressureWarningSlider = document.getElementById('pipeline-pressure-warning');
    const pressureWarningValue = document.getElementById('pipeline-pressure-warning-value');
    
    if (pressureWarningSlider && pressureWarningValue) {
        pressureWarningSlider.addEventListener('input', function() {
            pressureWarningValue.textContent = this.value;
            
            // Ensure warning is less than critical
            const criticalSlider = document.getElementById('pipeline-pressure-critical');
            if (criticalSlider && parseFloat(this.value) >= parseFloat(criticalSlider.value)) {
                criticalSlider.value = parseFloat(this.value) + 0.5;
                document.getElementById('pipeline-pressure-critical-value').textContent = criticalSlider.value;
            }
        });
    }
    
    // Pressure critical threshold
    const pressureCriticalSlider = document.getElementById('pipeline-pressure-critical');
    const pressureCriticalValue = document.getElementById('pipeline-pressure-critical-value');
    
    if (pressureCriticalSlider && pressureCriticalValue) {
        pressureCriticalSlider.addEventListener('input', function() {
            pressureCriticalValue.textContent = this.value;
            
            // Ensure critical is greater than warning
            const warningSlider = document.getElementById('pipeline-pressure-warning');
            if (warningSlider && parseFloat(this.value) <= parseFloat(warningSlider.value)) {
                warningSlider.value = parseFloat(this.value) - 0.5;
                document.getElementById('pipeline-pressure-warning-value').textContent = warningSlider.value;
            }
        });
    }
}

/**
 * Test service connections
 */
async function testConnections() {
    // Get status elements
    const mqttStatus = document.getElementById('mqtt-status');
    const catalogStatus = document.getElementById('catalog-status');
    const timeseriesStatus = document.getElementById('timeseries-status');
    const analyticsStatus = document.getElementById('analytics-status');
    
    // Set loading state
    const statusElements = [mqttStatus, catalogStatus, timeseriesStatus, analyticsStatus];
    
    statusElements.forEach(element => {
        if (element) {
            element.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> Testing...';
        }
    });
    
    try {
        // In a real implementation, these would be actual API calls to test connections
        // For demonstration, simulate connection tests with delays
        
        // Test MQTT connection
        await simulateConnectionTest();
        
        if (mqttStatus) {
            const mqttConnected = Math.random() > 0.2; // 80% chance of success
            
            if (mqttConnected) {
                mqttStatus.innerHTML = '<i class="fas fa-check-circle text-success"></i> Connected';
                settingsState.connectionStatus.mqtt = 'connected';
            } else {
                mqttStatus.innerHTML = '<i class="fas fa-times-circle text-danger"></i> Failed';
                settingsState.connectionStatus.mqtt = 'failed';
            }
        }
        
        // Test Catalog connection
        await simulateConnectionTest();
        
        if (catalogStatus) {
            const catalogConnected = Math.random() > 0.1; // 90% chance of success
            
            if (catalogConnected) {
                catalogStatus.innerHTML = '<i class="fas fa-check-circle text-success"></i> Connected';
                settingsState.connectionStatus.catalog = 'connected';
            } else {
                catalogStatus.innerHTML = '<i class="fas fa-times-circle text-danger"></i> Failed';
                settingsState.connectionStatus.catalog = 'failed';
            }
        }
        
        // Test Time Series DB connection
        await simulateConnectionTest();
        
        if (timeseriesStatus) {
            const timeseriesConnected = Math.random() > 0.15; // 85% chance of success
            
            if (timeseriesConnected) {
                timeseriesStatus.innerHTML = '<i class="fas fa-check-circle text-success"></i> Connected';
                settingsState.connectionStatus.timeseries = 'connected';
            } else {
                timeseriesStatus.innerHTML = '<i class="fas fa-times-circle text-danger"></i> Failed';
                settingsState.connectionStatus.timeseries = 'failed';
            }
        }
        
        // Test Analytics connection
        await simulateConnectionTest();
        
        if (analyticsStatus) {
            const analyticsConnected = Math.random() > 0.15; // 85% chance of success
            
            if (analyticsConnected) {
                analyticsStatus.innerHTML = '<i class="fas fa-check-circle text-success"></i> Connected';
                settingsState.connectionStatus.analytics = 'connected';
            } else {
                analyticsStatus.innerHTML = '<i class="fas fa-times-circle text-danger"></i> Failed';
                settingsState.connectionStatus.analytics = 'failed';
            }
        }
        
    } catch (error) {
        console.error('Error testing connections:', error);
        
        // Set error state
        statusElements.forEach(element => {
            if (element) {
                element.innerHTML = '<i class="fas fa-times-circle text-danger"></i> Error';
            }
        });
    }
}

/**
 * Simulate a connection test
 * @returns {Promise} - Promise that resolves after a delay
 */
function simulateConnectionTest() {
    return new Promise(resolve => {
        setTimeout(resolve, 500 + Math.random() * 500); // 500-1000ms delay
    });
}

/**
 * Save account settings
 */
function saveAccountSettings() {
    try {
        // Get form values
        const firstName = document.getElementById('first-name').value;
        const lastName = document.getElementById('last-name').value;
        const email = document.getElementById('email').value;
        const phone = document.getElementById('phone').value;
        
        // Get password fields
        const currentPassword = document.getElementById('current-password').value;
        const newPassword = document.getElementById('new-password').value;
        const confirmPassword = document.getElementById('confirm-password').value;
        
        // Validate passwords if changing
        if (newPassword) {
            if (!currentPassword) {
                throw new Error('Current password is required');
            }
            
            if (newPassword !== confirmPassword) {
                throw new Error('New passwords do not match');
            }
            
            const strength = calculatePasswordStrength(newPassword);
            
            if (strength.level === 'weak') {
                throw new Error('Password is too weak. Please choose a stronger password.');
            }
        }
        
        // Update user profile in state
        settingsState.userProfile = {
            ...settingsState.userProfile,
            firstName,
            lastName,
            email,
            phone
        };
        
        // In a real implementation, this would call an API to update the user profile
        // and change the password if provided
        
        // Show success notification
        window.utils.showNotification('Account settings saved successfully', 'success');
        
        // Update user info in UI
        if (firstName && lastName) {
            const userNameElements = document.querySelectorAll('.user-name');
            
            userNameElements.forEach(element => {
                element.textContent = `${firstName} ${lastName}`;
            });
        }
        
        // Clear password fields
        document.getElementById('current-password').value = '';
        document.getElementById('new-password').value = '';
        document.getElementById('confirm-password').value = '';
        
        // Reset password strength meter
        const strengthBar = document.querySelector('.strength-level');
        const strengthText = document.querySelector('.strength-text');
        
        if (strengthBar) strengthBar.style.width = '0%';
        if (strengthText) strengthText.textContent = 'Password strength';
        
    } catch (error) {
        console.error('Error saving account settings:', error);
        window.utils.showNotification(error.message || 'Failed to save account settings. Please try again.', 'error');
    }
}

/**
 * Save notification settings
 */
function saveNotificationSettings() {
    try {
        // Get toggle states
        const criticalAlerts = document.getElementById('critical-alerts').checked;
        const warningAlerts = document.getElementById('warning-alerts').checked;
        const infoAlerts = document.getElementById('info-alerts').checked;
        
        const inAppNotifications = document.getElementById('in-app-notifications').checked;
        const emailNotifications = document.getElementById('email-notifications').checked;
        const telegramNotifications = document.getElementById('telegram-notifications').checked;
        const smsNotifications = document.getElementById('sms-notifications').checked;
        
        const doNotDisturb = document.getElementById('do-not-disturb').checked;
        const dndStart = document.getElementById('dnd-start').value;
        const dndEnd = document.getElementById('dnd-end').value;
        
        // In a real implementation, this would call an API to update notification settings
        
        // Show success notification
        window.utils.showNotification('Notification settings saved successfully', 'success');
        
    } catch (error) {
        console.error('Error saving notification settings:', error);
        window.utils.showNotification('Failed to save notification settings. Please try again.', 'error');
    }
}

/**
 * Save threshold settings
 */
function saveThresholdSettings() {
    try {
        // Get global threshold values
        const tempWarning = document.getElementById('temp-warning-threshold').value;
        const tempCritical = document.getElementById('temp-critical-threshold').value;
        const pressureWarning = document.getElementById('pressure-warning-threshold').value;
        const pressureCritical = document.getElementById('pressure-critical-threshold').value;
        
        // Get pipeline-specific settings
        const usePipelineSpecific = document.getElementById('pipeline-specific-thresholds').checked;
        
        // Validate thresholds
        if (parseInt(tempWarning) >= parseInt(tempCritical)) {
            throw new Error('Temperature warning threshold must be less than critical threshold');
        }
        
        if (parseFloat(pressureWarning) >= parseFloat(pressureCritical)) {
            throw new Error('Pressure warning threshold must be less than critical threshold');
        }
        
        // Update thresholds in state
        settingsState.thresholds = {
            temperature: {
                warning: parseInt(tempWarning),
                critical: parseInt(tempCritical)
            },
            pressure: {
                warning: parseFloat(pressureWarning),
                critical: parseFloat(pressureCritical)
            }
        };
        
        // In a real implementation, this would call an API to update threshold settings
        
        // If using pipeline-specific thresholds, also save those
        if (usePipelineSpecific) {
            const pipelineId = document.getElementById('pipeline-select').value;
            
            if (pipelineId) {
                // Get pipeline-specific thresholds
                const pipelineTempWarning = document.getElementById('pipeline-temp-warning').value;
                const pipelineTempCritical = document.getElementById('pipeline-temp-critical').value;
                const pipelinePressureWarning = document.getElementById('pipeline-pressure-warning').value;
                const pipelinePressureCritical = document.getElementById('pipeline-pressure-critical').value;
                
                // Validate pipeline thresholds
                if (parseInt(pipelineTempWarning) >= parseInt(pipelineTempCritical)) {
                    throw new Error('Pipeline temperature warning threshold must be less than critical threshold');
                }
                
                if (parseFloat(pipelinePressureWarning) >= parseFloat(pipelinePressureCritical)) {
                    throw new Error('Pipeline pressure warning threshold must be less than critical threshold');
                }
                
                // In a real implementation, this would call an API to update pipeline-specific threshold settings
            }
        }
        
        // Show success notification
        window.utils.showNotification('Threshold settings saved successfully', 'success');
        
    } catch (error) {
        console.error('Error saving threshold settings:', error);
        window.utils.showNotification(error.message || 'Failed to save threshold settings. Please try again.', 'error');
    }
}

/**
 * Save display settings
 */
function saveDisplaySettings() {
    try {
        // Get form values
        const darkMode = document.getElementById('theme-toggle-setting').checked;
        const followSystem = document.getElementById('system-theme').checked;
        const refreshInterval = document.getElementById('refresh-interval').value;
        const chartAnimation = document.getElementById('chart-animation').checked;
        const defaultView = document.getElementById('default-view').value;
        const temperatureUnit = document.getElementById('temperature-unit').value;
        const pressureUnit = document.getElementById('pressure-unit').value;
        
        // In a real implementation, this would call an API to update display settings
        
        // Apply theme settings
        if (followSystem) {
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            window.utils.setTheme(prefersDark ? 'dark' : 'light');
        } else {
            window.utils.setTheme(darkMode ? 'dark' : 'light');
        }
        
        // Show success notification
        window.utils.showNotification('Display settings saved successfully', 'success');
        
    } catch (error) {
        console.error('Error saving display settings:', error);
        window.utils.showNotification('Failed to save display settings. Please try again.', 'error');
    }
}

/**
 * Save connection settings
 */
function saveConnectionSettings() {
    try {
        // Get form values
        const mqttBroker = document.getElementById('mqtt-broker').value;
        const mqttPort = document.getElementById('mqtt-port').value;
        const mqttUsername = document.getElementById('mqtt-username').value;
        const mqttPassword = document.getElementById('mqtt-password').value;
        
        const catalogUrl = document.getElementById('catalog-url').value;
        const timeseriesUrl = document.getElementById('timeseries-url').value;
        const analyticsUrl = document.getElementById('analytics-url').value;
        
        // In a real implementation, this would call an API to update connection settings
        
        // Show success notification
        window.utils.showNotification('Connection settings saved successfully', 'success');
        
    } catch (error) {
        console.error('Error saving connection settings:', error);
        window.utils.showNotification('Failed to save connection settings. Please try again.', 'error');
    }
}

/**
 * Save system settings
 */
function saveSystemSettings() {
    try {
        // Get form values
        const dataRetention = document.getElementById('data-retention').value;
        const dataSampling = document.getElementById('data-sampling').value;
        const predictiveAnalytics = document.getElementById('predictive-analytics').checked;
        const predictionWindow = document.getElementById('prediction-window').value;
        
        // In a real implementation, this would call an API to update system settings
        
        // Show success notification
        window.utils.showNotification('System settings saved successfully', 'success');
        
    } catch (error) {
        console.error('Error saving system settings:', error);
        window.utils.showNotification('Failed to save system settings. Please try again.', 'error');
    }
}

/**
 * Show add user modal
 */
function showAddUserModal() {
    const modal = document.getElementById('add-user-modal');
    
    if (modal) {
        // Reset form
        const form = document.getElementById('add-user-form');
        if (form) form.reset();
        
        // Show modal
        modal.classList.add('show');
    }
}

/**
 * Save new user
 */
function saveNewUser() {
    try {
        // Get form values
        const firstName = document.getElementById('new-first-name').value;
        const lastName = document.getElementById('new-last-name').value;
        const email = document.getElementById('new-email').value;
        const role = document.getElementById('new-role').value;
        const password = document.getElementById('new-password').value;
        const confirmPassword = document.getElementById('new-confirm-password').value;
        const sendWelcome = document.getElementById('send-welcome').checked;
        
        // Validate form
        if (!firstName || !lastName || !email || !role || !password) {
            throw new Error('Please fill in all required fields');
        }
        
        if (password !== confirmPassword) {
            throw new Error('Passwords do not match');
        }
        
        // In a real implementation, this would call an API to create a new user
        
        // Close modal
        const modal = document.getElementById('add-user-modal');
        if (modal) modal.classList.remove('show');
        
        // Show success notification
        window.utils.showNotification(`User ${firstName} ${lastName} created successfully`, 'success');
        
        // Refresh user list (in a real implementation)
        // loadUserList();
        
    } catch (error) {
        console.error('Error creating user:', error);
        window.utils.showNotification(error.message || 'Failed to create user. Please try again.', 'error');
    }
}

/**
 * Edit user
 * @param {string} email - User email
 */
function editUser(email) {
    // In a real implementation, this would open an edit user modal
    // and pre-fill it with the user's data
    
    window.utils.showNotification(`Edit user functionality is not implemented in this version`, 'info');
}

/**
 * Reset user password
 * @param {string} email - User email
 */
function resetUserPassword(email) {
    // In a real implementation, this would open a reset password modal
    
    window.utils.showNotification(`Reset password functionality is not implemented in this version`, 'info');
}

/**
 * Deactivate user
 * @param {string} email - User email
 */
function deactivateUser(email) {
    // In a real implementation, this would show a confirmation dialog
    // and then call an API to deactivate the user
    
    window.utils.createModal({
        title: 'Deactivate User',
        content: `Are you sure you want to deactivate user <strong>${email}</strong>?`,
        buttons: [
            {
                text: 'Cancel',
                type: 'secondary'
            },
            {
                text: 'Deactivate',
                type: 'danger',
                handler: () => {
                    // In a real implementation, this would call an API to deactivate the user
                    
                    window.utils.showNotification(`User ${email} deactivated successfully`, 'success');
                    
                    // Refresh user list (in a real implementation)
                    // loadUserList();
                }
            }
        ]
    });
}

/**
 * Activate user
 * @param {string} email - User email
 */
function activateUser(email) {
    // In a real implementation, this would call an API to activate the user
    
    window.utils.showNotification(`User ${email} activated successfully`, 'success');
    
    // Refresh user list (in a real implementation)
    // loadUserList();
}

// Export settings functions
window.settings = {
    initSettings,
    loadSettingsData,
    testConnections
};