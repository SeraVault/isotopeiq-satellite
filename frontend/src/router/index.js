import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import DashboardView from '../views/DashboardView.vue'
import DevicesView from '../views/DevicesView.vue'
import ScriptsView from '../views/ScriptsView.vue'
import ScriptEditorView from '../views/ScriptEditorView.vue'
import PoliciesView from '../views/PoliciesView.vue'
import JobMonitorView from '../views/JobMonitorView.vue'
import DriftView from '../views/DriftView.vue'
import BaselinesView from '../views/BaselinesView.vue'
import RetentionView from '../views/RetentionView.vue'
import AuditLogView from '../views/AuditLogView.vue'
import VolatileRulesView from '../views/VolatileRulesView.vue'
import SystemSettingsView from '../views/SystemSettingsView.vue'
import UsersView from '../views/UsersView.vue'
import AgentDownloadView from '../views/AgentDownloadView.vue'

const routes = [
  { path: '/login', component: LoginView, meta: { public: true } },
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', component: DashboardView },
  { path: '/devices', component: DevicesView },
  { path: '/agent-download', component: AgentDownloadView },
  { path: '/scripts', component: ScriptsView },
  { path: '/scripts/new', component: ScriptEditorView },
  { path: '/scripts/:id/edit', component: ScriptEditorView },
  { path: '/policies', component: PoliciesView },
  { path: '/jobs', component: JobMonitorView },
  { path: '/drift', component: DriftView },
  { path: '/volatile-rules', component: VolatileRulesView },
  { path: '/baselines', component: BaselinesView },
  { path: '/audit', component: AuditLogView },
  { path: '/retention', component: RetentionView },
  { path: '/system-settings', component: SystemSettingsView },
  { path: '/users', component: UsersView },
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
