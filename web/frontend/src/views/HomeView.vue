<template>
  <div class="home">
    <div class="dashboard-header mb-4">
      <h1 class="display-6">Welcome to LeRobot Interface</h1>
      <p class="lead text-muted">Control and monitor your robot from one centralized dashboard</p>
    </div>
    
    <div class="dashboard-content">
      <!-- Status cards row -->
      <div class="row g-3 mb-4">
        <div class="col-sm-6 col-lg-3">
          <div class="card status-card h-100">
            <div class="card-body d-flex align-items-center">
              <div :class="['status-indicator', robotStore.status.connected ? 'connected' : 'disconnected']">
                <i class="bi" :class="robotStore.status.connected ? 'bi-check-circle-fill' : 'bi-x-circle-fill'"></i>
              </div>
              <div class="ms-3">
                <h6 class="card-subtitle text-muted">Connection Status</h6>
                <h5 class="card-title mb-0">{{ robotStore.status.connected ? 'Connected' : 'Disconnected' }}</h5>
              </div>
            </div>
          </div>
        </div>
        
        <div class="col-sm-6 col-lg-3">
          <div class="card status-card h-100">
            <div class="card-body d-flex align-items-center">
              <div class="status-indicator mode">
                <i class="bi bi-gear-fill"></i>
              </div>
              <div class="ms-3">
                <h6 class="card-subtitle text-muted">Current Mode</h6>
                <h5 class="card-title mb-0">{{ robotStore.status.mode || 'Idle' }}</h5>
              </div>
            </div>
          </div>
        </div>
        
        <div class="col-sm-6 col-lg-3">
          <div class="card status-card h-100">
            <div class="card-body d-flex align-items-center">
              <div class="status-indicator cameras">
                <i class="bi bi-camera-video-fill"></i>
              </div>
              <div class="ms-3">
                <h6 class="card-subtitle text-muted">Available Cameras</h6>
                <h5 class="card-title mb-0">{{ robotStore.availableCameras.length || 0 }}</h5>
              </div>
            </div>
          </div>
        </div>
        
        <div class="col-sm-6 col-lg-3">
          <div class="card status-card h-100">
            <div class="card-body d-flex align-items-center">
              <div class="status-indicator arms">
                <i class="bi bi-robot"></i>
              </div>
              <div class="ms-3">
                <h6 class="card-subtitle text-muted">Available Arms</h6>
                <h5 class="card-title mb-0">{{ robotStore.status.available_arms.length || 0 }}</h5>
              </div>
            </div>
          </div>
        </div>
      </div>
      
      <!-- Main dashboard content -->
      <div class="row g-4">
        <!-- Left column -->
        <div class="col-lg-8">
          <div class="card mb-4">
            <div class="card-header d-flex justify-content-between align-items-center">
              <h5 class="card-title mb-0">System Overview</h5>
              <div class="btn-group btn-group-sm">
                <button type="button" class="btn btn-outline-secondary">Day</button>
                <button type="button" class="btn btn-outline-secondary active">Week</button>
                <button type="button" class="btn btn-outline-secondary">Month</button>
              </div>
            </div>
            <div class="card-body">
              <div class="alert alert-info">
                <i class="bi bi-info-circle me-2"></i>
                Robot system is operating normally. All components are functioning as expected.
              </div>
              
              <div class="system-metrics py-3">
                <div class="row text-center">
                  <div class="col-4">
                    <h2>4.2h</h2>
                    <p class="text-muted">Uptime</p>
                  </div>
                  <div class="col-4">
                    <h2>27</h2>
                    <p class="text-muted">Tasks Completed</p>
                  </div>
                  <div class="col-4">
                    <h2>98%</h2>
                    <p class="text-muted">Success Rate</p>
                  </div>
                </div>
              </div>
              
              <div class="chart-placeholder bg-light d-flex align-items-center justify-content-center" style="height: 240px;">
                <span class="text-muted">Performance chart will display here</span>
              </div>
            </div>
          </div>
          
          <div class="card">
            <div class="card-header">
              <h5 class="card-title mb-0">Recent Activity</h5>
            </div>
            <div class="card-body p-0">
              <ul class="list-group list-group-flush">
                <li class="list-group-item d-flex justify-content-between align-items-center">
                  <div>
                    <i class="bi bi-check-circle text-success me-2"></i>
                    <span>Robot connection established</span>
                    <small class="d-block text-muted">All systems nominal</small>
                  </div>
                  <small class="text-muted">2m ago</small>
                </li>
                <li class="list-group-item d-flex justify-content-between align-items-center">
                  <div>
                    <i class="bi bi-camera-video text-primary me-2"></i>
                    <span>Camera stream started</span>
                    <small class="d-block text-muted">Left arm camera at 30 FPS</small>
                  </div>
                  <small class="text-muted">5m ago</small>
                </li>
                <li class="list-group-item d-flex justify-content-between align-items-center">
                  <div>
                    <i class="bi bi-gear text-secondary me-2"></i>
                    <span>Teleoperation mode activated</span>
                    <small class="d-block text-muted">Manual control enabled</small>
                  </div>
                  <small class="text-muted">15m ago</small>
                </li>
                <li class="list-group-item d-flex justify-content-between align-items-center">
                  <div>
                    <i class="bi bi-database text-info me-2"></i>
                    <span>Dataset imported</span>
                    <small class="d-block text-muted">"Pick and Place v2" - 1.2GB</small>
                  </div>
                  <small class="text-muted">1h ago</small>
                </li>
              </ul>
            </div>
          </div>
        </div>
        
        <!-- Right column -->
        <div class="col-lg-4">
          <div class="card mb-4">
            <div class="card-header">
              <h5 class="card-title mb-0">Quick Actions</h5>
            </div>
            <div class="card-body">
              <div class="d-grid gap-3">
                <router-link to="/control" class="btn btn-primary">
                  <i class="bi bi-robot me-2"></i>Robot Control Center
                </router-link>
                <router-link to="/datasets" class="btn btn-outline-secondary">
                  <i class="bi bi-database me-2"></i>Manage Datasets
                </router-link>
                <router-link to="/policies" class="btn btn-outline-info">
                  <i class="bi bi-gear me-2"></i>Configure Policies
                </router-link>
                <button class="btn btn-outline-dark" :disabled="!robotStore.status.connected">
                  <i class="bi bi-camera-video me-2"></i>View All Camera Feeds
                </button>
              </div>
            </div>
          </div>
          
          <div class="card mb-4">
            <div class="card-header">
              <h5 class="card-title mb-0">Robot Health</h5>
            </div>
            <div class="card-body">
              <div class="mb-3">
                <label class="form-label d-flex justify-content-between">
                  <span>Battery Level</span>
                  <span>78%</span>
                </label>
                <div class="progress">
                  <div class="progress-bar bg-success" role="progressbar" style="width: 78%" aria-valuenow="78" aria-valuemin="0" aria-valuemax="100"></div>
                </div>
              </div>
              
              <div class="mb-3">
                <label class="form-label d-flex justify-content-between">
                  <span>CPU Usage</span>
                  <span>45%</span>
                </label>
                <div class="progress">
                  <div class="progress-bar bg-info" role="progressbar" style="width: 45%" aria-valuenow="45" aria-valuemin="0" aria-valuemax="100"></div>
                </div>
              </div>
              
              <div>
                <label class="form-label d-flex justify-content-between">
                  <span>Memory Usage</span>
                  <span>32%</span>
                </label>
                <div class="progress">
                  <div class="progress-bar bg-primary" role="progressbar" style="width: 32%" aria-valuenow="32" aria-valuemin="0" aria-valuemax="100"></div>
                </div>
              </div>
            </div>
          </div>
          
          <div class="card">
            <div class="card-body" v-if="!robotStore.status.connected">
              <div class="text-center py-3">
                <i class="bi bi-robot display-1 text-muted"></i>
                <h5 class="mt-3">Robot Disconnected</h5>
                <p class="text-muted mb-4">Connect to your robot to access all features</p>
                <router-link to="/control" class="btn btn-primary">
                  Connect Now
                </router-link>
              </div>
            </div>
            <div v-else>
              <div class="card-header">
                <h5 class="card-title mb-0">Connected Device</h5>
              </div>
              <div class="card-body">
                <h6>LeRobot Aloha</h6>
                <p class="text-muted small">Last calibrated: Today at 9:45 AM</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { useRobotStore } from '@/stores/robotStore';

export default {
  name: 'HomeView',
  setup() {
    const robotStore = useRobotStore();
    return { robotStore };
  }
}
</script>

<style scoped>

.home {
  width: 100%;
  /* Remove any width constraints that might be causing the small size */
}

.dashboard-content {
  width: 100%;
  max-width: 100%;
}

.row {
  /* Make sure rows take full width */
  margin-right: 0;
  margin-left: 0;
  width: 100%;
}

.dashboard-header {
  padding-bottom: 1rem;
  border-bottom: 1px solid #eee;
}

.status-indicator {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.status-indicator i {
  font-size: 1.5rem;
}

.status-indicator.connected {
  background-color: rgba(40, 167, 69, 0.1);
  color: #28a745;
}

.status-indicator.disconnected {
  background-color: rgba(220, 53, 69, 0.1);
  color: #dc3545;
}

.status-indicator.mode {
  background-color: rgba(108, 117, 125, 0.1);
  color: #6c757d;
}

.status-indicator.cameras {
  background-color: rgba(23, 162, 184, 0.1);
  color: #17a2b8;
}

.status-indicator.arms {
  background-color: rgba(0, 123, 255, 0.1);
  color: #007bff;
}

.card {
  width: 100%;
  border-radius: 0.5rem;
  transition: transform 0.2s, box-shadow 0.2s;
  border: 1px solid rgba(0,0,0,.125);
}

.card:hover {
  transform: translateY(-3px);
  box-shadow: 0 5px 15px rgba(0,0,0,0.1);
}

.status-card {
  overflow: hidden;
}

.system-metrics h2 {
  font-weight: 500;
  margin-bottom: 0.25rem;
}

.list-group-item {
  padding-left: 1rem;
  padding-right: 1rem;
}

body.dark-mode .chart-placeholder {
  background-color: rgba(255,255,255,0.05) !important;
}

/* Ensure responsiveness */
@media (max-width: 767px) {
  .dashboard-header h1 {
    font-size: 1.5rem;
  }
  
  .dashboard-header .lead {
    font-size: 1rem;
  }
}

@media (min-width: 1600px) {
  .dashboard-content {
  width: 100%;
  max-width: 100%; /* Changed from fixed values like 1800px */
}
}

/* Keep your existing styles below */
.dashboard-header {
  padding-bottom: 1rem;
  border-bottom: 1px solid #eee;
}

.status-indicator {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

</style>