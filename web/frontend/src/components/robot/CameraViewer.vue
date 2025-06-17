<template>
  <div class="camera-viewer">
    <div v-if="!displayedCameras.length" class="no-cameras">
      <p class="text-muted">No cameras available</p>
    </div>
    
    <div v-else class="row g-3">
      <!-- Display available cameras (up to 4) -->
      <div 
        v-for="(camera, index) in displayedCameras" 
        :key="getCameraId(camera, index)" 
        class="col-md-6 mb-3"
      >
        <div class="card h-100">
          <div class="card-header d-flex justify-content-between align-items-center">
            <span>{{ getCameraName(camera, index) }}</span>
            <span v-if="cameraStreams[getCameraId(camera, index)]" class="badge bg-success">Live</span>
            <span v-else class="badge bg-secondary">Offline</span>
          </div>
          
          <div class="card-body p-0">
            <div class="camera-feed">
              <img 
                v-if="cameraStreams[getCameraId(camera, index)]" 
                :src="cameraStreams[getCameraId(camera, index)]" 
                class="img-fluid" 
                alt="Camera feed"
                @error="onImageError(getCameraId(camera, index))"
              />
              <div v-else class="camera-placeholder">
                <i class="bi bi-camera-video-off me-2"></i>
                <span>{{ getCameraStatus(camera, index) }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Add placeholder slots to always have 4 camera positions -->
      <div 
        v-for="index in (4 - displayedCameras.length)" 
        :key="`placeholder-${index}`" 
        class="col-md-6 mb-3"
        v-if="displayedCameras.length < 4"
      >
        <div class="card h-100">
          <div class="card-header d-flex justify-content-between align-items-center">
            <span>Camera {{ displayedCameras.length + index }}</span>
            <span class="badge bg-secondary">Not Connected</span>
          </div>
          
          <div class="card-body p-0">
            <div class="camera-placeholder">
              <i class="bi bi-camera-video me-2"></i>
              <span>Camera not connected</span>
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Debug info (only in development) -->
    <div v-if="showDebugInfo" class="mt-3">
      <div class="card">
        <div class="card-header">
          <h6 class="mb-0">Camera Debug Info</h6>
        </div>
        <div class="card-body">
          <p><strong>Available Cameras:</strong> {{ JSON.stringify(cameras) }}</p>
          <p><strong>Camera Streams:</strong> {{ Object.keys(cameraStreams) }}</p>
          <p><strong>Socket Connected:</strong> {{ robotStore.socket?.connected || false }}</p>
          
          <!-- Test buttons -->
          <div class="mt-3">
            <button @click="testCameraStreams" class="btn btn-sm btn-primary me-2">
              Test Camera Streams
            </button>
            <button @click="stopTestStreams" class="btn btn-sm btn-secondary me-2">
              Stop Test Streams
            </button>
            <button @click="forceSocketConnect" class="btn btn-sm btn-info">
              Force Socket Connect
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted } from 'vue';
import { useRobotStore } from '@/stores/robotStore';

const robotStore = useRobotStore();

// Show debug info in development
const showDebugInfo = computed(() => process.env.NODE_ENV === 'development');

// Computed properties
const cameras = computed(() => robotStore.status.cameras || []);
const cameraStreams = computed(() => robotStore.cameraStreams || {});

// Always show up to 4 cameras (limit if more than 4)
const displayedCameras = computed(() => {
  return cameras.value.slice(0, 4);
});

// Helper methods to handle different camera data formats
const getCameraId = (camera, index) => {
  // Handle different camera data structures
  if (typeof camera === 'string') {
    return camera; // Camera is just a string ID
  } else if (camera && typeof camera === 'object') {
    return camera.id || camera.name || camera.key || `camera_${index}`;
  }
  return `camera_${index}`;
};

const getCameraName = (camera, index) => {
  if (typeof camera === 'string') {
    return camera;
  } else if (camera && typeof camera === 'object') {
    return camera.name || camera.id || camera.key || `Camera ${index + 1}`;
  }
  return `Camera ${index + 1}`;
};

const getCameraStatus = (camera, index) => {
  const cameraId = getCameraId(camera, index);
  if (cameraStreams.value[cameraId]) {
    return 'Loading...';
  }
  return 'Camera feed unavailable';
};

const onImageError = (cameraId) => {
  console.warn(`Failed to load camera image for ${cameraId}`);
};

// Test methods for development
const testCameraStreams = () => {
  console.log('Testing camera streams...');
  robotStore.initSocket();
  
  // Test with common ALOHA camera names
  const testCameras = ['cam_high', 'cam_right_wrist', 'cam_left_wrist', 'cam_low'];
  testCameras.forEach(cameraId => {
    robotStore.socket.emit('start_camera_stream', {
      camera_id: cameraId,
      fps: 10
    });
  });
};

const stopTestStreams = () => {
  console.log('Stopping test camera streams...');
  const testCameras = ['cam_high', 'cam_right_wrist', 'cam_left_wrist', 'cam_low'];
  testCameras.forEach(cameraId => {
    robotStore.socket.emit('stop_camera_stream', {
      camera_id: cameraId
    });
  });
  robotStore.cameraStreams = {};
};

const forceSocketConnect = () => {
  console.log('Force connecting socket...');
  robotStore.initSocket();
};

// Initialize socket connection when component mounts
onMounted(() => {
  console.log('CameraViewer mounted, initializing socket...');
  robotStore.initSocket();
});

// Cleanup when component unmounts
onUnmounted(() => {
  console.log('CameraViewer unmounted');
});
</script>

<style scoped>
.camera-viewer {
  width: 100%;
}

.camera-feed {
  position: relative;
  min-height: 220px; /* Slightly reduced height for 2x2 grid */
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #222;
  overflow: hidden;
  border-radius: 0 0 4px 4px;
}

.camera-feed img {
  width: 100%;
  height: auto;
  object-fit: cover; /* Ensures image fills space nicely */
}

.camera-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  min-height: 220px;
  background-color: #222;
  color: #999;
  border-radius: 0 0 4px 4px;
}

.no-cameras {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 220px;
  background-color: #f8f9fa;
  border-radius: 5px;
}

/* Make cameras taller on larger screens */
@media (min-width: 1200px) {
  .camera-feed, .camera-placeholder {
    min-height: 250px;
  }
}

/* Make cameras shorter on smaller screens */
@media (max-width: 991px) {
  .camera-feed, .camera-placeholder {
    min-height: 200px;
  }
}
</style>