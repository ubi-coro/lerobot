<template>
  <div class="control-view container-fluid py-4">
    <h1 class="mb-4">LeRobot Control</h1>
    
    <div class="row">
      <!-- Left sidebar for controls -->
      <div class="col-md-4">
        <div class="mb-4">
          <h2 class="h5 mb-3">Robot Connection</h2>
          <RobotConnection />
        </div>
        
        <div class="mb-4">
          <h2 class="h5 mb-3">Teleoperation</h2>
          <TeleoperationPanel />
        </div>
      </div>
      
      <!-- Right side for camera feeds -->
      <div class="col-md-8">
        <h2 class="h5 mb-3">Camera Feeds</h2>
        <CameraViewer />
      </div>
    </div>
  </div>
</template>

<script setup>
import RobotConnection from '@/components/robot/RobotConnection.vue';
import TeleoperationPanel from '@/components/robot/TeleoperationPanel.vue';
import CameraViewer from '@/components/robot/CameraViewer.vue';
</script>
```