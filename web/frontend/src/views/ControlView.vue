<template>
  <div class="control-view container-fluid py-4">
    <div class="row mb-4">
      <div class="col">
        <h1 class="display-6">Advanced Robot Control</h1>
        <p class="lead text-muted">Configure and control your LeRobot system with advanced teleoperation options</p>
      </div>
    </div>
    
    <!-- Navigation Tabs -->
    <ul class="nav nav-tabs mb-4" role="tablist">
      <li class="nav-item" role="presentation">
        <button 
          class="nav-link active" 
          id="control-tab" 
          data-bs-toggle="tab" 
          data-bs-target="#control-panel" 
          type="button" 
          role="tab"
        >
          <i class="bi bi-robot me-2"></i>
          Control Panel
        </button>
      </li>
      <li class="nav-item" role="presentation">
        <button 
          class="nav-link" 
          id="enhanced-tab" 
          data-bs-toggle="tab" 
          data-bs-target="#enhanced-teleoperation" 
          type="button" 
          role="tab"
        >
          <i class="bi bi-gear me-2"></i>
          Enhanced Teleoperation
        </button>
      </li>
      <li class="nav-item" role="presentation">
        <button 
          class="nav-link" 
          id="safety-tab" 
          data-bs-toggle="tab" 
          data-bs-target="#safety-controls" 
          type="button" 
          role="tab"
        >
          <i class="bi bi-shield-check me-2"></i>
          Safety Controls
        </button>
      </li>
      <li class="nav-item" role="presentation">
        <button 
          class="nav-link" 
          id="docs-tab" 
          data-bs-toggle="tab" 
          data-bs-target="#documentation" 
          type="button" 
          role="tab"
        >
          <i class="bi bi-book me-2"></i>
          Documentation
        </button>
      </li>
    </ul>

    <!-- Tab Contents -->
    <div class="tab-content">
      <!-- Control Panel Tab -->
      <div class="tab-pane fade show active" id="control-panel" role="tabpanel">
        <div class="row g-4">
          <!-- Left sidebar for controls -->
          <div class="col-lg-4">
            <!-- Robot Connection -->
            <div class="mb-4">
              <h2 class="h5 mb-3">
                <i class="bi bi-plug me-2"></i>
                Robot Connection
              </h2>
              <RobotConnection />
            </div>
          </div>
          
          <!-- Center area for robot status and teleoperation -->
          <div class="col-lg-8">
            <!-- Robot Status (Always visible) -->
            <div class="mb-4">
              <h2 class="h5 mb-3">
                <i class="bi bi-info-circle me-2"></i>
                Robot Status
              </h2>
              <div class="card">
                <div class="card-body">
                  <!-- Connection Status Display -->
                  <div class="row g-3 mb-3">
                    <div class="col-12">
                      <div class="text-center">
                        <div class="h4 mb-1">
                          <span class="badge" :class="getConnectionStatusBadgeClass()">
                            {{ getConnectionStatusText() }}
                          </span>
                        </div>
                        <div class="text-muted small">Connection Status</div>
                      </div>
                    </div>
                  </div>

                  <!-- Connected State - Show detailed stats -->
                  <div v-if="isConnected" class="row g-3">
                    <div class="col-md-4">
                      <div class="text-center">
                        <div class="h4 mb-1">{{ robotStore.status.available_arms?.length || 0 }}</div>
                        <div class="text-muted small">Available Arms</div>
                      </div>
                    </div>
                    <div class="col-md-4">
                      <div class="text-center">
                        <div class="h4 mb-1">{{ robotStore.availableCameras?.length || 0 }}</div>
                        <div class="text-muted small">Active Cameras</div>
                      </div>
                    </div>
                    <div class="col-md-4">
                      <div class="text-center">
                        <div class="h4 mb-1">{{ robotStore.status.mode || 'Idle' }}</div>
                        <div class="text-muted small">Current Mode</div>
                      </div>
                    </div>
                  </div>

                  <!-- Disconnected State - Show basic info -->
                  <div v-else class="text-center text-muted">
                    <i class="bi bi-robot display-6 mb-3"></i>
                    <p class="mb-0">No robot connected. Use the Robot Connection panel to connect to your ALOHA robot.</p>
                  </div>
                  
                  <!-- Error Information Display (Always visible when there's an error) -->
                  <div v-if="robotStore.hasError" class="mt-3">
                    <div class="alert alert-danger mb-0">
                      <div class="d-flex align-items-start">
                        <i class="bi bi-exclamation-triangle-fill me-2 mt-1"></i>
                        <div class="flex-grow-1">
                          <div class="fw-bold">Connection Error</div>
                          <div class="small mt-1">{{ robotStore.errorMessage }}</div>
                          <div class="small text-muted mt-2">
                            <i class="bi bi-lightbulb me-1"></i>
                            Try selecting a different configuration or check your robot connections
                          </div>
                        </div>
                        <button 
                          type="button" 
                          class="btn-close btn-close-white ms-2" 
                          @click="clearError"
                          aria-label="Dismiss error"
                          title="Dismiss this error message"
                        ></button>
                      </div>
                    </div>
                  </div>
                  
                  <!-- Additional Status Information -->
                  <div v-if="robotStore.status.mode === 'teleoperating'" class="mt-3">
                    <div class="alert alert-info mb-0">
                      <div class="d-flex align-items-center">
                        <i class="bi bi-activity me-2"></i>
                        <div class="flex-grow-1">
                          <div class="fw-bold">Teleoperation Active</div>
                          <div class="small">Robot is responding to leader arm movements</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            <!-- Teleoperation Control -->
            <div class="mb-4" v-if="isConnected">
              <h2 class="h5 mb-3">
                <i class="bi bi-joystick me-2"></i>
                Teleoperation Control
              </h2>
              <div class="card">
                <div class="card-header d-flex justify-content-between align-items-center">
                  <span class="fw-bold">Control Panel</span>
                  <span class="badge" :class="isTeleoperating ? 'bg-success' : 'bg-secondary'">
                    {{ isTeleoperating ? 'Active' : 'Inactive' }}
                  </span>
                </div>
                <div class="card-body">
                  <!-- Control Buttons -->
                  <div class="d-grid gap-2">
                    <button 
                      v-if="!isTeleoperating"
                      type="button" 
                      class="btn btn-success" 
                      @click="startTeleoperation" 
                      :disabled="robotStore.isLoading"
                    >
                      <span v-if="robotStore.isLoading" class="spinner-border spinner-border-sm me-2" role="status"></span>
                      <i v-else class="bi bi-play-fill me-2"></i>
                      Start Teleoperation
                    </button>
                    
                    <button 
                      v-if="isTeleoperating"
                      type="button" 
                      class="btn btn-warning" 
                      @click="stopTeleoperation" 
                      :disabled="robotStore.isLoading"
                    >
                      <span v-if="robotStore.isLoading" class="spinner-border spinner-border-sm me-2" role="status"></span>
                      <i v-else class="bi bi-stop-fill me-2"></i>
                      Stop Teleoperation
                    </button>
                    
                    <button 
                      type="button" 
                      class="btn btn-outline-primary" 
                      @click="moveToSafePosition" 
                      :disabled="robotStore.isLoading"
                    >
                      <i class="bi bi-shield-check me-2"></i>
                      Move to Safe Position
                    </button>
                    
                    <button 
                      type="button" 
                      class="btn btn-danger" 
                      @click="emergencyStop" 
                      :disabled="robotStore.isLoading"
                    >
                      <i class="bi bi-octagon-fill me-2"></i>
                      Emergency Stop
                    </button>
                  </div>
                  
                </div>
              </div>
            </div>
          </div>
        </div>
        
        <!-- Camera feeds section -->
        <div class="row mt-4" v-if="hasCameras">
          <div class="col-12">
            <h2 class="h5 mb-3">
              <i class="bi bi-camera-video me-2"></i>
              Camera Feeds
            </h2>
            <CameraViewer />
          </div>
        </div>
        
        <!-- No Cameras Info -->
        <div class="row mt-4" v-if="isConnected && !hasCameras">
          <div class="col-12">
            <div class="alert alert-info">
              <i class="bi bi-info-circle me-2"></i>
              <strong>No Cameras Active</strong> - Current configuration does not include camera feeds. 
              To enable cameras, disconnect and reconnect with a camera-enabled configuration.
            </div>
          </div>
        </div>

        <!-- Camera Debug Info Section -->
        <div class="row mt-4">
          <div class="col-12">
            <div class="card" style="border: 2px solid #007bff; background-color: #e3f2fd;">
              <div class="card-header" style="background-color: #1976d2; color: white;">
                <h5 class="card-title mb-0">🔍 Camera Debug Info</h5>
              </div>
              <div class="card-body">
                <div class="row">
                  <div class="col-md-6">
                    <p><strong>Socket Connected:</strong> {{ robotStore.socket?.connected || false }}</p>
                    <p><strong>Available Cameras:</strong> {{ robotStore.status?.cameras?.length || 0 }}</p>
                    <p><strong>Camera Names:</strong> {{ getCameraNames() }}</p>
                  </div>
                  <div class="col-md-6">
                    <p><strong>Robot Connected:</strong> {{ robotStore.isConnected }}</p>
                    <p><strong>Teleoperation Active:</strong> {{ robotStore.isTeleoperating }}</p>
                    <button class="btn btn-primary btn-sm me-2" @click="testCameraStreams">Test Camera Streams</button>
                    <button class="btn btn-secondary btn-sm" @click="stopTestStreams">Stop Test</button>
                  </div>
                </div>
                <div class="mt-3">
                  <h6>Camera Streams Active:</h6>
                  <p>{{ Object.keys(robotStore.cameraStreams || {}).join(', ') || 'None' }}</p>
                </div>
                <div class="mt-3">
                  <h6>Debug Data:</h6>
                  <pre style="font-size: 12px; max-height: 150px; overflow-y: auto; background: #f8f9fa; padding: 10px; border-radius: 4px;">{{ getDebugInfo() }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Enhanced Teleoperation Tab -->
      <div class="tab-pane fade" id="enhanced-teleoperation" role="tabpanel">
        <div class="row">
          <div class="col-12">
            <div class="mb-4">
              <h2 class="h4 mb-3">
                <i class="bi bi-gear me-2"></i>
                Advanced Teleoperation Configuration
              </h2>
              <p class="text-muted mb-4">
                Configure advanced teleoperation settings, monitoring, and specialized features for precise robot control.
              </p>
              <EnhancedTeleoperationPanel />
            </div>
          </div>
        </div>
      </div>

      <!-- Safety Controls Tab -->
      <div class="tab-pane fade" id="safety-controls" role="tabpanel">
        <div class="row">
          <div class="col-12">
            <div class="mb-4">
              <h2 class="h4 mb-3">
                <i class="bi bi-shield-check me-2"></i>
                Robot Safety Controls
              </h2>
              <p class="text-muted mb-4">
                Manage robot safety positions, emergency procedures, and protective control settings.
              </p>
              <SafePositionControl />
            </div>
          </div>
        </div>
      </div>

      <!-- Documentation Tab -->
      <div class="tab-pane fade" id="documentation" role="tabpanel">
        <TeleoperationDocs />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue';
import { useRobotStore } from '@/stores/robotStore';
import RobotConnection from '@/components/calibration/RobotConnection.vue';
import EnhancedTeleoperationPanel from '@/components/teleoperation/EnhancedTeleoperationPanel.vue';
import SafePositionControl from '@/components/calibration/SafePositionControl.vue';
import CameraViewer from '@/components/dataVisualization/CameraViewer.vue';
import TeleoperationDocs from '@/components/teleoperation/TeleoperationDocs.vue';

// Initialize the robot store
const robotStore = useRobotStore();

// Initialize socket connection when component mounts
onMounted(() => {
  console.log('🔌 ControlView mounted - initializing socket...');
  robotStore.initSocket();
});

// Computed properties
const isConnected = computed(() => robotStore.isConnected);
const isTeleoperating = computed(() => robotStore.isTeleoperating);
const hasCameras = computed(() => {
  // Only show cameras if connected AND cameras are enabled in the configuration
  return robotStore.isConnected && 
         robotStore.teleoperationConfig?.showCameras === true;
});

// Helper methods for robot status display
const getConnectionStatusText = () => {
  if (robotStore.isConnected) {
    return 'Connected';
  } else if (robotStore.hasError) {
    return 'Connection Failed';
  } else {
    return 'Disconnected';
  }
};

const getConnectionStatusBadgeClass = () => {
  if (robotStore.isConnected) {
    return 'bg-success';
  } else if (robotStore.hasError) {
    return 'bg-danger';
  } else {
    return 'bg-secondary';
  }
};

// Methods for teleoperation control
const startTeleoperation = async () => {
  try {
    await robotStore.startTeleoperation(30); // Default 30 FPS
  } catch (error) {
    console.error('Error starting teleoperation:', error);
  }
};

const stopTeleoperation = async () => {
  try {
    await robotStore.stopTeleoperation();
  } catch (error) {
    console.error('Error stopping teleoperation:', error);
  }
};

const moveToSafePosition = async () => {
  try {
    await robotStore.moveToSafePosition();
  } catch (error) {
    console.error('Error moving to safe position:', error);
  }
};

const emergencyStop = async () => {
  try {
    await robotStore.emergencyStop();
  } catch (error) {
    console.error('Error during emergency stop:', error);
  }
};

// Method to clear error messages
const clearError = () => {
  robotStore.status.error = null;
};

// Debug helper methods
const getCameraNames = () => {
  const cameras = robotStore.status?.cameras || [];
  if (cameras.length === 0) return 'None';
  return cameras.map(camera => {
    if (typeof camera === 'string') return camera;
    return camera.name || camera.id || 'Unknown';
  }).join(', ');
};

const getDebugInfo = () => {
  return JSON.stringify({
    socket: {
      connected: robotStore.socket?.connected || false,
      id: robotStore.socket?.id || null
    },
    robot: {
      connected: robotStore.isConnected,
      teleoperating: robotStore.isTeleoperating,
      hasError: robotStore.hasError,
      errorMessage: robotStore.errorMessage
    },
    cameras: {
      available: robotStore.status?.cameras || [],
      streams: Object.keys(robotStore.cameraStreams || {}),
      showCameras: robotStore.teleoperationConfig?.showCameras
    }
  }, null, 2);
};

const testCameraStreams = () => {
  console.log('🧪 Testing camera streams...');
  robotStore.initSocket();
  
  // Wait a moment for socket to connect, then start test streams
  setTimeout(() => {
    const testCameras = ['cam_high', 'cam_right_wrist', 'cam_left_wrist', 'cam_low'];
    testCameras.forEach(cameraId => {
      console.log(`Starting test stream for ${cameraId}`);
      robotStore.socket?.emit('start_camera_stream', {
        camera_id: cameraId,
        fps: 10
      });
    });
  }, 1000);
};

const stopTestStreams = () => {
  console.log('🛑 Stopping test camera streams...');
  const testCameras = ['cam_high', 'cam_right_wrist', 'cam_left_wrist', 'cam_low'];
  testCameras.forEach(cameraId => {
    console.log(`Stopping test stream for ${cameraId}`);
    robotStore.socket?.emit('stop_camera_stream', {
      camera_id: cameraId
    });
  });
  // Clear camera streams after a moment
  setTimeout(() => {
    robotStore.cameraStreams = {};
  }, 500);
};
</script>

<style scoped>
.control-view {
  min-height: 100vh;
}

.display-6 {
  font-weight: 600;
}

.lead {
  font-size: 1.1rem;
}

h2.h5 {
  font-weight: 600;
  color: #495057;
}

.nav-tabs .nav-link {
  font-weight: 500;
}

.nav-tabs .nav-link.active {
  font-weight: 600;
}

body.dark-mode h2.h5 {
  color: #e4e6eb;
}

body.dark-mode .nav-tabs {
  border-color: #444;
}

body.dark-mode .nav-tabs .nav-link {
  color: #adb5bd;
  border-color: transparent;
}

body.dark-mode .nav-tabs .nav-link:hover {
  color: #e4e6eb;
  border-color: #444 #444 #333;
}

body.dark-mode .nav-tabs .nav-link.active {
  color: #e4e6eb;
  background-color: #2a2a2a;
  border-color: #444 #444 #2a2a2a;
}

@media (max-width: 991px) {
  .col-lg-4 {
    margin-bottom: 2rem;
  }
}
</style>