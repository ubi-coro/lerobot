<template>
  <div class="camera-viewer">
    <div v-if="!cameras.length" class="no-cameras">
      <p class="text-muted">No cameras available</p>
    </div>
    
    <div v-else class="row g-3">
      <!-- Display available cameras (up to 4) -->
      <div 
        v-for="(camera, index) in displayedCameras" 
        :key="camera.id" 
        class="col-md-6 mb-3"
      >
        <div class="card h-100">
          <div class="card-header d-flex justify-content-between align-items-center">
            <span>{{ camera.name || `Camera ${index + 1}` }}</span>
            <span v-if="cameraStreams[camera.id]" class="badge bg-success">Live</span>
            <span v-else class="badge bg-secondary">Offline</span>
          </div>
          
          <div class="card-body p-0">
            <div class="camera-feed">
              <img 
                v-if="cameraStreams[camera.id]" 
                :src="cameraStreams[camera.id]" 
                class="img-fluid" 
                alt="Camera feed"
              />
              <div v-else class="camera-placeholder">
                <i class="bi bi-camera-video-off me-2"></i>
                <span>Camera feed unavailable</span>
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
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { useRobotStore } from '@/stores/robotStore';

const robotStore = useRobotStore();

// Computed properties
const cameras = computed(() => robotStore.availableCameras || []);
const cameraStreams = computed(() => robotStore.cameraStreams || {});

// Always show up to 4 cameras (limit if more than 4)
const displayedCameras = computed(() => {
  return cameras.value.slice(0, 4);
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