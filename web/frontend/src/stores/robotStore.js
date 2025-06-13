import { defineStore } from 'pinia';
import { io } from 'socket.io-client';
import robotApi from '@/services/api/robotApi';

export const useRobotStore = defineStore('robot', {
  state: () => ({
    configs: [],
    status: {
      connected: false,
      available_arms: [],
      cameras: []
    },
    errorMessage: '',
    hasError: false,
    socket: null,
    cameraStreams: {},
    statusPollingTimer: null
  }),

  getters: {
    isConnected: (state) => state.status.connected,
    isTeleoperating: (state) => state.status.mode === 'teleoperating',
    hasError: (state) => !!state.status.error,
    errorMessage: (state) => state.status.error,
    availableCameras: (state) => state.status.cameras || []
  },

  actions: {
    // Initialize socket connection
    initSocket() {
      if (!this.socket) {
        this.socket = io();

        this.socket.on('connect', () => {
          console.log('Socket connected');
        });

        this.socket.on('disconnect', () => {
          console.log('Socket disconnected');
        });

        this.socket.on('camera_frame', (data) => {
          // Handle camera frame data
          this.cameraStreams[data.camera_id] = data.frame;
        });
      }
    },

    // Fetch robot configurations
    async fetchRobotConfigs() {
      try {
        console.log('Fetching robot configurations from API...');
        const response = await robotApi.getConfigs();
        console.log('API response:', response);

        if (response.data && response.data.status === 'success' && response.data.data) {
          this.configs = response.data.data;
          console.log('Configs stored:', this.configs);
        } else {
          console.error('Invalid response format:', response);
          this.hasError = true;
          this.errorMessage = 'Invalid API response format';
        }
      } catch (error) {
        console.error('Error fetching robot configurations:', error);
        this.hasError = true;
        this.errorMessage = error.message || 'Failed to load robot configurations';
      }
    },

    // Connect to robot
    async connectRobot(robotConfig, robotOverrides = null) {
      try {
        this.hasError = false;
        this.errorMessage = '';

        const response = await robotApi.connect(robotConfig, robotOverrides);

        if (response.data.status === 'success') {
          this.status = { ...this.status, ...response.data.data };
          console.log('Robot connected successfully');
        } else {
          this.hasError = true;
          this.errorMessage = response.data.message || 'Connection failed';
        }
      } catch (error) {
        console.error('Error connecting to robot:', error);
        this.hasError = true;
        this.errorMessage = error.response?.data?.message || 'Connection failed';
      }
    },

    // Disconnect robot
    async disconnectRobot() {
      try {
        const response = await robotApi.disconnect();

        if (response.data.status === 'success') {
          this.status = {
            connected: false,
            available_arms: [],
            cameras: [],
            mode: null
          };
          console.log('Robot disconnected successfully');
        }
      } catch (error) {
        console.error('Error disconnecting robot:', error);
        this.hasError = true;
        this.errorMessage = error.response?.data?.message || 'Disconnect failed';
      }
    },

    // Start teleoperation
    async startTeleoperation(fps = 30) {
      try {
        const response = await robotApi.startTeleoperation(fps, false);

        if (response.data.status === 'success') {
          this.status.mode = 'teleoperating';
          console.log('Teleoperation started');
        }
      } catch (error) {
        console.error('Error starting teleoperation:', error);
        this.hasError = true;
        this.errorMessage = error.response?.data?.message || 'Failed to start teleoperation';
      }
    },

    // Stop teleoperation
    async stopTeleoperation() {
      try {
        const response = await robotApi.stopTeleoperation();

        if (response.data.status === 'success') {
          this.status.mode = null;
          console.log('Teleoperation stopped');
        }
      } catch (error) {
        console.error('Error stopping teleoperation:', error);
        this.hasError = true;
        this.errorMessage = error.response?.data?.message || 'Failed to stop teleoperation';
      }
    },

    // Get robot status
    async fetchRobotStatus() {
      try {
        const response = await robotApi.getStatus();

        if (response.data.status === 'success') {
          this.status = { ...this.status, ...response.data.data };
        }
      } catch (error) {
        console.error('Error fetching robot status:', error);
        // Don't set error state for status polling failures
      }
    },

    // Start status polling
    startStatusPolling(interval = 1000) {
      if (this.statusPollingTimer) {
        clearInterval(this.statusPollingTimer);
      }

      this.statusPollingTimer = setInterval(() => {
        if (this.status.connected) {
          this.fetchRobotStatus();
        }
      }, interval);
    },

    // Stop status polling
    stopStatusPolling() {
      if (this.statusPollingTimer) {
        clearInterval(this.statusPollingTimer);
        this.statusPollingTimer = null;
      }
    }
  }
});
