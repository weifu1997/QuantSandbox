import { createRouter, createWebHistory } from 'vue-router';

const routes = [
  { path: '/', component: () => import('../views/Dashboard.vue') },
  { path: '/config', component: () => import('../views/ConfigManager.vue') },
  { path: '/mx', component: () => import('../views/MxHub.vue'), props: { initialTab: 'search' } },
  { path: '/stock/:ticker', component: () => import('../views/Detail.vue'), props: true },

  // 工作流相关路由
  { path: '/workflow', component: () => import('../views/WorkflowRun.vue') },
  { path: '/workflow/history', component: () => import('../views/WorkflowHistory.vue') },
  { path: '/workflow/:runId', component: () => import('../views/WorkflowDetail.vue'), props: true },
  { path: '/watchlist', component: () => import('../views/Watchlist.vue') },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
