import { defineStore } from 'pinia';
import { io } from 'socket.io-client';
import robotApi from '@/services/api/robotApi';

export const useRobotStore = defineStore('robot', {
  state: () => ({
    configs: [],
    status: {
      connected: false,
      available_arms: [],
      cameras: [],
      error: null // Use this for error state instead of separate properties
    },
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
        // Import socket.io-client
        this.socket = io('http://localhost:5000'); // Explicitly connect to backend port

        this.socket.on('connect', () => {
          console.log('Socket connected to backend');
        });

        this.socket.on('disconnect', () => {
          console.log('Socket disconnected from backend');
        });

        this.socket.on('camera_frame', (data) => {
          // Handle camera frame data
          console.log(`Received camera frame for ${data.camera_id}`);
          this.cameraStreams[data.camera_id] = data.frame;
        });

        this.socket.on('connect_error', (error) => {
          console.error('Socket connection error:', error);
        });
      }
    },

    // Start camera streams for available cameras
    startCameraStreams(fps = 10) {
      if (!this.socket) {
        this.initSocket();
      }

      // Start streams for all available cameras
      this.status.cameras.forEach(camera => {
        const cameraId = camera.name || camera.id || camera;
        console.log(`Starting camera stream for ${cameraId}`);
        this.socket.emit('start_camera_stream', {
          camera_id: cameraId,
          fps: fps
        });
      });
    },

    // Stop camera streams
    stopCameraStreams() {
      if (this.socket) {
        this.status.cameras.forEach(camera => {
          const cameraId = camera.name || camera.id || camera;
          console.log(`Stopping camera stream for ${cameraId}`);
          this.socket.emit('stop_camera_stream', {
            camera_id: cameraId
          });
        });
        
        // Clear camera streams
        this.cameraStreams = {};
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
          this.status.error = 'Invalid API response format';
        }
      } catch (error) {
        console.error('Error fetching robot configurations:', error);
        this.status.error = error.message || 'Failed to load robot configurations';
      }
    },

    // Connect to robot
    async connectRobot(operationMode, configSettings = {}) {
      try {
        this.status.error = null;
        this.errorManuallyCleared = false; // Reset manual clear flag

        const response = await robotApi.connect(operationMode, configSettings);

        if (response.data.status === 'success') {
          this.status = { ...this.status, ...response.data.data };
          
          // Clear error state on successful connection
          this.status.error = null;
          
          console.log('Robot connected successfully');
          
          // Start status polling to get real-time updates including errors
          this.startStatusPolling(2000); // Poll every 2 seconds
        } else {
          this.status.error = response.data.message || 'Connection failed';
        }
      } catch (error) {
        console.error('Error connecting to robot:', error);
        this.status.error = error.response?.data?.message || 'Connection failed';
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
            mode: null,
            error: null // Clear error on disconnect
          };
          
          console.log('Robot disconnected successfully');
        }
      } catch (error) {
        console.error('Error disconnecting robot:', error);
        this.status.error = error.response?.data?.message || 'Disconnect failed';
      }
    },

    // Start teleoperation
    async startTeleoperation(fps = 30) {
      try {
        // Initialize socket connection if not already done
        this.initSocket();
        
        const response = await robotApi.startTeleoperation(fps, this.teleoperationConfig.showCameras);

        if (response.data.status === 'success') {
          this.status.mode = 'teleoperating';
          
          // Start camera streams if cameras are enabled in config
          if (this.teleoperationConfig.showCameras && this.status.cameras && this.status.cameras.length > 0) {
            console.log('Starting camera streams for simple teleoperation');
            this.startCameraStreams(fps);
          }
          
          console.log('Teleoperation started');
        }
      } catch (error) {
        console.error('Error starting teleoperation:', error);
        this.status.error = error.response?.data?.message || 'Failed to start teleoperation';
      }
    },

    // Stop teleoperation
    async stopTeleoperation() {
      try {
        const response = await robotApi.stopTeleoperation();

        if (response.data.status === 'success') {
          this.status.mode = null;
          
          // Stop camera streams
          this.stopCameraStreams();
          
          console.log('Teleoperation stopped');
        }
      } catch (error) {
        console.error('Error stopping teleoperation:', error);
        this.status.error = error.response?.data?.message || 'Failed to stop teleoperation';
      }
    },

    // Get robot status
    async fetchRobotStatus() {
      try {
        const response = await robotApi.getStatus();

        if (response.data.status === 'success') {
          const statusData = response.data.data;
          
          // Update status fields
          this.status = {
            ...this.status,
            connected: statusData.connected,
            available_arms: statusData.available_arms || [],
            cameras: statusData.cameras || [],
            mode: statusData.mode
          };
          
          // Only update error from backend if we don't currently have an error set
          if (statusData.error && !this.status.error) {
            this.status.error = statusData.error;
          }
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
        
        // Initialize socket connection if not already done
        this.initSocket();
        
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
          
          // Start camera streams if cameras are enabled
          if (finalConfig.showCameras && this.status.cameras && this.status.cameras.length > 0) {
            console.log('Starting camera streams for teleoperation');
            this.startCameraStreams(finalConfig.fps || 10);
          }
          
          // Start performance monitoring if enabled
          if (finalConfig.performanceMonitoring) {
            this.startPerformanceMonitoring();
          }
          
          console.log('Advanced teleoperation started with config:', finalConfig);
        } else {
          this.status.error = response.data.message || 'Failed to start teleoperation';
        }
      } catch (error) {
        console.error('Error starting advanced teleoperation:', error);
        this.status.error = error.response?.data?.message || 'Failed to start teleoperation';
      }
    },

    // Stop enhanced teleoperation
    async stopTeleoperationAdvanced() {
      try {
        const response = await robotApi.stopTeleoperation();

        if (response.data.status === 'success') {
          this.status.mode = null;
          
          // Stop camera streams
          this.stopCameraStreams();
          
          this.stopPerformanceMonitoring();
          console.log('Advanced teleoperation stopped');
        }
      } catch (error) {
        console.error('Error stopping teleoperation:', error);
        this.status.error = error.response?.data?.message || 'Failed to stop teleoperation';
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

    // Enhanced emergency stop functionality (FastTrack Step 1.2)
    async emergencyStop() {
      console.log('🚨 Emergency stop initiated');
      
      try {
        // 1. Immediately stop teleoperation via API
        const response = await fetch('/api/robot/teleoperate/emergency-stop', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
        });

        if (!response.ok) {
          throw new Error(`Emergency stop API failed: ${response.status}`);
        }

        console.log('✅ Emergency stop API call successful');
        
      } catch (error) {
        console.error('❌ Emergency stop API failed:', error);
        // Continue with local cleanup even if API fails
      }

      try {
        // 2. Force local state cleanup regardless of API response
        this.status.mode = null;
        this.status.isConnected = false;
        
        // 3. Stop camera streams
        this.stopCameraStreams();
        
        // 4. Stop performance monitoring
        this.stopPerformanceMonitoring();
        
        // 5. Clear any timers or intervals
        if (this.performanceTimer) {
          clearInterval(this.performanceTimer);
          this.performanceTimer = null;
        }
        
        // 6. Emit emergency stop event via socket
        if (this.socket && this.socket.connected) {
          this.socket.emit('emergency_stop');
        }
        
        console.log('✅ Emergency stop local cleanup completed');
        
      } catch (localError) {
        console.error('❌ Emergency stop local cleanup failed:', localError);
      }
      
      // 7. Always log completion
      console.log('🚨 Emergency stop procedure completed');
    }
  }
});
