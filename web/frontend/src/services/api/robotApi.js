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
  // ============================================
  // 🎮 TELEOPERATION CARD APIs
  // ============================================
  
  // Start teleoperation with LeRobot-compatible configuration
  startTeleoperation(config = {}) {
    console.log('Calling startTeleoperation with LeRobot config:', config);
    return apiCall('/teleoperate/start', {
      method: 'POST',
      body: {
        // Map our config to LeRobot parameters
        fps: config.fps || 30,
        show_cameras: config.show_cameras || true,  // LeRobot uses display_data, but we handle this in backend
        // Remove non-LeRobot parameters
        // operation_mode and environment are handled during connection, not teleoperation
      }
    });
  },

  // Stop teleoperation
  stopTeleoperation() {
    console.log('Calling stopTeleoperation...');
    return apiCall('/teleoperate/stop', {
      method: 'POST'
    });
  },

  // Get teleoperation status
  getTeleoperationStatus() {
    return apiCall('/teleoperate/status');
  },

  // Get performance metrics
  getPerformanceMetrics() {
    return apiCall('/teleoperate/performance');
  },

  // Emergency stop
  emergencyStop() {
    console.log('Calling emergencyStop...');
    return apiCall('/teleoperate/emergency-stop', {
      method: 'POST'
    });
  },

  // ============================================
  // ⚙️ CALIBRATION CARD APIs
  // ============================================
  
  // Get available robot configurations
  getConfigs() {
    console.log('Calling getConfigs...');
    return apiCall('/configs');
  },

  // Connect to robot
  connect(operationMode = 'bimanual', configSettings = {}) {
    console.log('Calling connect with operation mode:', operationMode);
    console.log('Calling connect with config settings:', configSettings);
    return apiCall('/connect', {
      method: 'POST',
      body: { 
        operation_mode: operationMode,
        config_settings: configSettings 
      }
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

  // Move robot to safe position
  moveToSafePosition(config = {}) {
    console.log('Calling moveToSafePosition with config:', config);
    return apiCall('/robot/safe-position', {
      method: 'POST',
      body: config
    });
  },

  // Run system diagnostics
  runDiagnostics() {
    console.log('Calling runDiagnostics...');
    return apiCall('/diagnostics', {
      method: 'POST'
    });
  },

  // Calibrate cameras
  calibrateCameras(config = {}) {
    console.log('Calling calibrateCameras with config:', config);
    return apiCall('/calibrate/cameras', {
      method: 'POST',
      body: config
    });
  },

  // Calibrate arms
  calibrateArms(config = {}) {
    console.log('Calling calibrateArms with config:', config);
    return apiCall('/calibrate/arms', {
      method: 'POST',
      body: config
    });
  }
};
