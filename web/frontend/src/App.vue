<template>
  <div class="app">
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
      <div class="container-fluid">
        <router-link class="navbar-brand" to="/">LeRobot Interface</router-link>
        
        <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
          <span class="navbar-toggler-icon"></span>
        </button>
        
        <div class="collapse navbar-collapse" id="navbarNav">
          <ul class="navbar-nav">
            <li class="nav-item">
              <router-link class="nav-link" to="/">Home</router-link>
            </li>
            <li class="nav-item">
              <router-link class="nav-link" to="/control">Control</router-link>
            </li>
            <li class="nav-item">
              <router-link class="nav-link" to="/datasets">Datasets</router-link>
            </li>
            <li class="nav-item">
              <router-link class="nav-link" to="/policies">Policies</router-link>
            </li>
          </ul>
        </div>
      </div>
    </nav>
    
    <main>
      <router-view />
    </main>
  </div>
</template>

<style>
.app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

main {
  flex: 1;
}
</style>