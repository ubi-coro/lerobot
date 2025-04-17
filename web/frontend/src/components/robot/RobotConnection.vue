<template>
  <div class="robot-connection">
    <div v-if="!isConnected" class="connection-form">
      <div class="mb-3">
        <label for="robotConfig" class="form-label">Select Robot</label>
        <select id="robotConfig" v-model="selectedConfig" class="form-select" :disabled="isLoading">
          <option v-for="config in configs" :key="config.path" :value="config.path">
            {{ config.name }}
          </option>
        </select>
      </div>
      
      <div class="mb-3">
        <label for="operationMode" class="form-label">Operation Mode</label>
        <select id="operationMode" v-model="operationMode" class="form-select" :disabled="isLoading">
          <option value="bimanual">Bimanual (Both Arms)</option>
          <option value="right_only">Single-Handed (Right Arm Only)</option>
          <option value="left_only">Single-Handed (Left Arm Only)</option>
        </select>
      </div>
      
      <div class="mb-3">
        <label for="robotOverrides" class="form-label">Robot Overrides (optional)</label>
        <input 
          type="text" 
          id="robotOverrides" 
          v-model="robotOverrides" 
          class="form-control" 
          placeholder="e.g. port=[PORT] or ~cameras" 
          :disabled="isLoading"
        />
        <small class="form-text text-muted">
          Additional overrides will be combined with the operation mode selection.
        </small>
      </div>
      
      <div class="d-grid">
        <button 
          type="button" 
          class="btn btn-primary" 
          @click="connectRobot" 
          :disabled="isLoading || !selectedConfig"
        >
          <span v-if="isLoading" class="spinner-border spinner-border-sm me-2" role="status"></span>
          Connect
        </button>
      </div>
    </div>
    
    <div v-else class="connection-info">
      <div class="d-flex justify-content-between align-items-center mb-3">
        <div>
          <strong>Connected to:</strong> 
          <span>{{ getConfigName(selectedConfig) }}</span>
        </div>
        <span class="badge bg-success">Connected</span>
      </div>
      
      <div v-if="status.available_arms && status.available_arms.length" class="mb-3">
        <strong>Available Arms:</strong>
        <ul class="list-unstyled mb-0">
          <li v-for="arm in status.available_arms" :key="arm">{{ arm }}</li>
        </ul>
      </div>
      
      <div v-if="status.cameras && status.cameras.length" class="mb-3">
        <strong>Cameras:</strong>
        <ul class="list-unstyled mb-0">
          <li v-for="camera in status.cameras" :key="camera.id">{{ camera.name }}</li>
        </ul>
      </div>
      
      <div class="d-grid">
        <button 
          type="button" 
          class="btn btn-danger" 
          @click="disconnectRobot" 
          :disabled="isLoading"
        >
          <span v-if="isLoading" class="spinner-border spinner-border-sm me-2" role="status"></span>
          Disconnect
        </button>
      </div>
    </div>
    
    <div v-if="hasError" class="alert alert-danger mt-3">
      {{ errorMessage }}
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue';
import { useRobotStore } from '@/stores/robotStore';

const robotStore = useRobotStore();

const selectedConfig = ref('');
const robotOverrides = ref('');
const operationMode = ref('bimanual'); // Default to bimanual operation

// Computed properties
const isConnected = computed(() => robotStore.isConnected);
const isLoading = computed(() => robotStore.isLoading);
const configs = computed(() => robotStore.configs);
const status = computed(() => robotStore.status);
const hasError = computed(() => robotStore.hasError);
const errorMessage = computed(() => robotStore.errorMessage);

// For Aloha, select it by default
watch(configs, (newConfigs) => {
  if (newConfigs.length > 0 && !selectedConfig.value) {
    // Find Aloha config
    const alohaConfig = newConfigs.find(config => config.name.toLowerCase().includes('aloha'));
    if (alohaConfig) {
      selectedConfig.value = alohaConfig.path;
    } else {
      // Default to first config
      selectedConfig.value = newConfigs[0].path;
    }
  }
});

// Methods
const connectRobot = async () => {
  try {
    // Start with user-provided overrides
    let overrides = robotOverrides.value.trim();
    
    // Add operation mode overrides
    if (operationMode.value === 'right_only') {
      // Exclude left arms for right-only operation
      overrides = `${overrides} ~leader_arms.left ~follower_arms.left`.trim();
    } else if (operationMode.value === 'left_only') {
      // Exclude right arms for left-only operation
      overrides = `${overrides} ~leader_arms.right ~follower_arms.right`.trim();
    }
    
    // Convert to array if not empty
    const overridesArray = overrides ? overrides.split(' ') : null;
    
    // Connect with operation mode
    await robotStore.connectRobot(selectedConfig.value, overridesArray);
  } catch (error) {
    console.error('Error connecting to robot:', error);
  }
};

const disconnectRobot = async () => {
  try {
    await robotStore.disconnectRobot();
  } catch (error) {
    console.error('Error disconnecting from robot:', error);
  }
};

const getConfigName = (configPath) => {
  const config = configs.value.find(c => c.path === configPath);
  return config ? config.name : configPath;
};

// Fetch configs on mount
onMounted(async () => {
  await robotStore.fetchConfigs();
});
</script>

<style scoped>
.robot-connection {
  padding: 15px;
}
</style>