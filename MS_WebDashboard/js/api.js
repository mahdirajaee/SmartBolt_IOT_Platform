/**
 * API Service Module for Smart IoT Bolt Dashboard
 * Handles connections to microservices and API requests
 */

// Configuration
const API_CONFIG = {
    // Services URLs - can be updated dynamically based on the Resource Catalog
    catalog: 'http://localhost:8080',
    accountManager: 'http://localhost:8082',
    timeSeriesDB: 'http://localhost:5000/api',
    analytics: 'http://localhost:5000',
    controlCenter: 'http://localhost:8081/api',
    // Request timeout in milliseconds
    timeout: 10000,
    // Retry configuration
    retry: {
        maxRetries: 2,
        delayMs: 1000
    }
};

/**
 * Initialize the API service
 * Gets service endpoints from the Resource Catalog
 */
async function initApiService() {
    try {
        // Get all service endpoints from the catalog
        const services = await fetchServiceEndpoints();
        
        if (services) {
            // Update API_CONFIG with the actual service endpoints
            Object.keys(services).forEach(serviceKey => {
                if (API_CONFIG[serviceKey] && services[serviceKey]) {
                    API_CONFIG[serviceKey] = services[serviceKey];
                }
            });
            
            console.log('API Service initialized with endpoints:', API_CONFIG);
            return true;
        }
        
        return false;
    } catch (error) {
        console.error('Failed to initialize API service:', error);
        return false;
    }
}

/**
 * Fetch service endpoints from the Resource Catalog
 * @returns {Object} - Service endpoints
 */
async function fetchServiceEndpoints() {
    try {
        const response = await fetch(`${API_CONFIG.catalog}/services`);
        
        if (!response.ok) {
            throw new Error(`Failed to fetch service endpoints: ${response.status}`);
        }
        
        const services = await response.json();
        
        // Map service data to our config format
        const serviceMap = {};
        
        services.forEach(service => {
            if (service.name === 'AccountManager') {
                serviceMap.accountManager = service.endpoint;
            } else if (service.name === 'Time Series DB Connector') {
                serviceMap.timeSeriesDB = service.endpoint;
            } else if (service.name === 'Analytics Microservice') {
                serviceMap.analytics = service.endpoint;
            } else if (service.name === 'Control Center') {
                serviceMap.controlCenter = service.endpoint;
            }
        });
        
        return serviceMap;
    } catch (error) {
        console.error('Error fetching service endpoints:', error);
        // Return null to use default endpoints
        return null;
    }
}

/**
 * Get the base URL for a microservice
 * @param {string} service - Service name
 * @returns {string} - Base URL for the service
 */
function getServiceUrl(service) {
    return API_CONFIG[service] || null;
}

/**
 * Make a basic API request
 * @param {string} url - Full URL for the request
 * @param {Object} options - Fetch options
 * @param {number} retryCount - Current retry count
 * @returns {Promise<Object>} - Response data
 */
async function makeRequest(url, options, retryCount = 0) {
    try {
        // Add timeout controller
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), API_CONFIG.timeout);
        
        // Add the abort signal to options
        options.signal = controller.signal;
        
        // Make the request
        const response = await fetch(url, options);
        
        // Clear timeout
        clearTimeout(timeoutId);
        
        // Parse response
        if (response.ok) {
            // For non-JSON responses
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            } else {
                return {
                    status: response.status,
                    statusText: response.statusText,
                    data: await response.text()
                };
            }
        } else {
            // Handle error response
            const errorData = await response.json().catch(() => ({
                message: response.statusText
            }));
            
            throw {
                status: response.status,
                message: errorData.message || errorData.error || 'API request failed',
                data: errorData
            };
        }
    } catch (error) {
        // Handle timeout
        if (error.name === 'AbortError') {
            throw { status: 408, message: 'Request timeout' };
        }
        
        // Handle retry logic
        if (retryCount < API_CONFIG.retry.maxRetries) {
            console.warn(`Retrying request to ${url} (${retryCount + 1}/${API_CONFIG.retry.maxRetries})`);
            
            // Wait before retry
            await new Promise(resolve => setTimeout(resolve, API_CONFIG.retry.delayMs));
            
            // Retry the request
            return makeRequest(url, options, retryCount + 1);
        }
        
        // Throw the error if we've exhausted retries
        throw error;
    }
}

/**
 * Prepare request options with authorization
 * @param {Object} options - Fetch options
 * @returns {Promise<Object>} - Updated options with auth headers
 */
async function prepareRequestOptions(options = {}) {
    // Set default headers
    options.headers = options.headers || {};
    options.headers['Content-Type'] = options.headers['Content-Type'] || 'application/json';
    
    // Get auth token if available
    try {
        const token = await window.authService.getAuthToken();
        
        // Add authorization header if token exists
        if (token) {
            options.headers['Authorization'] = `Bearer ${token}`;
        }
    } catch (error) {
        console.error('Error preparing request options:', error);
    }
    
    return options;
}

/**
 * Make a GET request
 * @param {string} service - Service name
 * @param {string} endpoint - API endpoint
 * @param {Object} params - Query parameters
 * @param {Object} options - Additional fetch options
 * @returns {Promise<Object>} - Response data
 */
async function get(service, endpoint, params = {}, options = {}) {
    // Get service URL
    const baseUrl = getServiceUrl(service);
    
    if (!baseUrl) {
        throw new Error(`Service ${service} not found`);
    }
    
    // Build URL with query parameters
    let url = `${baseUrl}${endpoint}`;
    
    if (Object.keys(params).length > 0) {
        const queryParams = new URLSearchParams();
        
        for (const [key, value] of Object.entries(params)) {
            if (value !== null && value !== undefined) {
                queryParams.append(key, value);
            }
        }
        
        url += `?${queryParams.toString()}`;
    }
    
    // Prepare options with auth token
    const requestOptions = await prepareRequestOptions({
        method: 'GET',
        ...options
    });
    
    // Make request
    return makeRequest(url, requestOptions);
}

/**
 * Make a POST request
 * @param {string} service - Service name
 * @param {string} endpoint - API endpoint
 * @param {Object} data - Request body data
 * @param {Object} options - Additional fetch options
 * @returns {Promise<Object>} - Response data
 */
async function post(service, endpoint, data = {}, options = {}) {
    // Get service URL
    const baseUrl = getServiceUrl(service);
    
    if (!baseUrl) {
        throw new Error(`Service ${service} not found`);
    }
    
    // Build URL
    const url = `${baseUrl}${endpoint}`;
    
    // Prepare options with auth token
    const requestOptions = await prepareRequestOptions({
        method: 'POST',
        body: JSON.stringify(data),
        ...options
    });
    
    // Make request
    return makeRequest(url, requestOptions);
}

/**
 * Make a PUT request
 * @param {string} service - Service name
 * @param {string} endpoint - API endpoint
 * @param {Object} data - Request body data
 * @param {Object} options - Additional fetch options
 * @returns {Promise<Object>} - Response data
 */
async function put(service, endpoint, data = {}, options = {}) {
    // Get service URL
    const baseUrl = getServiceUrl(service);
    
    if (!baseUrl) {
        throw new Error(`Service ${service} not found`);
    }
    
    // Build URL
    const url = `${baseUrl}${endpoint}`;
    
    // Prepare options with auth token
    const requestOptions = await prepareRequestOptions({
        method: 'PUT',
        body: JSON.stringify(data),
        ...options
    });
    
    // Make request
    return makeRequest(url, requestOptions);
}

/**
 * Make a DELETE request
 * @param {string} service - Service name
 * @param {string} endpoint - API endpoint
 * @param {Object} options - Additional fetch options
 * @returns {Promise<Object>} - Response data
 */
async function deleteRequest(service, endpoint, options = {}) {
    // Get service URL
    const baseUrl = getServiceUrl(service);
    
    if (!baseUrl) {
        throw new Error(`Service ${service} not found`);
    }
    
    // Build URL
    const url = `${baseUrl}${endpoint}`;
    
    // Prepare options with auth token
    const requestOptions = await prepareRequestOptions({
        method: 'DELETE',
        ...options
    });
    
    // Make request
    return makeRequest(url, requestOptions);
}

/**
 * Fetch all pipelines/sectors from the catalog
 * @returns {Promise<Array>} - List of pipelines/sectors
 */
async function fetchPipelines() {
    try {
        return await get('catalog', '/sectors');
    } catch (error) {
        console.error('Error fetching pipelines:', error);
        throw error;
    }
}

/**
 * Fetch devices (bolts) for a specific pipeline
 * @param {string} pipelineId - Pipeline/sector ID
 * @returns {Promise<Array>} - List of devices in the pipeline
 */
async function fetchPipelineDevices(pipelineId) {
    try {
        return await get('catalog', `/sectors/${pipelineId}/devices`);
    } catch (error) {
        console.error(`Error fetching devices for pipeline ${pipelineId}:`, error);
        throw error;
    }
}

/**
 * Fetch sensor data for a device
 * @param {string} deviceId - Device ID
 * @param {string} sensorType - Sensor type ('temperature' or 'pressure')
 * @param {Object} timeRange - Time range object with start and end properties
 * @returns {Promise<Object>} - Sensor data
 */
async function fetchSensorData(deviceId, sensorType, timeRange = {}) {
    try {
        const params = {
            bolt_id: deviceId,
            type: sensorType
        };
        
        if (timeRange.start) {
            params.start = timeRange.start;
        }
        
        if (timeRange.end) {
            params.end = timeRange.end;
        }
        
        return await get('timeSeriesDB', '/data', params);
    } catch (error) {
        console.error(`Error fetching ${sensorType} data for device ${deviceId}:`, error);
        throw error;
    }
}

/**
 * Fetch predictions for a device
 * @param {string} deviceId - Device ID
 * @param {string} sensorType - Sensor type ('temperature' or 'pressure')
 * @param {number} hours - Number of hours to predict
 * @returns {Promise<Object>} - Prediction data
 */
async function fetchPredictions(deviceId, sensorType, hours = 24) {
    try {
        const params = {
            bolt_id: deviceId,
            type: sensorType,
            hours: hours
        };
        
        return await get('analytics', '/predictions', params);
    } catch (error) {
        console.error(`Error fetching predictions for device ${deviceId}:`, error);
        throw error;
    }
}

/**
 * Fetch alerts for all pipelines or a specific pipeline
 * @param {string} pipelineId - Optional pipeline ID
 * @returns {Promise<Array>} - List of alerts
 */
async function fetchAlerts(pipelineId = null) {
    try {
        const params = {};
        
        if (pipelineId) {
            params.pipeline_id = pipelineId;
        }
        
        return await get('analytics', '/alerts', params);
    } catch (error) {
        console.error('Error fetching alerts:', error);
        throw error;
    }
}

/**
 * Control a valve actuator
 * @param {string} deviceId - Device ID
 * @param {string} command - Command ('open' or 'close')
 * @returns {Promise<Object>} - Command result
 */
async function controlValve(deviceId, command) {
    try {
        if (command !== 'open' && command !== 'close') {
            throw new Error('Invalid command. Use "open" or "close"');
        }
        
        return await post('controlCenter', `/valve/${deviceId}`, { command });
    } catch (error) {
        console.error(`Error controlling valve for device ${deviceId}:`, error);
        throw error;
    }
}

/**
 * Fetch the latest status of all devices or a specific device
 * @param {string} deviceId - Optional device ID
 * @returns {Promise<Object>} - Latest device status
 */
async function fetchLatestStatus(deviceId = null) {
    try {
        const params = {};
        
        if (deviceId) {
            params.device_id = deviceId;
        }
        
        return await get('timeSeriesDB', '/latest', params);
    } catch (error) {
        console.error('Error fetching latest status:', error);
        throw error;
    }
}

// Export API service
window.apiService = {
    initApiService,
    get,
    post,
    put,
    delete: deleteRequest,
    fetchPipelines,
    fetchPipelineDevices,
    fetchSensorData,
    fetchPredictions,
    fetchAlerts,
    controlValve,
    fetchLatestStatus
};