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
            
            <!-- Safe Position Control -->
            <div class="mb-4">
              <h2 class="h5 mb-3">
                <i class="bi bi-shield-check me-2"></i>
                Safe Position Control
              </h2>
              <SafePositionControl />
            </div>
          </div>
          
          <!-- Center area for enhanced teleoperation -->
          <div class="col-lg-8">
            <div class="mb-4">
              <h2 class="h5 mb-3">
                <i class="bi bi-robot me-2"></i>
                Enhanced Teleoperation
              </h2>
              <EnhancedTeleoperationPanel />
            </div>
          </div>
        </div>
        
        <!-- Camera feeds section -->
        <div class="row mt-4">
          <div class="col-12">
            <h2 class="h5 mb-3">
              <i class="bi bi-camera-video me-2"></i>
              Camera Feeds
            </h2>
            <CameraViewer />
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
import RobotConnection from '@/components/robot/RobotConnection.vue';
import EnhancedTeleoperationPanel from '@/components/robot/EnhancedTeleoperationPanel.vue';
import SafePositionControl from '@/components/robot/SafePositionControl.vue';
import CameraViewer from '@/components/robot/CameraViewer.vue';
import TeleoperationDocs from '@/components/robot/TeleoperationDocs.vue';
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
```