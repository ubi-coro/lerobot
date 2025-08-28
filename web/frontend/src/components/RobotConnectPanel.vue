<template>
  <div class="status-card" :class="connectionStatusClass" ref="panelRoot">
    <div class="status-header">
      <div class="status-icon">
        <i :class="statusIcon"></i>
      </div>
      <div class="status-info">
        <h3>{{ statusTitle }}</h3>
        <p>{{ statusMessage }}</p>
      </div>
      <div class="status-actions" v-if="!busy">
        <button 
          v-if="!isConnected" 
          @click="connect" 
          class="btn btn-primary" 
          :disabled="busy"
        >
          <i class="bi bi-power me-2"></i>Connect Robot
        </button>
        <button 
          v-if="isConnected" 
          @click="disconnect" 
          class="btn btn-secondary"
        >
          <i class="bi bi-power me-2"></i>Disconnect
        </button>
      </div>
    </div>
    <div v-if="error && !isConnected" class="error-details">
      <h4><i class="bi bi-exclamation-triangle me-2"></i>Connection Failed</h4>
      <p>{{ error }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue';
const emit = defineEmits(['connect-error','connected']);
import { useRobotStore } from '@/stores/robotStore';
import robotApi from '@/services/api/robotApi';

const robotStore = useRobotStore();
const busy = ref(false);
const error = ref('');

const isConnected = computed(()=> robotStore.status.connected);
// Mirror TeleoperationView naming for exact design parity
const connectionStatusClass = computed(() => {
  if (busy.value) return 'connecting';
  if (error.value) return 'error';
  if (isConnected.value) return 'connected';
  return 'disconnected';
});
const statusIcon = computed(() => {
  if (busy.value) return 'bi bi-hourglass-split';
  if (error.value) return 'bi bi-exclamation-triangle';
  if (isConnected.value) return 'bi bi-check-circle';
  return 'bi bi-x-circle';
});
const statusTitle = computed(() => {
  if (busy.value) return 'Connecting...';
  if (error.value) return 'Connection Failed';
  if (isConnected.value) return 'Robot Connected';
  return 'Robot Disconnected';
});
const statusMessage = computed(() => {
  if (busy.value) return 'Establishing connection to robot hardware';
  if (error.value) return 'Unable to connect to robot';
  if (isConnected.value) return 'Ready for operations';
  return 'Click Connect Robot to begin';
});

async function connect(){
  try {
    busy.value = true; error.value='';
    // Minimal connect: fetch configs first (if not loaded), then connect using first config
    if (!robotStore.configs || robotStore.configs.length === 0){
      await robotStore.fetchRobotConfigs();
    }
    // Mirror TeleoperationView connect signature: first param operation mode, second settings
    const defaultMode = 'bimanual';
    const cameras = (robotStore.availableCameras || []).map(c => c.id) || [];
    const response = await robotApi.connect(defaultMode, {
      arms: ['left','right'],
      cameras
    });
    if (response.data.status !== 'success') {
      throw new Error(response.data.message || 'Connect failed');
    }
    await robotStore.updateStatus();
    emit('connected');
  } catch(e){
    error.value = e.message || 'Connection error';
    if ((error.value || '').toLowerCase().includes('calibr')) {
      emit('connect-error', error.value);
    }
  } finally { busy.value=false; }
}

async function disconnect(){
  try { await robotStore.disconnectRobot(); } catch(e){ /* ignore */ }
}
</script>

<style scoped>
/* Exact teleoperation card styling duplicated for parity */
.status-card { background: white; border-radius: 1rem; padding: 2rem; margin-bottom: 2rem; border: 2px solid #e5e7eb; transition: all 0.3s ease; }
.status-card.disconnected { border-color: #ef4444; background: linear-gradient(135deg, #fef2f2 0%, #ffffff 100%); }
.status-card.connecting { border-color: #f59e0b; background: linear-gradient(135deg, #fffbeb 0%, #ffffff 100%); }
.status-card.connected { border-color: #10b981; background: linear-gradient(135deg, #ecfdf5 0%, #ffffff 100%); }
.status-card.error { border-color: #ef4444; background: linear-gradient(135deg, #fef2f2 0%, #ffffff 100%); }
.status-header { display: flex; align-items: center; gap: 1.5rem; }
.status-icon { font-size: 3rem; display: flex; align-items: center; justify-content: center; }
.status-card.disconnected .status-icon { color: #ef4444; }
.status-card.connecting .status-icon { color: #f59e0b; }
.status-card.connected .status-icon { color: #10b981; }
.status-card.error .status-icon { color: #ef4444; }
.status-info { flex: 1; }
.status-info h3 { margin: 0 0 0.5rem 0; font-size: 1.5rem; font-weight: 600; color: #1f2937; }
.status-info p { margin: 0; color: #6b7280; font-size: 1rem; line-height: 1.4; }
.status-actions { display: flex; gap: 1rem; }
button.btn { padding: 0.75rem 1.5rem; border: none; border-radius: 0.5rem; cursor: pointer; font-weight: 500; transition: all 0.2s ease; display: inline-flex; align-items: center; justify-content: center; gap: 0.5rem; }
button.btn-primary { background: #3b82f6; color: white; }
button.btn-primary:hover:not(:disabled) { background: #2563eb; }
button.btn-secondary { background: #6b7280; color: white; }
button.btn-secondary:hover { background: #4b5563; }
button[disabled] { opacity: 0.5; cursor: not-allowed; }
.error-details { margin-top: 1.5rem; padding-top: 1.5rem; border-top: 1px solid #f3f4f6; }
.error-details h4 { color: #dc2626; margin: 0 0 0.5rem 0; }
.error-details p { color: #6b7280; margin: 0; }
</style>
