<template>
  <div class="dataset-selector">
    <div class="modal-header">
      <h3><i class="bi bi-chart-bar me-2"></i>Select Dataset to Visualize</h3>
      <button @click="$emit('close')" class="btn-close">
        <i class="bi bi-x-lg"></i>
      </button>
    </div>

    <div class="selector-tabs">
      <button 
        :class="['tab-btn', { active: activeTab === 'repos' }]"
        @click="activeTab = 'repos'"
      >
        <i class="bi bi-cloud me-2"></i>HuggingFace Repos
      </button>
      <button 
        :class="['tab-btn', { active: activeTab === 'local' }]"
        @click="activeTab = 'local'"
      >
        <i class="bi bi-hdd me-2"></i>Local Datasets
      </button>
    </div>

    <!-- HuggingFace Repos Tab -->
    <div v-if="activeTab === 'repos'" class="tab-content">
      <div class="input-section">
        <label for="repoInput">Repository ID:</label>
        <div class="input-group">
          <input
            id="repoInput"
            v-model="repoInput"
            type="text"
            placeholder="e.g., lerobot/aloha_sim_insertion_human"
            class="form-control"
            @keyup.enter="validateRepo"
          />
          <button @click="validateRepo" class="btn btn-outline" :disabled="!repoInput.trim()">
            <i class="bi bi-search"></i>
          </button>
        </div>
        <small class="hint">Enter HuggingFace repository ID (username/dataset-name)</small>
      </div>

      <!-- Popular repos suggestions -->
      <div class="suggestions">
        <h5>Popular Datasets:</h5>
        <div class="repo-grid">
          <div 
            v-for="repo in popularRepos" 
            :key="repo.id"
            class="repo-card"
            @click="selectRepo(repo.id)"
          >
            <div class="repo-icon">{{ repo.icon }}</div>
            <div class="repo-info">
              <span class="repo-name">{{ repo.name }}</span>
              <span class="repo-id">{{ repo.id }}</span>
              <span class="repo-desc">{{ repo.description }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Local Datasets Tab -->
    <div v-if="activeTab === 'local'" class="tab-content">
      <div v-if="localDatasets.length === 0" class="no-datasets">
        <i class="bi bi-inbox"></i>
        <p>No local datasets found</p>
        <small>Record some data first or switch to HuggingFace repos</small>
      </div>
      
      <div v-else class="dataset-list">
        <div 
          v-for="dataset in localDatasets" 
          :key="dataset.id"
          class="dataset-item"
          @click="selectLocalDataset(dataset)"
        >
          <div class="dataset-icon">📊</div>
          <div class="dataset-info">
            <span class="dataset-name">{{ dataset.name }}</span>
            <span class="dataset-meta">{{ dataset.episodes }} episodes • {{ dataset.size }}</span>
            <span class="dataset-date">{{ formatDate(dataset.created) }}</span>
            <span class="dataset-path">{{ dataset.path }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Validation Result -->
    <div v-if="validationResult" class="validation-result" :class="validationResult.valid ? 'valid' : 'invalid'">
      <i :class="validationResult.valid ? 'bi bi-check-circle' : 'bi bi-exclamation-triangle'"></i>
      <span>{{ validationResult.message }}</span>
    </div>

    <!-- Action Buttons -->
    <div class="action-buttons">
      <button @click="$emit('close')" class="btn btn-secondary">
        Cancel
      </button>
      <button 
        @click="launchVisualizer('html')" 
        :disabled="!selectedRepo && !selectedDataset"
        class="btn btn-primary"
      >
        <i class="bi bi-window me-2"></i>HTML Visualizer
      </button>
      <button 
        @click="launchVisualizer('rerun')" 
        :disabled="!selectedRepo && !selectedDataset"
        class="btn btn-outline"
      >
        <i class="bi bi-box me-2"></i>3D Rerun
      </button>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import datasetApi from '@/services/api/datasetApi'

const emit = defineEmits(['close', 'launch'])

// State
const activeTab = ref('repos')
const repoInput = ref('')
const selectedRepo = ref('')
const selectedDataset = ref('')
const validationResult = ref(null)
const localDatasets = ref([])

// Popular repositories (can be fetched from API later)
const popularRepos = ref([
  {
    id: 'lerobot/aloha_sim_insertion_human',
    name: 'ALOHA Insertion',
    icon: '🤖',
    description: 'Human demonstrations for insertion tasks'
  },
  {
    id: 'lerobot/pusht',
    name: 'PushT',
    icon: '📦',
    description: 'Push task demonstrations'
  },
  {
    id: 'lerobot/aloha_sim_transfer_cube_human',
    name: 'ALOHA Transfer',
    icon: '🎯',
    description: 'Cube transfer demonstrations'
  },
  {
    id: 'lerobot/droid_100',
    name: 'DROID-100',
    icon: '🦾',
    description: 'Diverse robot interaction dataset'
  }
])

// Methods
const selectRepo = (repoId) => {
  repoInput.value = repoId
  selectedRepo.value = repoId
  selectedDataset.value = ''
  validationResult.value = null
}

const selectLocalDataset = (dataset) => {
  selectedDataset.value = dataset
  selectedRepo.value = ''
  validationResult.value = {
    valid: true,
    message: `✓ Local dataset: ${dataset.episodes} episodes, ${dataset.size}`
  }
}

const validateRepo = async () => {
  if (!repoInput.value.trim()) return
  
  try {
    validationResult.value = { valid: false, message: 'Validating repository...' }
    
    const response = await datasetApi.validateRepo(repoInput.value.trim())
    
    if (response.data.valid) {
      selectedRepo.value = repoInput.value.trim()
      validationResult.value = {
        valid: true,
        message: `✓ Repository found: ${response.data.info.episodes} episodes`
      }
    } else {
      validationResult.value = {
        valid: false,
        message: `Repository not found or inaccessible`
      }
    }
  } catch (error) {
    validationResult.value = {
      valid: false,
      message: `Error: ${error.message}`
    }
  }
}

const launchVisualizer = async (type) => {
  const target = selectedRepo.value || selectedDataset.value
  if (!target) return

  try {
    let response;
    
    if (selectedDataset.value) {
      // Local dataset - use local visualizer API
      response = await datasetApi.launchLocalDatasetVisualizer(
        selectedDataset.value.path,
        type,
        { 
          port: type === 'html' ? 9090 : 9087,
          episodeIndex: 0 
        }
      )
    } else {
      // HuggingFace repo - check if it should be local-files-only
      const isLocalRepo = selectedRepo.value.includes('/') && 
                         !selectedRepo.value.startsWith('lerobot/') &&
                         validationResult.value?.local_dataset
      
      if (type === 'html') {
        response = await datasetApi.launchHtmlVisualizer(selectedRepo.value, {
          localFilesOnly: isLocalRepo,
          port: 9090
        })
      } else {
        response = await datasetApi.launchRerunVisualizer(selectedRepo.value, {
          localFilesOnly: isLocalRepo,
          wsPort: 9087
        })
      }
    }

    // Open visualizer window after launch
    if (type === 'html') {
      setTimeout(() => {
        datasetApi.openVisualizerWindow('html', 9090)
      }, 1500) // Slightly longer delay for local datasets
    } else {
      // Show Rerun connection instructions
      const target_name = selectedDataset.value?.name || selectedRepo.value
      alert(`3D Visualizer started for "${target_name}"!\n\nTo view:\n1. Install Rerun: pip install rerun-sdk\n2. Run: rerun ws://localhost:9087\n\nThe visualizer is now streaming data.`)
    }

    emit('launch', { 
      type, 
      target: selectedDataset.value?.name || selectedRepo.value,
      isLocal: !!selectedDataset.value 
    })
    emit('close')
    
  } catch (error) {
    console.error('Failed to launch visualizer:', error)
    alert(`Failed to launch visualizer: ${error.message}`)
  }
}

const loadLocalDatasets = async () => {
  try {
    const response = await datasetApi.listLocalDatasets()
    localDatasets.value = response.data.datasets || []
  } catch (error) {
    console.error('Failed to load local datasets:', error)
    localDatasets.value = []
  }
}

const formatDate = (date) => {
  return new Date(date).toLocaleDateString()
}

// Lifecycle
onMounted(() => {
  loadLocalDatasets()
})
</script>

<style scoped>
.dataset-selector {
  background: white;
  border-radius: 1rem;
  padding: 1.5rem;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.15);
  max-width: 600px;
  max-height: 80vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #e5e7eb;
}

.modal-header h3 {
  margin: 0;
  color: #1f2937;
}

.btn-close {
  background: none;
  border: none;
  font-size: 1.2rem;
  color: #6b7280;
  cursor: pointer;
  padding: 0.5rem;
  border-radius: 0.5rem;
}

.btn-close:hover {
  background: #f3f4f6;
  color: #374151;
}

.selector-tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
  border-bottom: 1px solid #e5e7eb;
}

.tab-btn {
  background: none;
  border: none;
  padding: 0.75rem 1rem;
  cursor: pointer;
  border-radius: 0.5rem 0.5rem 0 0;
  color: #6b7280;
  border-bottom: 2px solid transparent;
}

.tab-btn.active {
  color: #3b82f6;
  border-bottom-color: #3b82f6;
  background: #eff6ff;
}

.tab-content {
  min-height: 300px;
}

.input-section {
  margin-bottom: 1.5rem;
}

.input-section label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: 500;
  color: #374151;
}

.input-group {
  display: flex;
  gap: 0.5rem;
}

.form-control {
  flex: 1;
  padding: 0.75rem;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
  font-size: 0.95rem;
}

.form-control:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.hint {
  color: #6b7280;
  font-size: 0.85rem;
  margin-top: 0.25rem;
  display: block;
}

.suggestions h5 {
  margin-bottom: 1rem;
  color: #374151;
}

.repo-grid {
  display: grid;
  gap: 0.75rem;
}

.repo-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  border: 1px solid #e5e7eb;
  border-radius: 0.75rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.repo-card:hover {
  border-color: #3b82f6;
  background: #eff6ff;
}

.repo-icon {
  font-size: 1.5rem;
}

.repo-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.repo-name {
  font-weight: 600;
  color: #1f2937;
}

.repo-id {
  font-size: 0.85rem;
  color: #3b82f6;
  font-family: monospace;
}

.repo-desc {
  font-size: 0.85rem;
  color: #6b7280;
}

.dataset-list {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.dataset-item {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  border: 1px solid #e5e7eb;
  border-radius: 0.75rem;
  cursor: pointer;
  transition: all 0.2s ease;
}

.dataset-item:hover {
  border-color: #10b981;
  background: #ecfdf5;
}

.dataset-icon {
  font-size: 1.5rem;
}

.dataset-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.dataset-name {
  font-weight: 600;
  color: #1f2937;
}

.dataset-meta {
  font-size: 0.85rem;
  color: #059669;
}

.dataset-date {
  font-size: 0.8rem;
  color: #6b7280;
}

.dataset-path {
  font-size: 0.75rem;
  color: #9ca3af;
  font-family: monospace;
  margin-top: 0.25rem;
}

.no-datasets {
  text-align: center;
  padding: 2rem;
  color: #6b7280;
}

.no-datasets i {
  font-size: 3rem;
  margin-bottom: 1rem;
  display: block;
}

.validation-result {
  padding: 0.75rem;
  border-radius: 0.5rem;
  margin: 1rem 0;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.validation-result.valid {
  background: #ecfdf5;
  color: #059669;
  border: 1px solid #a7f3d0;
}

.validation-result.invalid {
  background: #fef2f2;
  color: #dc2626;
  border: 1px solid #fecaca;
}

.action-buttons {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
  padding-top: 1.5rem;
  border-top: 1px solid #e5e7eb;
  margin-top: 1.5rem;
}

.btn {
  padding: 0.75rem 1.5rem;
  border-radius: 0.5rem;
  border: none;
  cursor: pointer;
  font-weight: 500;
  transition: all 0.2s ease;
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

.btn-outline {
  background: white;
  color: #3b82f6;
  border: 1px solid #3b82f6;
}

.btn-outline:hover:not(:disabled) {
  background: #3b82f6;
  color: white;
}
</style>
