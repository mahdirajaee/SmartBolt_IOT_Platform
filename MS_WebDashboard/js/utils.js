/**
 * Utility Functions for Smart IoT Bolt Dashboard
 * Contains helper functions used across the application
 */

/**
 * Format a date object to a readable string
 * @param {Date|string|number} date - Date to format
 * @param {string} format - Format string ('short', 'long', 'time', 'datetime', 'iso', 'relative')
 * @returns {string} - Formatted date string
 */
function formatDate(date, format = 'short') {
    if (!date) return 'N/A';
    
    // Parse the date if it's a string or timestamp
    const dateObj = typeof date === 'string' || typeof date === 'number' 
        ? new Date(date) 
        : date;
    
    // Check if date is valid
    if (isNaN(dateObj.getTime())) {
        return 'Invalid Date';
    }
    
    // Format based on requested format
    switch (format) {
        case 'short':
            return dateObj.toLocaleDateString();
        
        case 'long':
            return dateObj.toLocaleDateString(undefined, {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });
        
        case 'time':
            return dateObj.toLocaleTimeString();
        
        case 'datetime':
            return dateObj.toLocaleString();
        
        case 'iso':
            return dateObj.toISOString();
        
        case 'relative':
            return getRelativeTimeString(dateObj);
        
        default:
            return dateObj.toLocaleDateString();
    }
}

/**
 * Get a relative time string (e.g., "5 minutes ago")
 * @param {Date} date - Date to format
 * @returns {string} - Relative time string
 */
function getRelativeTimeString(date) {
    const now = new Date();
    const diffMs = now - date;
    
    // Convert to seconds
    const diffSec = Math.round(diffMs / 1000);
    
    if (diffSec < 60) {
        return diffSec <= 1 ? 'Just now' : `${diffSec} seconds ago`;
    }
    
    // Convert to minutes
    const diffMin = Math.round(diffSec / 60);
    
    if (diffMin < 60) {
        return diffMin === 1 ? '1 minute ago' : `${diffMin} minutes ago`;
    }
    
    // Convert to hours
    const diffHrs = Math.round(diffMin / 60);
    
    if (diffHrs < 24) {
        return diffHrs === 1 ? '1 hour ago' : `${diffHrs} hours ago`;
    }
    
    // Convert to days
    const diffDays = Math.round(diffHrs / 24);
    
    if (diffDays < 7) {
        return diffDays === 1 ? '1 day ago' : `${diffDays} days ago`;
    }
    
    // More than a week, show actual date
    return date.toLocaleDateString();
}

/**
 * Format a number with units
 * @param {number} value - Number to format
 * @param {string} unit - Unit of measurement
 * @param {number} decimals - Number of decimal places
 * @returns {string} - Formatted number with unit
 */
function formatNumberWithUnit(value, unit = '', decimals = 1) {
    if (value === undefined || value === null) {
        return 'N/A';
    }
    
    let formattedValue;
    
    if (Number.isInteger(value)) {
        formattedValue = value.toLocaleString();
    } else {
        formattedValue = value.toLocaleString(undefined, {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        });
    }
    
    return unit ? `${formattedValue} ${unit}` : formattedValue;
}

/**
 * Get a status color based on value and thresholds
 * @param {number} value - Value to check
 * @param {Object} thresholds - Thresholds object with warning and critical values
 * @returns {string} - Status string ('healthy', 'warning', or 'critical')
 */
function getStatusFromValue(value, thresholds) {
    if (value === undefined || value === null) {
        return 'unknown';
    }
    
    if (thresholds.critical !== undefined && value >= thresholds.critical) {
        return 'critical';
    }
    
    if (thresholds.warning !== undefined && value >= thresholds.warning) {
        return 'warning';
    }
    
    return 'healthy';
}

/**
 * Get a color based on status
 * @param {string} status - Status string ('healthy', 'warning', 'critical', 'unknown')
 * @param {boolean} isBackground - Whether the color is for a background
 * @returns {string} - Color value (hex or CSS variable)
 */
function getColorFromStatus(status, isBackground = false) {
    if (isBackground) {
        switch (status) {
            case 'healthy':
                return 'rgba(16, 185, 129, 0.1)';
            case 'warning':
                return 'rgba(245, 158, 11, 0.1)';
            case 'critical':
                return 'rgba(239, 68, 68, 0.1)';
            case 'unknown':
            default:
                return 'rgba(100, 116, 139, 0.1)';
        }
    } else {
        switch (status) {
            case 'healthy':
                return '#10b981'; // success-color
            case 'warning':
                return '#f59e0b'; // warning-color
            case 'critical':
                return '#ef4444'; // danger-color
            case 'unknown':
            default:
                return '#64748b'; // secondary-color
        }
    }
}

/**
 * Truncate a string to a maximum length
 * @param {string} str - String to truncate
 * @param {number} maxLength - Maximum length
 * @returns {string} - Truncated string
 */
function truncateString(str, maxLength = 50) {
    if (!str) return '';
    
    if (str.length <= maxLength) {
        return str;
    }
    
    return str.substring(0, maxLength - 3) + '...';
}

/**
 * Debounce a function to avoid multiple rapid calls
 * @param {Function} func - Function to debounce
 * @param {number} wait - Debounce wait time in milliseconds
 * @returns {Function} - Debounced function
 */
function debounce(func, wait = 300) {
    let timeout;
    
    return function(...args) {
        const context = this;
        
        const later = function() {
            timeout = null;
            func.apply(context, args);
        };
        
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Throttle a function to limit its call frequency
 * @param {Function} func - Function to throttle
 * @param {number} limit - Throttle limit in milliseconds
 * @returns {Function} - Throttled function
 */
function throttle(func, limit = 300) {
    let inThrottle;
    
    return function(...args) {
        const context = this;
        
        if (!inThrottle) {
            func.apply(context, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

/**
 * Clone an object deeply
 * @param {Object} obj - Object to clone
 * @returns {Object} - Cloned object
 */
function deepClone(obj) {
    if (obj === null || typeof obj !== 'object') {
        return obj;
    }
    
    return JSON.parse(JSON.stringify(obj));
}

/**
 * Generate a random ID string
 * @param {number} length - ID length
 * @returns {string} - Random ID
 */
function generateId(length = 10) {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
    let result = '';
    
    for (let i = 0; i < length; i++) {
        result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    
    return result;
}

/**
 * Show a notification toast message
 * @param {string} message - Message to display
 * @param {string} type - Message type ('success', 'error', 'warning', 'info')
 * @param {number} duration - Duration in milliseconds
 */
function showNotification(message, type = 'info', duration = 5000) {
    // Create notification container if it doesn't exist
    let container = document.getElementById('notification-container');
    
    if (!container) {
        container = document.createElement('div');
        container.id = 'notification-container';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
        `;
        document.body.appendChild(container);
    }
    
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.style.cssText = `
        margin-bottom: 10px;
        padding: 15px;
        border-radius: 4px;
        display: flex;
        align-items: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        animation: notification 5s ease forwards;
        max-width: 350px;
    `;
    
    // Set background color based on type
    let backgroundColor, iconClass;
    
    switch (type) {
        case 'success':
            backgroundColor = '#10b981'; // success-color
            iconClass = 'fa-check-circle';
            break;
        case 'error':
            backgroundColor = '#ef4444'; // danger-color
            iconClass = 'fa-exclamation-circle';
            break;
        case 'warning':
            backgroundColor = '#f59e0b'; // warning-color
            iconClass = 'fa-exclamation-triangle';
            break;
        case 'info':
        default:
            backgroundColor = '#3b82f6'; // info-color
            iconClass = 'fa-info-circle';
            break;
    }
    
    notification.style.backgroundColor = backgroundColor;
    notification.style.color = '#ffffff';
    
    // Create icon
    const icon = document.createElement('i');
    icon.className = `fas ${iconClass}`;
    icon.style.marginRight = '10px';
    icon.style.fontSize = '18px';
    
    // Create message
    const messageElement = document.createElement('span');
    messageElement.textContent = message;
    messageElement.style.flex = '1';
    
    // Create close button
    const closeButton = document.createElement('i');
    closeButton.className = 'fas fa-times';
    closeButton.style.cursor = 'pointer';
    closeButton.style.marginLeft = '10px';
    
    closeButton.addEventListener('click', () => {
        notification.remove();
    });
    
    // Assemble notification
    notification.appendChild(icon);
    notification.appendChild(messageElement);
    notification.appendChild(closeButton);
    
    // Add to container
    container.appendChild(notification);
    
    // Remove after duration
    setTimeout(() => {
        notification.remove();
    }, duration);
}

/**
 * Create a modal dialog
 * @param {Object} options - Modal options
 * @param {string} options.title - Modal title
 * @param {string} options.content - Modal content HTML
 * @param {Array} options.buttons - Modal buttons configuration
 * @param {boolean} options.closeOnBackdrop - Whether to close on backdrop click
 * @returns {Object} - Modal controller object
 */
function createModal(options = {}) {
    const {
        title = 'Modal',
        content = '',
        buttons = [{ text: 'Close', type: 'secondary' }],
        closeOnBackdrop = true
    } = options;
    
    // Create modal container
    const modalContainer = document.createElement('div');
    modalContainer.className = 'modal-container';
    modalContainer.style.cssText = `
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background-color: rgba(0, 0, 0, 0.5);
        display: flex;
        justify-content: center;
        align-items: center;
        z-index: 9999;
        opacity: 0;
        visibility: hidden;
        transition: opacity 0.3s, visibility 0.3s;
    `;
    
    // Create modal
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.style.cssText = `
        width: 100%;
        max-width: 500px;
        background-color: var(--bg-card);
        border-radius: var(--border-radius);
        box-shadow: var(--box-shadow);
        overflow: hidden;
        transform: translateY(20px);
        transition: transform 0.3s;
    `;
    
    // Create modal header
    const modalHeader = document.createElement('div');
    modalHeader.className = 'modal-header';
    modalHeader.style.cssText = `
        padding: var(--spacing-lg);
        border-bottom: 1px solid var(--border-color);
        display: flex;
        justify-content: space-between;
        align-items: center;
    `;
    
    const modalTitle = document.createElement('h3');
    modalTitle.textContent = title;
    modalTitle.style.margin = '0';
    
    const modalClose = document.createElement('button');
    modalClose.className = 'modal-close';
    modalClose.innerHTML = '<i class="fas fa-times"></i>';
    modalClose.style.cssText = `
        background: transparent;
        border: none;
        color: var(--text-secondary);
        font-size: var(--font-size-lg);
        cursor: pointer;
    `;
    
    modalHeader.appendChild(modalTitle);
    modalHeader.appendChild(modalClose);
    
    // Create modal body
    const modalBody = document.createElement('div');
    modalBody.className = 'modal-body';
    modalBody.style.cssText = `
        padding: var(--spacing-lg);
        max-height: 70vh;
        overflow-y: auto;
    `;
    modalBody.innerHTML = content;
    
    // Create modal footer
    const modalFooter = document.createElement('div');
    modalFooter.className = 'modal-footer';
    modalFooter.style.cssText = `
        padding: var(--spacing-lg);
        border-top: 1px solid var(--border-color);
        display: flex;
        justify-content: flex-end;
    `;
    
    // Add buttons
    buttons.forEach(button => {
        const btn = document.createElement('button');
        btn.textContent = button.text || 'Button';
        btn.className = `btn-${button.type || 'secondary'}`;
        btn.style.cssText = `
            padding: var(--spacing-md) var(--spacing-lg);
            border-radius: var(--border-radius);
            font-weight: var(--font-weight-medium);
            margin-left: var(--spacing-md);
            cursor: pointer;
            border: none;
        `;
        
        // Set button styles based on type
        if (button.type === 'primary') {
            btn.style.backgroundColor = 'var(--primary-color)';
            btn.style.color = 'var(--text-inverted)';
        } else if (button.type === 'danger') {
            btn.style.backgroundColor = 'var(--danger-color)';
            btn.style.color = 'var(--text-inverted)';
        } else {
            btn.style.backgroundColor = 'var(--bg-tertiary)';
            btn.style.color = 'var(--text-primary)';
        }
        
        // Add click handler
        if (typeof button.handler === 'function') {
            btn.addEventListener('click', e => {
                button.handler(e, {
                    close: () => closeModal()
                });
            });
        } else {
            btn.addEventListener('click', () => closeModal());
        }
        
        modalFooter.appendChild(btn);
    });
    
    // Assemble modal
    modal.appendChild(modalHeader);
    modal.appendChild(modalBody);
    modal.appendChild(modalFooter);
    modalContainer.appendChild(modal);
    
    // Add to document
    document.body.appendChild(modalContainer);
    
    // Close modal function
    function closeModal() {
        modalContainer.style.opacity = '0';
        modalContainer.style.visibility = 'hidden';
        modal.style.transform = 'translateY(20px)';
        
        // Remove from DOM after transition
        setTimeout(() => {
            modalContainer.remove();
        }, 300);
    }
    
    // Open modal function
    function openModal() {
        // Show modal with animation
        setTimeout(() => {
            modalContainer.style.opacity = '1';
            modalContainer.style.visibility = 'visible';
            modal.style.transform = 'translateY(0)';
        }, 10);
    }
    
    // Close handlers
    modalClose.addEventListener('click', closeModal);
    
    if (closeOnBackdrop) {
        modalContainer.addEventListener('click', e => {
            if (e.target === modalContainer) {
                closeModal();
            }
        });
    }
    
    // Open modal
    openModal();
    
    // Return controller
    return {
        close: closeModal,
        modal: modalContainer
    };
}

/**
 * Convert temperature between Celsius and Fahrenheit
 * @param {number} value - Temperature value
 * @param {string} from - Source unit ('C' or 'F')
 * @param {string} to - Target unit ('C' or 'F')
 * @returns {number} - Converted temperature
 */
function convertTemperature(value, from = 'C', to = 'F') {
    if (from === to) {
        return value;
    }
    
    if (from === 'C' && to === 'F') {
        return (value * 9/5) + 32;
    }
    
    if (from === 'F' && to === 'C') {
        return (value - 32) * 5/9;
    }
    
    return value;
}

/**
 * Convert pressure between different units
 * @param {number} value - Pressure value
 * @param {string} from - Source unit ('bar', 'psi', 'kPa')
 * @param {string} to - Target unit ('bar', 'psi', 'kPa')
 * @returns {number} - Converted pressure
 */
function convertPressure(value, from = 'bar', to = 'psi') {
    if (from === to) {
        return value;
    }
    
    // Convert to bar first (as intermediate unit)
    let barValue = value;
    
    switch (from) {
        case 'psi':
            barValue = value * 0.0689476;
            break;
        case 'kPa':
            barValue = value * 0.01;
            break;
    }
    
    // Convert from bar to target unit
    switch (to) {
        case 'psi':
            return barValue * 14.5038;
        case 'kPa':
            return barValue * 100;
        default:
            return barValue; // bar
    }
}

/**
 * Set theme preference (light/dark)
 * @param {string} theme - Theme name ('light' or 'dark')
 */
function setTheme(theme) {
    if (theme === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
        localStorage.setItem('theme', 'dark');
    } else {
        document.documentElement.setAttribute('data-theme', 'light');
        localStorage.setItem('theme', 'light');
    }
}

/**
 * Load and apply theme preference from storage
 */
function loadTheme() {
    const savedTheme = localStorage.getItem('theme');
    
    if (savedTheme) {
        setTheme(savedTheme);
    } else {
        // Check for OS preference
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        setTheme(prefersDark ? 'dark' : 'light');
    }
}

/**
 * Initialize theme switcher
 */
function initThemeSwitcher() {
    const themeSwitch = document.getElementById('theme-switch');
    
    if (themeSwitch) {
        // Set initial state
        themeSwitch.checked = document.documentElement.getAttribute('data-theme') === 'dark';
        
        // Add change listener
        themeSwitch.addEventListener('change', function() {
            setTheme(this.checked ? 'dark' : 'light');
        });
    }
}

// Export utility functions
window.utils = {
    formatDate,
    formatNumberWithUnit,
    getStatusFromValue,
    getColorFromStatus,
    truncateString,
    debounce,
    throttle,
    deepClone,
    generateId,
    showNotification,
    createModal,
    convertTemperature,
    convertPressure,
    setTheme,
    loadTheme,
    initThemeSwitcher
};

// Initialize theme on load
document.addEventListener('DOMContentLoaded', loadTheme);