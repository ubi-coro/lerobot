<template>
  <div class="teleoperation-view">
    <div class="page-header">
      <!-- Replaced large heading with concise left-aligned contextual intro -->
      <p class="page-intro">
        <strong>Instruction:</strong> Configure how you want to control the robot (bimanual or single arm), choose the environment, and optional external data display. Press <em>Start Teleoperation</em> to begin; hit the <kbd>Space</kbd> bar anytime for an emergency stop.
      </p>
    </div>

  <!-- Connection status card removed: dashboard handles connection -->

    <!-- Teleoperation Configuration (shown when connected) -->
  <div v-if="robotStore.isConnected" class="config-section">
      <div class="config-card">
        <h3><i class="bi bi-sliders me-2"></i>Teleoperation Settings</h3>
        
        <div class="config-grid">
          <!-- Operation Mode -->
          <div class="config-group">
            <label>Operation Mode</label>
            <div class="mode-selector">
              <button 
                v-for="mode in operationModes" 
                :key="mode.value"
                :class="['mode-btn', { active: teleoperationConfig.operationMode === mode.value }]"
                @click="teleoperationConfig.operationMode = mode.value"
              >
                <div class="mode-icon">{{ mode.icon }}</div>
                <div class="mode-info">
                  <span class="mode-name">{{ mode.name }}</span>
                  <span class="mode-desc">{{ mode.description }}</span>
                </div>
              </button>
            </div>
          </div>

          <!-- Environment Type -->
          <div class="config-group">
            <label>Environment</label>
            <div class="env-selector">
              <button 
                :class="['env-btn', { active: teleoperationConfig.environment === 'real' }]"
                @click="teleoperationConfig.environment = 'real'"
              >
                <i class="bi bi-robot"></i>
                <span>Real Robot</span>
              </button>
              <button 
                :class="['env-btn', { active: teleoperationConfig.environment === 'sim' }]"
                @click="teleoperationConfig.environment = 'sim'"
                disabled
              >
                <i class="bi bi-display"></i>
                <span>Simulation</span>
              </button>
            </div>
          </div>

          <!-- Camera Display Options (camera feeds temporarily disabled) -->
          <div class="config-group">
            <label>Display Options</label>
            <div class="display-options">
              <label class="checkbox-label" style="opacity:0.6;cursor:not-allowed;">
                <input 
                  type="checkbox" 
                  v-model="teleoperationConfig.showCameras"
                  class="config-checkbox"
                  disabled
                />
                Show Camera Feeds (disabled)
                <small>Camera streaming temporarily disabled</small>
              </label>
              
              <label class="checkbox-label">
                <input 
                  type="checkbox" 
                  v-model="teleoperationConfig.displayData"
                  class="config-checkbox"
                />
                Show External Display
                <small>Open LeRobot's display window with cameras and telemetry</small>
              </label>
            </div>
          </div>
        </div>

        <!-- Start/Stop Controls -->
        <div class="operation-controls">
          <button 
            v-if="!isOperating" 
            @click="startTeleoperation" 
            class="btn btn-success btn-lg"
            :disabled="isStarting"
          >
            <i class="bi bi-play-circle me-2"></i>
            {{ isStarting ? 'Starting...' : 'Start Teleoperation' }}
          </button>
          
          <div v-if="isOperating" class="active-controls">
            <button @click="stopTeleoperation" class="btn btn-warning btn-lg">
              <i class="bi bi-stop-circle me-2"></i>Stop Teleoperation
            </button>
            <button @click="emergencyStop" class="btn btn-danger">
              <i class="bi bi-exclamation-triangle me-2"></i>Emergency Stop
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Active Teleoperation Status -->
    <div v-if="isOperating" class="operation-status">
      <div class="status-grid">
        <div class="status-item">
          <span class="status-label">Mode</span>
          <span class="status-value">{{ getCurrentModeDisplay() }}</span>
        </div>
        <div class="status-item">
          <span class="status-label">Environment</span>
          <span class="status-value">{{ teleoperationConfig.environment === 'real' ? 'Real Robot' : 'Simulation' }}</span>
        </div>
        <div class="status-item">
          <span class="status-label">Cameras</span>
          <span class="status-value">{{ teleoperationConfig.showCameras ? 'Active' : 'Disabled' }}</span>
        </div>
        <div class="status-item">
          <span class="status-label">External Display</span>
          <span class="status-value">{{ teleoperationConfig.displayData ? 'Active' : 'Disabled' }}</span>
        </div>
        <div class="status-item">
          <span class="status-label">Duration</span>
          <span class="status-value">{{ formatDuration(operationDuration) }}</span>
        </div>
      </div>
    </div>

    <!-- Display Data Info (if enabled) -->
    <div v-if="isOperating && teleoperationConfig.displayData" class="display-data-info">
      <div class="alert alert-info">
        <i class="bi bi-window me-2"></i>
        <strong>External Display Active:</strong> LeRobot's display window should be open showing real-time camera feeds and telemetry data.
        If you don't see it, check your system for a new rerun window.
      </div>
    </div>

    <!-- Camera Feeds Disabled Notice -->
    <div v-if="isOperating" class="camera-section" style="opacity:0.6;">
      <h3><i class="bi bi-camera-video me-2"></i>Camera Feeds (disabled)</h3>
      <div class="alert alert-info" style="margin:0;">
        Camera streaming is currently disabled.
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useRobotStore } from '@/stores/robotStore'
import robotApi from '@/services/api/robotApi'

const router = useRouter()
const robotStore = useRobotStore()
// Removed storeToRefs usage (not imported) – we access reactive store state directly.

// State
const isStarting = ref(false)
const isOperating = ref(false)
const operationStartTime = ref(null)
const operationDuration = ref(0)

// Teleoperation configuration
const teleoperationConfig = ref({
  operationMode: 'bimanual',
  environment: 'real',
  showCameras: false, // disabled by default
  displayData: false  // External LeRobot display window
})

// Watch for changes in display options to make them mutually exclusive
watch(() => teleoperationConfig.value.showCameras, (newValue) => {
  if (newValue) {
    teleoperationConfig.value.displayData = false
  }
})

watch(() => teleoperationConfig.value.displayData, (newValue) => {
  if (newValue) {
    teleoperationConfig.value.showCameras = false
  }
})

// Available operation modes
const operationModes = ref([
  {
    value: 'bimanual',
    name: 'Bimanual',
    icon: '',
    description: 'Control both arms simultaneously'
  },
  {
    value: 'right_arm',
    name: 'Right Arm',
    icon: '',
    description: 'Control right arm only'
  },
  {
    value: 'left_arm',
    name: 'Left Arm',
    icon: '',
    description: 'Control left arm only'
  }
])

// Cameras: prefer those reported by backend status; fallback to common ALOHA camera IDs
const fallbackCameras = [
  { id: 'cam_high', name: 'Top View' },
  { id: 'cam_right_wrist', name: 'Right Wrist' },
  { id: 'cam_left_wrist', name: 'Left Wrist' },
  { id: 'cam_low', name: 'Low View' }
]
const availableCameras = computed(() => {
  const cams = robotStore.status.cameras || []
  if (!cams.length) return fallbackCameras
  // Normalize possible string list into objects
  return cams.map(c => (typeof c === 'string' ? { id: c, name: c } : c))
})

// Computed properties
// Removed connection status computations

// Methods
// Connection / disconnection handled elsewhere

const startTeleoperation = async () => {
  isStarting.value = true
  
  try {
    const config = {
      operation_mode: teleoperationConfig.value.operationMode,
      show_cameras: teleoperationConfig.value.showCameras,
      display_data: teleoperationConfig.value.displayData,  // Add display_data parameter
      fps: 30,
      safety_limits: true,
      performance_monitoring: true
    }
    
    // Use the dedicated teleoperation API with 'normal' preset as default
    const response = await robotApi.startTeleoperation({ ...config, preset: 'normal' })
    
    isOperating.value = true
    operationStartTime.value = Date.now()
    
    console.log('✅ Teleoperation started successfully:', response.data)
    
    // Add status polling to detect issues early
    const statusCheckInterval = setInterval(async () => {
      try {
        const status = await robotApi.getTeleoperationStatus()
        console.log('📊 Teleoperation status check:', status.data)
        
        // Check for error conditions
        if (status.data.status === 'error' || status.data.active === false) {
          console.error('⚠️ Teleoperation stopped unexpectedly:', status.data)
          clearInterval(statusCheckInterval)
          isOperating.value = false
          // Log unexpected stop; surface via alert
          console.error('Teleoperation stopped unexpectedly:', status.data)
        }
      } catch (error) {
        console.error('❌ Status check failed:', error)
        // Don't stop teleoperation just because status check failed
      }
    }, 2000) // Check every 2 seconds
    
    // Store interval for cleanup
    window.teleoperationStatusInterval = statusCheckInterval
    
  } catch (error) {
    console.error('Failed to start teleoperation:', error)
    alert(`Failed to start teleoperation: ${error.message}`)
  } finally {
    isStarting.value = false
  }
}

const stopTeleoperation = async () => {
  try {
    // Clean up status checking
    if (window.teleoperationStatusInterval) {
      clearInterval(window.teleoperationStatusInterval)
      window.teleoperationStatusInterval = null
    }
    
    await robotApi.stopTeleoperation()
    isOperating.value = false
    operationStartTime.value = null
    operationDuration.value = 0
    console.log('✅ Teleoperation stopped successfully')
  } catch (error) {
    console.error('❌ Failed to stop teleoperation:', error)
  }
}

const emergencyStop = async () => {
  try {
    await robotApi.emergencyStop()
    isOperating.value = false
    operationStartTime.value = null
    operationDuration.value = 0
  } catch (error) {
    console.error('Emergency stop failed:', error)
  }
}

const openCalibration = () => {
  router.push('/calibration')
}

const getCurrentModeDisplay = () => {
  const mode = operationModes.value.find(m => m.value === teleoperationConfig.value.operationMode)
  return mode ? mode.name : teleoperationConfig.value.operationMode
}

const formatDuration = (seconds) => {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins}:${secs.toString().padStart(2, '0')}`
}

// Update operation duration
let durationInterval = null

const startDurationTracking = () => {
  if (durationInterval) clearInterval(durationInterval)
  
  durationInterval = setInterval(() => {
    if (operationStartTime.value) {
      operationDuration.value = Math.floor((Date.now() - operationStartTime.value) / 1000)
    }
  }, 1000)
}

const stopDurationTracking = () => {
  if (durationInterval) {
    clearInterval(durationInterval)
    durationInterval = null
  }
}

// Lifecycle
onMounted(() => {
  // Ensure socket connected for receiving camera_frame events
  robotStore.initSocket()
  robotStore.updateStatus()
  startDurationTracking()
  const handleKeyPress = (event) => {
    if (event.code === 'Space' && isOperating.value) {
      event.preventDefault()
      emergencyStop()
    }
  }
  document.addEventListener('keydown', handleKeyPress)
  onUnmounted(() => {
    document.removeEventListener('keydown', handleKeyPress)
    stopDurationTracking()
  })
})

onUnmounted(() => {
  stopDurationTracking()
})
</script>

<style scoped>
.teleoperation-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
}

.page-header {
  margin-bottom: 1.25rem;
}

/* Intro paragraph style (left-aligned) */
.page-intro {
  font-size: 0.95rem;
  line-height: 1.45;
  color: #374151;
  background: #f3f4f6;
  padding: 0.85rem 1rem;
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  margin: 0; /* remove default p margin */
  text-align: left;
}

.page-intro kbd {
  background: #1f2937;
  color: #f9fafb;
  padding: 0.15rem 0.4rem;
  border-radius: 4px;
  font-size: 0.7rem;
  font-weight: 600;
}

/* Status card removed */

/* Configuration Section */
.config-section {
  margin-bottom: 2rem;
}

.config-card {
  background: white;
  border-radius: 1rem;
  padding: 2rem;
  border: 1px solid #e5e7eb;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.05);
}

.config-card h3 {
  margin: 0 0 1.5rem 0;
  color: #1f2937;
}

.config-grid {
  display: grid;
  gap: 2rem;
  margin-bottom: 2rem;
}

.config-group {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.config-group label {
  font-weight: 600;
  color: #374151;
}

/* Mode Selector */
.mode-selector {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
}

.mode-btn {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  background: white;
  border: 2px solid #e5e7eb;
  border-radius: 0.75rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.mode-btn:hover {
  border-color: #3b82f6;
  background: #eff6ff;
}

.mode-btn.active {
  border-color: #3b82f6;
  background: #dbeafe;
}

.mode-icon {
  font-size: 2rem;
}

.mode-info {
  flex: 1;
  text-align: left;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.mode-name {
  font-weight: 600;
  color: #1f2937;
}

.mode-desc {
  font-size: 0.85rem;
  color: #6b7280;
}

/* Environment Selector */
.env-selector {
  display: flex;
  gap: 1rem;
}

.env-btn {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 1rem;
  background: white;
  border: 2px solid #e5e7eb;
  border-radius: 0.75rem;
  cursor: pointer;
  transition: all 0.2s ease;
  color: #111827;
}

.env-btn:hover:not(:disabled) {
  border-color: #3b82f6;
  background: #eff6ff;
  color: #111827;
}

.env-btn.active {
  border-color: #3b82f6;
  background: #dbeafe;
  color: #111827;
}

.env-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.env-btn i {
  font-size: 1.5rem;
  color: currentColor;
}

/* Display Options */
.display-options {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

/* Unified checkbox label style with centered checkbox */
.checkbox-label {
  position: relative;
  display: block;
  cursor: pointer;
  padding: 0.85rem 1rem 1.2rem 2.75rem; /* left space for centered checkbox */
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  transition: all 0.2s ease;
  line-height: 1.1;
}
.checkbox-label:hover {
  background: #f3f4f6;
  border-color: #d1d5db;
}
.checkbox-label input.config-checkbox {
  position: absolute;
  left: 1rem;
  top: 50%;
  transform: translateY(-50%);
  margin: 0;
  width: 1.1rem;
  height: 1.1rem;
}
.checkbox-label small {
  display: block;
  color: #6b7280;
  font-size: 0.7rem;
  margin-top: 0.35rem;
}

/* Operation Controls */
.operation-controls {
  display: flex;
  justify-content: center;
  padding-top: 1.5rem;
  border-top: 1px solid #f3f4f6;
}

.active-controls {
  display: flex;
  gap: 1rem;
  align-items: center;
}

/* Operation Status */
.operation-status {
  background: white;
  border-radius: 1rem;
  padding: 1.5rem;
  border: 1px solid #e5e7eb;
  margin-bottom: 2rem;
}

.status-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 1rem;
}

.status-item {
  text-align: center;
  padding: 1rem;
  background: #f9fafb;
  border-radius: 0.5rem;
}

.status-label {
  display: block;
  font-size: 0.85rem;
  color: #6b7280;
  margin-bottom: 0.25rem;
}

.status-value {
  display: block;
  font-weight: 600;
  color: #1f2937;
}

/* Camera Section */
.camera-section {
  background: white;
  border-radius: 1rem;
  padding: 2rem;
  border: 1px solid #e5e7eb;
}

.camera-section h3 {
  margin: 0 0 1.5rem 0;
  color: #1f2937;
}

/* Display Data Info */
.display-data-info {
  margin-bottom: 2rem;
}

.alert {
  padding: 1rem;
  border-radius: 0.5rem;
  border: 1px solid transparent;
}

.alert-info {
  background-color: #e0f2fe;
  border-color: #0288d1;
  color: #01579b;
}

.camera-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 1rem;
}

.camera-feed {
  border: 1px solid #e5e7eb;
  border-radius: 0.5rem;
  overflow: hidden;
}

.camera-header {
  background: #f9fafb;
  padding: 0.75rem;
  font-weight: 600;
  color: #374151;
  border-bottom: 1px solid #e5e7eb;
}

.camera-stream {
  aspect-ratio: 16/9;
  background: #000;
  position: relative;
}

.stream-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #6b7280;
  background: #f3f4f6;
}

.stream-placeholder i {
  font-size: 2rem;
  margin-bottom: 0.5rem;
}

/* Buttons */
.btn {
  padding: 0.75rem 1.5rem;
  border: none;
  border-radius: 0.5rem;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s ease;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: #3b82f6;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #2563eb;
}

.btn-secondary {
  background: #6b7280;
  color: white;
}

.btn-secondary:hover {
  background: #4b5563;
}

.btn-success {
  background: #10b981;
  color: white;
}

.btn-success:hover:not(:disabled) {
  background: #059669;
}

.btn-warning {
  background: #f59e0b;
  color: white;
}

.btn-warning:hover {
  background: #d97706;
}

.btn-danger {
  background: #ef4444;
  color: white;
}

.btn-danger:hover {
  background: #dc2626;
}

.btn-outline {
  background: white;
  color: #3b82f6;
  border: 1px solid #3b82f6;
}

.btn-outline:hover {
  background: #3b82f6;
  color: white;
}

.btn-lg {
  padding: 1rem 2rem;
  font-size: 1.1rem;
}

/* Responsive Design */
@media (max-width: 768px) {
  .teleoperation-view {
    padding: 1rem;
  }
  
  .page-header h1 {
    font-size: 2rem;
  }
  
  .status-header {
    flex-direction: column;
    text-align: center;
    gap: 1rem;
  }
  
  .mode-selector {
    grid-template-columns: 1fr;
  }
  
  .env-selector {
    flex-direction: column;
  }
  
  .active-controls {
    flex-direction: column;
    width: 100%;
  }
  
  .camera-grid {
    grid-template-columns: 1fr;
  }
}
</style>