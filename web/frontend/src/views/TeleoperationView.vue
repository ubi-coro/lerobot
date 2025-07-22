<template>
  <div class="teleoperation-view">
    <div class="page-header">
      <h1><i class="bi bi-joystick me-3"></i>Robot Teleoperation</h1>
      <p class="subtitle">Real-time bimanual robot control with safety features</p>
    </div>

    <!-- Connection Status Card -->
    <div class="status-card" :class="connectionStatusClass">
      <div class="status-header">
        <div class="status-icon">
          <i :class="statusIcon"></i>
        </div>
        <div class="status-info">
          <h3>{{ statusTitle }}</h3>
          <p>{{ statusMessage }}</p>
        </div>
        <div class="status-actions" v-if="!isConnecting">
          <button 
            v-if="!robotStore.isConnected" 
            @click="connectRobot" 
            class="btn btn-primary"
            :disabled="isConnecting"
          >
            <i class="bi bi-power me-2"></i>Connect Robot
          </button>
          <button 
            v-if="robotStore.isConnected && !isOperating" 
            @click="disconnectRobot" 
            class="btn btn-secondary"
          >
            <i class="bi bi-power me-2"></i>Disconnect
          </button>
        </div>
      </div>
      
      <!-- Connection Error Details -->
      <div v-if="connectionError" class="error-details">
        <h4><i class="bi bi-exclamation-triangle me-2"></i>Connection Failed</h4>
        <p>{{ connectionError }}</p>
        <div class="error-suggestions">
          <h5>Quick fixes:</h5>
          <ul>
            <li>Check robot power and USB connections</li>
            <li>Verify robot configuration in Calibration section</li>
            <li>Ensure robot drivers are installed</li>
            <li>Try restarting the robot hardware</li>
          </ul>
          <button @click="openCalibration" class="btn btn-outline">
            <i class="bi bi-gear me-2"></i>Open Calibration
          </button>
        </div>
      </div>
    </div>

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
              >
                <i class="bi bi-display"></i>
                <span>Simulation</span>
              </button>
            </div>
          </div>

          <!-- Camera Display -->
          <div class="config-group">
            <label>
              <input 
                type="checkbox" 
                v-model="teleoperationConfig.showCameras"
                class="config-checkbox"
              />
              Show Camera Feeds
            </label>
            <small>Display real-time camera streams during teleoperation</small>
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
          <span class="status-label">Duration</span>
          <span class="status-value">{{ formatDuration(operationDuration) }}</span>
        </div>
      </div>
    </div>

    <!-- Camera Feeds (if enabled) -->
    <div v-if="isOperating && teleoperationConfig.showCameras" class="camera-section">
      <h3><i class="bi bi-camera-video me-2"></i>Camera Feeds</h3>
      <div class="camera-grid">
        <div 
          v-for="camera in availableCameras" 
          :key="camera.id"
          class="camera-feed"
        >
          <div class="camera-header">{{ camera.name }}</div>
          <div class="camera-stream">
            <!-- Camera stream placeholder - will be replaced with actual stream -->
            <div class="stream-placeholder">
              <i class="bi bi-camera-video"></i>
              <span>{{ camera.name }} Stream</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useRobotStore } from '@/stores/robotStore'
import robotApi from '@/services/api/robotApi'

const router = useRouter()
const robotStore = useRobotStore()

// State
const isConnecting = ref(false)
const isStarting = ref(false)
const isOperating = ref(false)
const connectionError = ref('')
const operationStartTime = ref(null)
const operationDuration = ref(0)

// Teleoperation configuration
const teleoperationConfig = ref({
  operationMode: 'bimanual',
  environment: 'real',
  showCameras: true
})

// Available operation modes
const operationModes = ref([
  {
    value: 'bimanual',
    name: 'Bimanual',
    icon: '🤝',
    description: 'Control both arms simultaneously'
  },
  {
    value: 'right_arm',
    name: 'Right Arm',
    icon: '👉',
    description: 'Control right arm only'
  },
  {
    value: 'left_arm',
    name: 'Left Arm',
    icon: '👈',
    description: 'Control left arm only'
  }
])

// Mock camera data (replace with actual camera detection)
const availableCameras = ref([
  { id: 'cam_high', name: 'Top View' },
  { id: 'cam_right_wrist', name: 'Right Wrist' },
  { id: 'cam_left_wrist', name: 'Left Wrist' }
])

// Computed properties
const connectionStatusClass = computed(() => {
  if (isConnecting.value) return 'connecting'
  if (connectionError.value) return 'error'
  if (robotStore.isConnected) return 'connected'
  return 'disconnected'
})

const statusIcon = computed(() => {
  if (isConnecting.value) return 'bi bi-hourglass-split'
  if (connectionError.value) return 'bi bi-exclamation-triangle'
  if (robotStore.isConnected) return 'bi bi-check-circle'
  return 'bi bi-x-circle'
})

const statusTitle = computed(() => {
  if (isConnecting.value) return 'Connecting...'
  if (connectionError.value) return 'Connection Failed'
  if (robotStore.isConnected) return 'Robot Connected'
  return 'Robot Disconnected'
})

const statusMessage = computed(() => {
  if (isConnecting.value) return 'Establishing connection to robot hardware'
  if (connectionError.value) return 'Unable to connect to robot'
  if (robotStore.isConnected) return 'Ready for teleoperation'
  return 'Click Connect Robot to begin'
})

// Methods
const connectRobot = async () => {
  isConnecting.value = true
  connectionError.value = ''
  
  try {
    // Connect to robot with default bimanual configuration
    const response = await robotApi.connect('bimanual', {
      arms: ['left', 'right'],
      cameras: availableCameras.value.map(cam => cam.id)
    })
    
    // Update robot store status
    await robotStore.updateStatus()
    
    console.log('Robot connected successfully:', response.data)
    
  } catch (error) {
    console.error('Failed to connect to robot:', error)
    connectionError.value = error.message || 'Unknown connection error'
  } finally {
    isConnecting.value = false
  }
}

const disconnectRobot = async () => {
  try {
    await robotApi.disconnect()
    await robotStore.updateStatus()
    isOperating.value = false
    operationStartTime.value = null
  } catch (error) {
    console.error('Failed to disconnect robot:', error)
  }
}

const startTeleoperation = async () => {
  isStarting.value = true
  
  try {
    const config = {
      operation_mode: teleoperationConfig.value.operationMode,
      environment: teleoperationConfig.value.environment,
      show_cameras: teleoperationConfig.value.showCameras,
      fps: 30
    }
    
    const response = await robotApi.startTeleoperation(config)
    
    isOperating.value = true
    operationStartTime.value = Date.now()
    
    console.log('Teleoperation started:', response.data)
    
  } catch (error) {
    console.error('Failed to start teleoperation:', error)
    alert(`Failed to start teleoperation: ${error.message}`)
  } finally {
    isStarting.value = false
  }
}

const stopTeleoperation = async () => {
  try {
    await robotApi.stopTeleoperation()
    isOperating.value = false
    operationStartTime.value = null
    operationDuration.value = 0
  } catch (error) {
    console.error('Failed to stop teleoperation:', error)
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
  robotStore.updateStatus()
  startDurationTracking()
  
  // Add keyboard emergency stop (Space key)
  const handleKeyPress = (event) => {
    if (event.code === 'Space' && isOperating.value) {
      event.preventDefault()
      console.log('Emergency stop triggered by Space key')
      emergencyStop()
    }
  }
  
  document.addEventListener('keydown', handleKeyPress)
  
  // Cleanup function
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
  text-align: center;
  margin-bottom: 2rem;
}

.page-header h1 {
  font-size: 2.5rem;
  font-weight: 600;
  color: #1f2937;
  margin-bottom: 0.5rem;
}

.subtitle {
  font-size: 1.2rem;
  color: #6b7280;
  margin: 0;
}

/* Status Card */
.status-card {
  background: white;
  border-radius: 1rem;
  padding: 2rem;
  margin-bottom: 2rem;
  border: 2px solid #e5e7eb;
  transition: all 0.3s ease;
}

.status-card.disconnected {
  border-color: #ef4444;
  background: linear-gradient(135deg, #fef2f2 0%, #ffffff 100%);
}

.status-card.connecting {
  border-color: #f59e0b;
  background: linear-gradient(135deg, #fffbeb 0%, #ffffff 100%);
}

.status-card.connected {
  border-color: #10b981;
  background: linear-gradient(135deg, #ecfdf5 0%, #ffffff 100%);
}

.status-card.error {
  border-color: #ef4444;
  background: linear-gradient(135deg, #fef2f2 0%, #ffffff 100%);
}

.status-header {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.status-icon {
  font-size: 3rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.status-card.disconnected .status-icon { color: #ef4444; }
.status-card.connecting .status-icon { color: #f59e0b; }
.status-card.connected .status-icon { color: #10b981; }
.status-card.error .status-icon { color: #ef4444; }

.status-info {
  flex: 1;
}

.status-info h3 {
  margin: 0 0 0.5rem 0;
  font-size: 1.5rem;
  color: #1f2937;
}

.status-info p {
  margin: 0;
  color: #6b7280;
}

.status-actions {
  display: flex;
  gap: 1rem;
}

/* Error Details */
.error-details {
  margin-top: 1.5rem;
  padding-top: 1.5rem;
  border-top: 1px solid #f3f4f6;
}

.error-details h4 {
  color: #dc2626;
  margin-bottom: 0.5rem;
}

.error-details p {
  color: #6b7280;
  margin-bottom: 1rem;
}

.error-suggestions h5 {
  color: #374151;
  margin-bottom: 0.5rem;
}

.error-suggestions ul {
  list-style: none;
  padding: 0;
  margin-bottom: 1rem;
}

.error-suggestions li {
  color: #6b7280;
  margin-bottom: 0.25rem;
  padding-left: 1.5rem;
  position: relative;
}

.error-suggestions li::before {
  content: '•';
  position: absolute;
  left: 0;
  color: #ef4444;
}

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
}

.env-btn:hover {
  border-color: #3b82f6;
  background: #eff6ff;
}

.env-btn.active {
  border-color: #3b82f6;
  background: #dbeafe;
}

.env-btn i {
  font-size: 1.5rem;
}

/* Checkbox */
.config-checkbox {
  margin-right: 0.5rem;
  transform: scale(1.2);
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