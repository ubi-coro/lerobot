<template>
  <div class="enhanced-teleoperation-panel">
    <div class="row g-3">
      <!-- Teleoperation Configuration -->
      <div class="col-12">
        <TeleoperationConfig @configurationApplied="onConfigurationApplied" />
      </div>
      
      <!-- Teleoperation Control -->
      <div class="col-md-6">
        <div class="card">
          <div class="card-header d-flex justify-content-between align-items-center">
            <h5 class="mb-0">Teleoperation Control</h5>
            <span 
              class="badge" 
              :class="isTeleoperating ? 'bg-success' : 'bg-secondary'"
            >
              {{ isTeleoperating ? 'Active' : 'Inactive' }}
            </span>
          </div>
          
          <div class="card-body">
            <div v-if="!isConnected" class="alert alert-warning">
              Please connect to a robot first.
            </div>
            
            <div v-else>
              <!-- Quick Start -->
              <div v-if="!isTeleoperating" class="mb-3">
                <div class="d-grid gap-2">
                  <button 
                    type="button" 
                    class="btn btn-success" 
                    @click="startTeleoperation" 
                    :disabled="isLoading"
                  >
                    <span v-if="isLoading" class="spinner-border spinner-border-sm me-2" role="status"></span>
                    <i v-else class="bi bi-play-fill me-2"></i>
                    Start Teleoperation
                  </button>
                  
                  <button 
                    type="button" 
                    class="btn btn-outline-primary" 
                    @click="moveToSafePosition" 
                    :disabled="isLoading"
                  >
                    <i class="bi bi-shield-check me-2"></i>
                    Move to Safe Position
                  </button>
                </div>
              </div>
              
              <!-- Active Teleoperation Controls -->
              <div v-else>
                <div class="alert alert-info mb-3">
                  <i class="bi bi-robot me-2"></i>
                  Teleoperation is active. Robot is ready for control.
                  <div class="mt-2 small">
                    <strong>Hotkeys:</strong> 
                    <span v-if="currentConfig.enableSafeShutdown">Space = Emergency Stop</span>
                  </div>
                </div>
                
                <div class="d-grid gap-2">
                  <button 
                    type="button" 
                    class="btn btn-warning" 
                    @click="stopTeleoperation" 
                    :disabled="isLoading"
                  >
                    <span v-if="isLoading" class="spinner-border spinner-border-sm me-2" role="status"></span>
                    <i v-else class="bi bi-stop-fill me-2"></i>
                    Stop Teleoperation
                  </button>
                  
                  <button 
                    type="button" 
                    class="btn btn-danger" 
                    @click="emergencyStop"
                  >
                    <i class="bi bi-exclamation-triangle me-2"></i>
                    Emergency Stop
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Performance Monitoring -->
      <div class="col-md-6" v-if="currentConfig.performanceMonitoring && isTeleoperating">
        <div class="card">
          <div class="card-header">
            <h5 class="mb-0">Performance Metrics</h5>
          </div>
          <div class="card-body">
            <div class="row g-2">
              <div class="col-6">
                <div class="d-flex justify-content-between">
                  <span class="text-muted">Actual FPS:</span>
                  <span class="badge bg-primary">{{ performanceMetrics.actualFps || 0 }}</span>
                </div>
              </div>
              <div class="col-6">
                <div class="d-flex justify-content-between">
                  <span class="text-muted">Latency:</span>
                  <span class="badge bg-info">{{ performanceMetrics.latency || 0 }}ms</span>
                </div>
              </div>
              <div class="col-6">
                <div class="d-flex justify-content-between">
                  <span class="text-muted">CPU Usage:</span>
                  <span class="badge bg-warning">{{ performanceMetrics.cpuUsage || 0 }}%</span>
                </div>
              </div>
              <div class="col-6">
                <div class="d-flex justify-content-between">
                  <span class="text-muted">Memory:</span>
                  <span class="badge bg-secondary">{{ performanceMetrics.memoryUsage || 0 }}%</span>
                </div>
              </div>
            </div>
            
            <!-- Performance Graph Placeholder -->
            <div class="mt-3">
              <div class="bg-light p-3 text-center" style="height: 120px; border-radius: 4px;">
                <small class="text-muted">Performance graph will be displayed here</small>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Status Information -->
      <div class="col-12" v-if="isConnected">
        <div class="card">
          <div class="card-header">
            <h5 class="mb-0">Robot Status</h5>
          </div>
          <div class="card-body">
            <div class="row g-3">
              <div class="col-md-3">
                <div class="text-center">
                  <div class="h4 mb-1">{{ robotStore.status.available_arms.length }}</div>
                  <div class="text-muted small">Available Arms</div>
                </div>
              </div>
              <div class="col-md-3">
                <div class="text-center">
                  <div class="h4 mb-1">{{ robotStore.availableCameras.length }}</div>
                  <div class="text-muted small">Active Cameras</div>
                </div>
              </div>
              <div class="col-md-3">
                <div class="text-center">
                  <div class="h4 mb-1">{{ currentConfig.operationMode }}</div>
                  <div class="text-muted small">Operation Mode</div>
                </div>
              </div>
              <div class="col-md-3">
                <div class="text-center">
                  <div class="h4 mb-1">{{ getEffectiveFps() }}</div>
                  <div class="text-muted small">Target FPS</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Error Display -->
    <div v-if="hasError" class="alert alert-danger mt-3">
      <i class="bi bi-exclamation-triangle me-2"></i>
      {{ errorMessage }}
    </div>
    
    <!-- Session Timer -->
    <div v-if="isTeleoperating && currentConfig.teleopTimeLimit" class="mt-3">
      <div class="card">
        <div class="card-body">
          <div class="d-flex justify-content-between align-items-center">
            <span>Session Time Remaining:</span>
            <span class="badge bg-warning">{{ formatTime(sessionTimeRemaining) }}</span>
          </div>
          <div class="progress mt-2" style="height: 8px;">
            <div 
              class="progress-bar bg-warning" 
              :style="`width: ${sessionProgress}%`"
            ></div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useRobotStore } from '@/stores/robotStore';
import TeleoperationConfig from './TeleoperationConfig.vue';

const robotStore = useRobotStore();

// Data
const currentConfig = ref(robotStore.teleoperationConfig);
const sessionStartTime = ref(null);
const sessionTimeRemaining = ref(0);
const sessionTimer = ref(null);

// Computed properties
const isConnected = computed(() => robotStore.isConnected);
const isTeleoperating = computed(() => robotStore.isTeleoperating);
const isLoading = computed(() => robotStore.isLoading);
const hasError = computed(() => robotStore.hasError);
const errorMessage = computed(() => robotStore.errorMessage);
const performanceMetrics = computed(() => robotStore.performanceMetrics);

const sessionProgress = computed(() => {
  if (!currentConfig.value.teleopTimeLimit || !sessionStartTime.value) return 0;
  const elapsed = (Date.now() - sessionStartTime.value) / 1000 / 60; // minutes
  return Math.min(100, (elapsed / currentConfig.value.teleopTimeLimit) * 100);
});

// Methods
const getEffectiveFps = () => {
  return currentConfig.value.fps || 'Unlimited';
};

const formatTime = (seconds) => {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
};

const onConfigurationApplied = (config) => {
  currentConfig.value = config;
  console.log('Configuration applied to teleoperation panel:', config);
};

const startTeleoperation = async () => {
  try {
    await robotStore.startTeleoperationWithConfig(currentConfig.value);
    
    // Start session timer if time limit is set
    if (currentConfig.value.teleopTimeLimit) {
      sessionStartTime.value = Date.now();
      sessionTimeRemaining.value = currentConfig.value.teleopTimeLimit * 60; // convert to seconds
      
      sessionTimer.value = setInterval(() => {
        sessionTimeRemaining.value--;
        if (sessionTimeRemaining.value <= 0) {
          stopTeleoperation();
        }
      }, 1000);
    }
    
    // Set up keyboard listener for emergency stop
    if (currentConfig.value.enableSafeShutdown) {
      document.addEventListener('keydown', handleKeyPress);
    }
    
  } catch (error) {
    console.error('Error starting teleoperation:', error);
  }
};

const stopTeleoperation = async () => {
  try {
    await robotStore.stopTeleoperationAdvanced();
    
    // Clean up session timer
    if (sessionTimer.value) {
      clearInterval(sessionTimer.value);
      sessionTimer.value = null;
    }
    sessionStartTime.value = null;
    sessionTimeRemaining.value = 0;
    
    // Remove keyboard listener
    document.removeEventListener('keydown', handleKeyPress);
    
  } catch (error) {
    console.error('Error stopping teleoperation:', error);
  }
};

const emergencyStop = async () => {
  try {
    await robotStore.emergencyStop();
    
    // Clean up timers and listeners
    if (sessionTimer.value) {
      clearInterval(sessionTimer.value);
      sessionTimer.value = null;
    }
    document.removeEventListener('keydown', handleKeyPress);
    
  } catch (error) {
    console.error('Error during emergency stop:', error);
  }
};

const moveToSafePosition = async () => {
  try {
    const safePositionConfig = {
      arms: null, // Move all arms
      timeout_s: 10.0,
      speed_factor: 0.3
    };
    
    // This would need to be implemented in the API
    console.log('Moving robot to safe position...');
    // await robotApi.moveToSafePosition(safePositionConfig);
    
  } catch (error) {
    console.error('Error moving to safe position:', error);
  }
};

const handleKeyPress = (event) => {
  if (event.code === 'Space' && currentConfig.value.enableSafeShutdown) {
    event.preventDefault();
    emergencyStop();
  }
};

// Lifecycle
onMounted(() => {
  // Initialize configuration from store
  currentConfig.value = robotStore.teleoperationConfig;
});

onUnmounted(() => {
  // Clean up timers and listeners
  if (sessionTimer.value) {
    clearInterval(sessionTimer.value);
  }
  document.removeEventListener('keydown', handleKeyPress);
});
</script>

<style scoped>
.enhanced-teleoperation-panel {
  width: 100%;
}

.card-body {
  padding: 1rem;
}

.progress {
  border-radius: 4px;
}

.badge {
  font-size: 0.8rem;
}

.alert {
  border-radius: 4px;
}

body.dark-mode .bg-light {
  background-color: #2d2d2d !important;
  color: #e4e6eb;
}
</style>
