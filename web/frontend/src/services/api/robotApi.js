import axios from 'axios';

const API_URL = '/api/robot';

export default {
  // Get available robot configurations
  getConfigs() {
    return axios.get(`${API_URL}/configs`);
  },
  
  // Connect to robot
  connect(robotConfig, robotOverrides = null) {
    return axios.post(`${API_URL}/connect`, {
      robot_config: robotConfig,
      robot_overrides: robotOverrides
    });
  },
  
  // Disconnect from robot
  disconnect() {
    return axios.post(`${API_URL}/disconnect`);
  },
  
  // Get robot status
  getStatus() {
    return axios.get(`${API_URL}/status`);
  },
  
  // Start teleoperation
  startTeleoperation(fps = null, displayCameras = false) {
    return axios.post(`${API_URL}/teleoperate/start`, {
      fps,
      display_cameras: displayCameras
    });
  },
  
  // Stop teleoperation
  stopTeleoperation() {
    return axios.post(`${API_URL}/teleoperate/stop`);
  },
  
  // Send action to robot
  sendAction(action) {
    return axios.post(`${API_URL}/actions`, {
      action
    });
  }
};