import { createRouter, createWebHistory } from 'vue-router';
import Dashboard from '../views/Dashboard.vue';
import Detail from '../views/Detail.vue';
import ConfigManager from '../views/ConfigManager.vue';
import MxHub from '../views/MxHub.vue';

const routes = [
  { path: '/', component: Dashboard },
  { path: '/config', component: ConfigManager },
  { path: '/mx', component: MxHub, props: { initialTab: 'search' } },
  { path: '/stock/:ticker', component: Detail, props: true },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;