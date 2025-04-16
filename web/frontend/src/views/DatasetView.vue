<template>
  <div class="dataset-view">
    <h1>Dataset Management</h1>
    
    <div class="card mb-4">
      <div class="card-header d-flex justify-content-between align-items-center">
        <h5 class="card-title mb-0">Available Datasets</h5>
        <button class="btn btn-primary btn-sm">
          <i class="bi bi-plus"></i> New Dataset
        </button>
      </div>
      <div class="card-body">
        <div class="alert alert-info" v-if="!datasets.length">
          No datasets available. Create a new dataset to get started.
        </div>
        
        <table class="table" v-else>
          <thead>
            <tr>
              <th>Name</th>
              <th>Type</th>
              <th>Created</th>
              <th>Size</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(dataset, index) in datasets" :key="index">
              <td>{{ dataset.name }}</td>
              <td>{{ dataset.type }}</td>
              <td>{{ dataset.created }}</td>
              <td>{{ dataset.size }}</td>
              <td>
                <div class="btn-group btn-group-sm">
                  <button class="btn btn-outline-primary">
                    <i class="bi bi-eye"></i>
                  </button>
                  <button class="btn btn-outline-secondary">
                    <i class="bi bi-pencil"></i>
                  </button>
                  <button class="btn btn-outline-danger">
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
            <h5 class="card-title mb-0">Dataset Statistics</h5>
          </div>
          <div class="card-body">
            <p>Total Datasets: {{ datasets.length }}</p>
            <p>Total Storage Used: {{ totalStorageUsed }}</p>
            <p>Most Recent Dataset: {{ mostRecentDataset }}</p>
          </div>
        </div>
      </div>
      
      <div class="col-md-6 mb-4">
        <div class="card">
          <div class="card-header">
            <h5 class="card-title mb-0">Dataset Operations</h5>
          </div>
          <div class="card-body">
            <div class="d-grid gap-2">
              <button class="btn btn-outline-primary mb-2">Import Dataset</button>
              <button class="btn btn-outline-secondary mb-2">Export Selected</button>
              <button class="btn btn-outline-danger">Clean Old Datasets</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'DatasetView',
  data() {
    return {
      datasets: [
        // Sample data - replace with real API data
        { 
          name: 'Training Set 1', 
          type: 'Demonstrations', 
          created: '2023-04-15', 
          size: '2.3 GB'
        },
        { 
          name: 'Validation Data', 
          type: 'Evaluation', 
          created: '2023-04-10', 
          size: '450 MB'
        }
      ]
    }
  },
  computed: {
    totalStorageUsed() {
      // Implement actual calculation based on your data
      return '2.75 GB';
    },
    mostRecentDataset() {
      // Implement actual logic
      return this.datasets.length ? this.datasets[0].name : 'None';
    }
  },
  mounted() {
    // Here you would typically load datasets from your API
    // this.loadDatasets();
  },
  methods: {
    loadDatasets() {
      // Implementation for loading datasets from API
      // Example: 
      // api.getDatasets().then(response => {
      //   this.datasets = response.data;
      // });
    }
  }
}
</script>

<style scoped>
.dataset-view {
  max-width: 100%;
  width: 100%;
}

h1 {
  margin-bottom: 2rem;
}
</style>