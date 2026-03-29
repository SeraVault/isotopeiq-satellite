import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import DashboardView from '../views/DashboardView.vue'
import DevicesView from '../views/DevicesView.vue'
import ScriptsView from '../views/ScriptsView.vue'
import PoliciesView from '../views/PoliciesView.vue'
import JobMonitorView from '../views/JobMonitorView.vue'
import DriftView from '../views/DriftView.vue'
import BaselinesView from '../views/BaselinesView.vue'
import RetentionView from '../views/RetentionView.vue'
import AuditLogView from '../views/AuditLogView.vue'
import VolatileRulesView from '../views/VolatileRulesView.vue'

const routes = [
  { path: '/login', component: LoginView, meta: { public: true } },
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', component: DashboardView },
  { path: '/devices', component: DevicesView },
  { path: '/scripts', component: ScriptsView },
  { path: '/policies', component: PoliciesView },
  { path: '/jobs', component: JobMonitorView },
  { path: '/drift', component: DriftView },
  { path: '/volatile-rules', component: VolatileRulesView },
  { path: '/baselines', component: BaselinesView },
  { path: '/audit', component: AuditLogView },
  { path: '/retention', component: RetentionView },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const token = localStorage.getItem('access_token')
  if (!to.meta.public && !token) {
    return { path: '/login' }
  }
})

export default router
