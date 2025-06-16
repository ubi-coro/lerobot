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
    statusPollingTimer: null,
    // Add teleoperation configuration state
    teleoperationConfig: {
      fps: 30,
      showCameras: true,
      maxRelativeTarget: 25,
      operationMode: 'bimanual',
      enableSafeShutdown: true,
      movingTime: 0.1,
      teleopTimeLimit: null,
      performanceMonitoring: false,
      debugLevel: 'INFO'
    },
    // Performance monitoring state
    performanceMetrics: {
      actualFps: 0,
      latency: 0,
      cpuUsage: 0,
      memoryUsage: 0,
      timestamp: null
    }
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
    },

    // Set teleoperation configuration
    setTeleoperationConfig(config) {
      this.teleoperationConfig = { ...this.teleoperationConfig, ...config };
      console.log('Teleoperation configuration updated:', this.teleoperationConfig);
    },

    // Enhanced teleoperation start with configuration
    async startTeleoperationWithConfig(config = null) {
      try {
        const finalConfig = config || this.teleoperationConfig;
        
        // Prepare configuration for backend
        const teleoperationParams = {
          fps: finalConfig.fps,
          show_cameras: finalConfig.showCameras,
          max_relative_target: finalConfig.maxRelativeTarget,
          operation_mode: finalConfig.operationMode,
          enable_safe_shutdown: finalConfig.enableSafeShutdown,
          moving_time: finalConfig.movingTime,
          teleop_time_limit: finalConfig.teleopTimeLimit,
          performance_monitoring: finalConfig.performanceMonitoring,
          debug_level: finalConfig.debugLevel
        };

        const response = await robotApi.startTeleoperationAdvanced(teleoperationParams);

        if (response.data.status === 'success') {
          this.status.mode = 'teleoperating';
          
          // Start performance monitoring if enabled
          if (finalConfig.performanceMonitoring) {
            this.startPerformanceMonitoring();
          }
          
          console.log('Advanced teleoperation started with config:', finalConfig);
        } else {
          this.hasError = true;
          this.errorMessage = response.data.message || 'Failed to start teleoperation';
        }
      } catch (error) {
        console.error('Error starting advanced teleoperation:', error);
        this.hasError = true;
        this.errorMessage = error.response?.data?.message || 'Failed to start teleoperation';
      }
    },

    // Stop enhanced teleoperation
    async stopTeleoperationAdvanced() {
      try {
        const response = await robotApi.stopTeleoperation();

        if (response.data.status === 'success') {
          this.status.mode = null;
          this.stopPerformanceMonitoring();
          console.log('Advanced teleoperation stopped');
        }
      } catch (error) {
        console.error('Error stopping teleoperation:', error);
        this.hasError = true;
        this.errorMessage = error.response?.data?.message || 'Failed to stop teleoperation';
      }
    },

    // Performance monitoring
    startPerformanceMonitoring() {
      if (this.performanceTimer) {
        clearInterval(this.performanceTimer);
      }

      this.performanceTimer = setInterval(async () => {
        try {
          const response = await robotApi.getPerformanceMetrics();
          if (response.data.status === 'success') {
            this.performanceMetrics = {
              ...this.performanceMetrics,
              ...response.data.data,
              timestamp: new Date()
            };
          }
        } catch (error) {
          console.error('Error fetching performance metrics:', error);
        }
      }, 1000);
    },

    stopPerformanceMonitoring() {
      if (this.performanceTimer) {
        clearInterval(this.performanceTimer);
        this.performanceTimer = null;
      }
    },

    // Emergency stop functionality
    emergencyStop() {
      if (this.status.mode === 'teleoperating') {
        this.stopTeleoperationAdvanced();
        console.log('Emergency stop activated');
      }
    }
  }
});
