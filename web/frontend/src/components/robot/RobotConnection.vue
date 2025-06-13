<template>
  <div class="aloha-robot-control">
    <div v-if="!isConnected" class="connection-form">
      <h3>ALOHA Robot Connection</h3>

      <div class="mb-3">
        <label for="operationMode" class="form-label">Operation Mode</label>
        <select id="operationMode" v-model="operationMode" class="form-select" :disabled="isLoading">
          <option value="bimanual">Bimanual (Both Arms)</option>
          <option value="right_only">Single-Handed (Right Arm Only)</option>
          <option value="left_only">Single-Handed (Left Arm Only)</option>
        </select>
      </div>

      <div class="mb-3">
        <label for="fps" class="form-label">FPS</label>
        <input
          type="number"
          id="fps"
          v-model="fps"
          class="form-control"
          min="1"
          max="60"
          :disabled="isLoading"
        >
      </div>

      <button
        @click="connectAloha"
        class="btn btn-primary"
        :disabled="isLoading"
      >
        {{ isLoading ? 'Connecting...' : 'Connect ALOHA Robot' }}
      </button>
    </div>

    <div v-else class="robot-controls">
      <h3>ALOHA Robot Connected</h3>

      <!-- Add camera display toggle -->
      <div class="mb-3">
        <div class="form-check">
          <input
            class="form-check-input"
            type="checkbox"
            id="showCameras"
            v-model="showCameras"
          >
          <label class="form-check-label" for="showCameras">
            Show Camera Windows During Teleoperation
          </label>
        </div>
      </div>

      <p>Operation Mode: {{ operationMode }}</p>
      <p>Available Arms: {{ robotStore.status.available_arms?.join(', ') }}</p>
      <p>Cameras: {{ robotStore.status.cameras?.length || 0 }}</p>

      <div class="control-buttons">
        <button
          @click="startTeleoperation"
          class="btn btn-success me-2"
          :disabled="isTeleoperating"
        >
          {{ isTeleoperating ? 'Teleoperating...' : 'Start Teleoperation' }}
        </button>

        <button
          @click="stopTeleoperation"
          class="btn btn-warning me-2"
          :disabled="!isTeleoperating"
        >
          Stop Teleoperation
        </button>

        <button
          @click="disconnectRobot"
          class="btn btn-danger"
        >
          Disconnect
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue';
import { useRobotStore } from '@/stores/robotStore';
import robotApi from '@/services/api/robotApi';

// Initialize the robot store
const robotStore = useRobotStore();

const operationMode = ref('bimanual');
const fps = ref(30);
const isLoading = ref(false);
const errorMessage = ref('');
const showCameras = ref(true);

// Use computed properties to get reactive state from the store
const isConnected = computed(() => robotStore.isConnected);
const isTeleoperating = computed(() => robotStore.isTeleoperating);
const robotStatus = computed(() => robotStore.status);

const connectAloha = async () => {
  console.log('Attempting to connect ALOHA robot...');
  isLoading.value = true;
  errorMessage.value = '';

  try {
    const response = await robotApi.connect(operationMode.value);
    console.log('Connect response:', response);

    if (response.data.status === 'success') {
      // Update the store with the connection status
      robotStore.status.connected = true;
      robotStore.status = { ...robotStore.status, ...response.data.data };
      console.log('ALOHA robot connected:', response.data.data);
    } else {
      errorMessage.value = response.data.message || 'Connection failed';
      console.error('Connection failed:', response.data);
    }
  } catch (error) {
    console.error('Error connecting to ALOHA robot:', error);
    errorMessage.value = error.response?.data?.message || `Connection failed: ${error.message}`;
  } finally {
    isLoading.value = false;
  }
};

const startTeleoperation = async () => {
  console.log('Attempting to start teleoperation...');
  try {
    const response = await robotApi.startTeleoperation(fps.value, showCameras.value);
    console.log('Teleoperation response:', response);

    if (response.data.status === 'success') {
      robotStore.status.mode = 'teleoperating';
      console.log('Teleoperation started');
    } else {
      errorMessage.value = response.data.message || 'Failed to start teleoperation';
    }
  } catch (error) {
    console.error('Error starting teleoperation:', error);
    errorMessage.value = error.response?.data?.message || 'Failed to start teleoperation';
  }
};

const stopTeleoperation = async () => {
  console.log('Attempting to stop teleoperation...');
  try {
    const response = await robotApi.stopTeleoperation();
    console.log('Stop teleoperation response:', response);

    if (response.data.status === 'success') {
      robotStore.status.mode = null;
      console.log('Teleoperation stopped');
    } else {
      errorMessage.value = response.data.message || 'Failed to stop teleoperation';
    }
  } catch (error) {
    console.error('Error stopping teleoperation:', error);
    errorMessage.value = error.response?.data?.message || 'Failed to stop teleoperation';
  }
};

const disconnectRobot = async () => {
  console.log('Attempting to disconnect robot...');
  try {
    if (robotStore.isTeleoperating) {
      await stopTeleoperation();
    }

    const response = await robotApi.disconnect();
    console.log('Disconnect response:', response);

    if (response.data.status === 'success') {
      robotStore.status.connected = false;
      robotStore.status.mode = null;
      robotStore.status.available_arms = [];
      robotStore.status.cameras = [];
      console.log('Robot disconnected');
    }
  } catch (error) {
    console.error('Error disconnecting robot:', error);
    errorMessage.value = error.response?.data?.message || 'Failed to disconnect';
  }
};

// Initialize store when component mounts
onMounted(() => {
  robotStore.initSocket();
});
</script>

<style scoped>
.robot-connection {
  padding: 15px;
}
</style>
