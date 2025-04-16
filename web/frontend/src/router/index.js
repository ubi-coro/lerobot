import { createRouter, createWebHistory } from 'vue-router';
import HomeView from '../views/HomeView.vue';
import ControlView from '../views/ControlView.vue';

const routes = [
  {
    path: '/',
    name: 'home',
    component: HomeView
  },
  {
    path: '/control',
    name: 'control',
    component: ControlView
  },
  {
    path: '/datasets',
    name: 'datasets',
    // Lazy loading
    component: () => import('../views/DatasetView.vue')
  },
  {
    path: '/policies',
    name: 'policies',
    // Lazy loading
    component: () => import('../views/PolicyView.vue')
  }
];

const router = createRouter({
  history: createWebHistory('/'),
  routes
});

export default router;