<template>
  <div class="policy-view">
    <h1>Policy Management</h1>
    
    <div class="card mb-4">
      <div class="card-header d-flex justify-content-between align-items-center">
        <h5 class="card-title mb-0">Available Policies</h5>
        <button class="btn btn-primary btn-sm">
          <i class="bi bi-plus"></i> New Policy
        </button>
      </div>
      <div class="card-body">
        <div class="alert alert-info" v-if="!policies.length">
          No policies available. Train or import a policy to get started.
        </div>
        
        <table class="table" v-else>
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Trained On</th>
              <th>Performance</th>
              <th>Status</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(policy, index) in policies" :key="index">
              <td>{{ policy.name }}</td>
              <td>{{ policy.type }}</td>
              <td>{{ policy.trainedOn }}</td>
              <td>
                <div class="progress">
                  <div class="progress-bar" role="progressbar" 
                       :style="`width: ${policy.performance}%`" 
                       :aria-valuenow="policy.performance" 
                       aria-valuemin="0" aria-valuemax="100">
                    {{ policy.performance }}%
                  </div>
                </div>
              </td>
              <td>
                <span :class="getStatusBadgeClass(policy.status)">
                  {{ policy.status }}
                </span>
              </td>
              <td>
                <div class="btn-group btn-group-sm">
                  <button class="btn btn-outline-primary" title="Deploy">
                    <i class="bi bi-play-fill"></i>
                  </button>
                  <button class="btn btn-outline-info" title="View Details">
                    <i class="bi bi-info-circle"></i>
                  </button>
                  <button class="btn btn-outline-danger" title="Delete">
                    <i class="bi bi-trash"></i>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
    
    <div class="row">
      <div class="col-md-6 mb-4">
        <div class="card">
          <div class="card-header">
            <h5 class="card-title mb-0">Training</h5>
          </div>
          <div class="card-body">
            <form>
              <div class="mb-3">
                <label for="policyName" class="form-label">Policy Name</label>
                <input type="text" class="form-control" id="policyName" placeholder="Enter policy name">
              </div>
              
              <div class="mb-3">
                <label for="policyType" class="form-label">Policy Type</label>
                <select class="form-select" id="policyType">
                  <option value="">Select a type</option>
                  <option value="bc">Behavior Cloning</option>
                  <option value="rl">Reinforcement Learning</option>
                  <option value="hybrid">Hybrid Approach</option>
                </select>
              </div>
              
              <div class="mb-3">
                <label for="trainingDataset" class="form-label">Training Dataset</label>
                <select class="form-select" id="trainingDataset">
                  <option value="">Select a dataset</option>
                  <option value="demo1">Training Set 1</option>
                  <option value="demo2">Validation Data</option>
                </select>
              </div>
              
              <div class="d-grid">
                <button type="button" class="btn btn-primary">
                  <i class="bi bi-gear"></i> Start Training
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
      
      <div class="col-md-6">
        <div class="card mb-4">
          <div class="card-header">
            <h5 class="card-title mb-0">Import/Export</h5>
          </div>
          <div class="card-body">
            <div class="d-grid gap-2">
              <button class="btn btn-outline-primary mb-2">
                <i class="bi bi-upload"></i> Import Policy
              </button>
              <button class="btn btn-outline-secondary" :disabled="!selectedPolicy">
                <i class="bi bi-download"></i> Export Selected Policy
              </button>
            </div>
          </div>
        </div>
        
        <div class="card">
          <div class="card-header">
            <h5 class="card-title mb-0">Evaluation</h5>
          </div>
          <div class="card-body">
            <div class="alert alert-secondary">
              Select a policy to run evaluation tests and measure performance.
            </div>
            
            <div class="d-grid">
              <button class="btn btn-info" :disabled="!selectedPolicy">
                <i class="bi bi-clipboard-data"></i> Run Evaluation
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'PolicyView',
  data() {
    return {
      policies: [
        { 
          name: 'Pick and Place Policy', 
          type: 'Behavior Cloning', 
          trainedOn: '2023-04-15', 
          performance: 85,
          status: 'Ready'
        },
        { 
          name: 'Drawer Opening', 
          type: 'Reinforcement Learning', 
          trainedOn: '2023-04-10', 
          performance: 72,
          status: 'Training'
        },
        { 
          name: 'Cup Grasping', 
          type: 'Hybrid', 
          trainedOn: '2023-03-22', 
          performance: 91,
          status: 'Ready'
        }
      ],
      selectedPolicy: null
    }
  },
  methods: {
    getStatusBadgeClass(status) {
      switch(status) {
        case 'Ready':
          return 'badge bg-success';
        case 'Training':
          return 'badge bg-warning text-dark';
        case 'Failed':
          return 'badge bg-danger';
        default:
          return 'badge bg-secondary';
      }
    },
    loadPolicies() {
      // Implementation for loading policies from API
      // Example: 
      // api.getPolicies().then(response => {
      //   this.policies = response.data;
      // });
    }
  },
  mounted() {
    // Here you would typically load policies from your API
    // this.loadPolicies();
  }
}
</script>

<style scoped>
.policy-view {
  max-width: 100%;
  width: 100%;
}

h1 {
  margin-bottom: 2rem;
}

.badge {
  font-size: 0.8rem;
  padding: 0.35em 0.65em;
}

.progress {
  height: 0.8rem;
}
</style>