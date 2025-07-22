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

    // Connect to robot with retry logic
    async connectRobot(operationMode, configSettings = {}) {
      const maxRetries = 3;
      let retryCount = 0;
      
      while (retryCount < maxRetries) {
        try {
          this.status.error = null;
          
          console.log(`Connection attempt ${retryCount + 1}/${maxRetries}`);
          const response = await robotApi.connect(operationMode, configSettings);

          if (response.data.status === 'success') {
            this.status = { ...this.status, ...response.data.data };
            
            // Clear error state on successful connection
            this.status.error = null;
            
            console.log('Robot connected successfully');
            
            // Start status polling to get real-time updates including errors
            this.startStatusPolling(2000); // Poll every 2 seconds
            return; // Success, exit retry loop
          } else {
            throw new Error(response.data.message || 'Connection failed');
          }
        } catch (error) {
          console.error(`Connection attempt ${retryCount + 1} failed:`, error);
          retryCount++;
          
          if (retryCount >= maxRetries) {
            // Final failure
            this.status.error = `Connection failed after ${maxRetries} attempts: ${error.response?.data?.message || error.message}`;
            break;
          } else {
            // Wait before retry (exponential backoff)
            const waitTime = Math.pow(2, retryCount) * 1000; // 2s, 4s, 8s
            console.log(`Waiting ${waitTime}ms before retry...`);
            await new Promise(resolve => setTimeout(resolve, waitTime));
          }
        }
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
    async startTeleoperation(config = {}) {
      try {
        // Initialize socket connection if not already done
        this.initSocket();
        
        const response = await robotApi.startTeleoperation(config);

        if (response.data.status === 'success') {
          this.status.mode = 'teleoperating';
          
          // Start camera streams if cameras are enabled in config
          if (config.show_cameras && this.status.cameras && this.status.cameras.length > 0) {
            console.log('Starting camera streams for teleoperation');
            this.startCameraStreams(config.fps || 30);
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

    // Alias for compatibility
    async updateStatus() {
      return this.fetchRobotStatus();
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
        
        // Use the unified teleoperation API
        const response = await robotApi.startTeleoperation(finalConfig);

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
        // 1. Immediately stop teleoperation via API with timeout
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 2000); // 2 second timeout
        
        const response = await fetch('/api/robot/teleoperate/emergency-stop', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          signal: controller.signal
        });

        clearTimeout(timeoutId);

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
        this.status.error = null; // Clear any existing errors
        
        // 3. Stop camera streams
        this.stopCameraStreams();
        
        // 4. Stop performance monitoring
        this.stopPerformanceMonitoring();
        
        // 5. Stop status polling to prevent conflicts
        this.stopStatusPolling();
        
        // 6. Clear any timers or intervals
        if (this.performanceTimer) {
          clearInterval(this.performanceTimer);
          this.performanceTimer = null;
        }
        
        // 7. Emit emergency stop event via socket
        if (this.socket && this.socket.connected) {
          this.socket.emit('emergency_stop');
          // Disconnect socket to ensure clean state
          this.socket.disconnect();
          this.socket = null;
        }
        
        console.log('✅ Emergency stop local cleanup completed');
        
      } catch (localError) {
        console.error('❌ Emergency stop local cleanup failed:', localError);
      }
      
      // 8. Always log completion and ensure UI is updated
      console.log('🚨 Emergency stop procedure completed');
      
      // 9. Force Vue reactivity update
      this.$patch((state) => {
        state.status.mode = null;
        state.status.connected = false;
      });
    }
  }
});
