import { defineStore } from 'pinia';
import { io } from 'socket.io-client';
import robotApi from '@/services/api/robotApi';

export const useRobotStore = defineStore('robot', {
  state: () => ({
    status: {
      connected: false,
      mode: null,
      error: null,
      cameras: [],
      available_arms: []
    },
    configs: [],
    isLoading: false,
    socket: null,
    cameraStreams: {}, // Map of camera ID to stream URL
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
          // Update camera stream for the specified camera
          if (data.camera_id && data.frame) {
            this.cameraStreams[data.camera_id] = `data:image/jpeg;base64,${data.frame}`;
          }
        });
      }
    },
    
    // Cleanup socket connection
    cleanupSocket() {
      if (this.socket) {
        this.socket.disconnect();
        this.socket = null;
      }
    },
    
    // Fetch robot configurations
    async fetchConfigs() {
      try {
        this.isLoading = true;
        const response = await robotApi.getConfigs();
        this.configs = response.data;
      } catch (error) {
        console.error('Error fetching robot configs:', error);
      } finally {
        this.isLoading = false;
      }
    },
    
    // Connect to robot
    async connectRobot(robotConfig, robotOverrides = null) {
      try {
        this.isLoading = true;
        const response = await robotApi.connect(robotConfig, robotOverrides);
        
        if (response.data.status === 'success') {
          // Initialize socket for camera streaming
          this.initSocket();
          
          // Start status polling
          this.startStatusPolling();
          
          // Update local status based on response data
          this.status.connected = true;
          if (response.data.data) {
            this.status.available_arms = response.data.data.available_arms || [];
            this.status.cameras = response.data.data.cameras || [];
          }
        }
        
        return response.data;
      } catch (error) {
        console.error('Error connecting to robot:', error);
        this.status.error = error.response?.data?.message || error.message;
        throw error;
      } finally {
        this.isLoading = false;
      }
    },
    
    // Disconnect from robot
    async disconnectRobot() {
      try {
        this.isLoading = true;
        
        // Stop camera streams
        this.stopAllCameraStreams();
        
        const response = await robotApi.disconnect();
        
        if (response.data.status === 'success') {
          // Stop polling and cleanup
          this.stopStatusPolling();
          this.cleanupSocket();
          
          // Reset state
          this.status.connected = false;
          this.status.mode = null;
          this.cameraStreams = {};
        }
        
        return response.data;
      } catch (error) {
        console.error('Error disconnecting from robot:', error);
        this.status.error = error.response?.data?.message || error.message;
        throw error;
      } finally {
        this.isLoading = false;
      }
    },
    
    // Start teleoperation
    async startTeleoperation(fps = null) {
      try {
        this.isLoading = true;
        const response = await robotApi.startTeleoperation(fps);
        
        if (response.data.status === 'success') {
          this.status.mode = 'teleoperating';
          
          // Start streaming all available cameras
          this.startAllCameraStreams();
        }
        
        return response.data;
      } catch (error) {
        console.error('Error starting teleoperation:', error);
        this.status.error = error.response?.data?.message || error.message;
        throw error;
      } finally {
        this.isLoading = false;
      }
    },
    
    // Stop teleoperation
    async stopTeleoperation() {
      try {
        this.isLoading = true;
        const response = await robotApi.stopTeleoperation();
        
        if (response.data.status === 'success') {
          this.status.mode = null;
        }
        
        return response.data;
      } catch (error) {
        console.error('Error stopping teleoperation:', error);
        this.status.error = error.response?.data?.message || error.message;
        throw error;
      } finally {
        this.isLoading = false;
      }
    },
    
    // Start camera streams
    startAllCameraStreams(fps = 10) {
      if (!this.socket) return;
      
      this.availableCameras.forEach(camera => {
        this.socket.emit('start_camera_stream', { 
          camera_id: camera.id,
          fps
        });
      });
    },
    
    // Stop camera streams
    stopAllCameraStreams() {
      if (!this.socket) return;
      
      this.availableCameras.forEach(camera => {
        this.socket.emit('stop_camera_stream', { 
          camera_id: camera.id 
        });
      });
    },
    
    // Send robot action
    async sendAction(action) {
      try {
        await robotApi.sendAction(action);
      } catch (error) {
        console.error('Error sending action:', error);
        this.status.error = error.response?.data?.message || error.message;
      }
    },
    
    // Fetch status
    async fetchStatus() {
      try {
        const response = await robotApi.getStatus();
        this.status = response.data;
      } catch (error) {
        console.error('Error fetching robot status:', error);
      }
    },
    
    // Start status polling
    startStatusPolling(interval = 1000) {
      this.stopStatusPolling();
      
      this.statusPollingTimer = setInterval(() => {
        this.fetchStatus();
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