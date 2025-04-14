<template>
  <div class="camera-viewer">
    <div v-if="!cameras.length" class="no-cameras">
      <p class="text-muted">No cameras available</p>
    </div>
    
    <div v-else class="row">
      <div 
        v-for="camera in cameras" 
        :key="camera.id" 
        class="col-md-6 mb-3"
      >
        <div class="card">
          <div class="card-header d-flex justify-content-between align-items-center">
            <span>{{ camera.name }}</span>
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
                <span>Camera feed unavailable</span>
              </div>
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
const cameras = computed(() => robotStore.availableCameras);
const cameraStreams = computed(() => robotStore.cameraStreams);
</script>

<style scoped>
.camera-viewer {
  width: 100%;
}

.camera-feed {
  position: relative;
  min-height: 240px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #222;
  overflow: hidden;
}

.camera-feed img {
  width: 100%;
  height: auto;
}

.camera-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  min-height: 240px;
  background-color: #222;
  color: #999;
}

.no-cameras {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 240px;
  background-color: #f8f9fa;
  border-radius: 5px;
}
</style>