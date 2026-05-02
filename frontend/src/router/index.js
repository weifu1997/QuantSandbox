import { createRouter, createWebHistory } from 'vue-router';

const routes = [
  { path: '/', component: () => import('../views/Dashboard.vue') },
  { path: '/config', component: () => import('../views/ConfigManager.vue') },
  { path: '/mx', component: () => import('../views/MxHub.vue'), props: { initialTab: 'search' } },
  { path: '/stock/:ticker', component: () => import('../views/Detail.vue'), props: true },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;