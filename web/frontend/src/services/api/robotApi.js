const API_BASE = '/api/robot';

// Helper function for making API calls with fetch
async function apiCall(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;

  const config = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers
    },
    ...options
  };

  // Convert body object to JSON string if needed
  if (config.body && typeof config.body === 'object') {
    config.body = JSON.stringify(config.body);
  }

  console.log(`Making ${config.method || 'GET'} request to ${url}`);

  try {
    const response = await fetch(url, config);

    // Parse JSON response
    let data;
    try {
      data = await response.json();
    } catch (parseError) {
      console.error('Failed to parse JSON response:', parseError);
      throw new Error('Invalid JSON response from server');
    }

    console.log(`Response from ${url}:`, data);

    // Check if response is successful
    if (!response.ok) {
      const errorMessage = data.message || `HTTP ${response.status}: ${response.statusText}`;
      throw new Error(errorMessage);
    }

    // Return in axios-like format for compatibility
    return { data };

  } catch (error) {
    console.error(`Error calling ${url}:`, error);

    // Create axios-like error object for compatibility
    const apiError = new Error(error.message);
    apiError.response = {
      data: { message: error.message },
      status: error.status || 500
    };

    throw apiError;
  }
}

export default {
  // Get available robot configurations
  getConfigs() {
    console.log('Calling getConfigs...');
    return apiCall('/configs');
  },

  // Connect to robot
  connect(operationMode = 'bimanual') {
    console.log('Calling connect with operation mode:', operationMode);
    return apiCall('/connect', {
      method: 'POST',
      body: { operation_mode: operationMode }
    });
  },

  // Disconnect from robot
  disconnect() {
    console.log('Calling disconnect...');
    return apiCall('/disconnect', {
      method: 'POST'
    });
  },

  // Get robot status
  getStatus() {
    console.log('Calling getStatus...');
    return apiCall('/status');
  },

  // Start teleoperation
  startTeleoperation(fps = 30, showCameras = true) {
    console.log('Calling startTeleoperation with fps:', fps, 'showCameras:', showCameras);
    return apiCall('/teleoperate/start', {
      method: 'POST',
      body: { fps, show_cameras: showCameras }
    });
  },

  // Stop teleoperation
  stopTeleoperation() {
    console.log('Calling stopTeleoperation...');
    return apiCall('/teleoperate/stop', {
      method: 'POST'
    });
  }
};
