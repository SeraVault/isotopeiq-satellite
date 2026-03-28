<template>
  <div>
    <h1>Dashboard</h1>

    <!-- Stat cards -->
    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-value">{{ stats.devices }}</div>
        <div class="stat-label">Devices</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{{ stats.policies }}</div>
        <div class="stat-label">Policies</div>
      </div>
      <div class="stat-card" :class="{ 'stat-card-alert': stats.running_jobs > 0 }">
        <div class="stat-value">{{ stats.running_jobs }}</div>
        <div class="stat-label">Running Jobs</div>
      </div>
      <div class="stat-card" :class="{ 'stat-card-alert': stats.new_drift > 0 }">
        <div class="stat-value">{{ stats.new_drift }}</div>
        <div class="stat-label">Unresolved Drift</div>
      </div>
    </div>

    <div class="dashboard-grid">
      <!-- Active drift alerts -->
      <div class="card">
        <div class="section-header">
          <h2>Drift Alerts</h2>
          <router-link to="/drift" class="view-all">View all →</router-link>
        </div>
        <div v-if="loadingDrift" class="text-muted">Loading…</div>
        <div v-else-if="driftEvents.length === 0" class="text-muted empty-state">No unresolved drift detected.</div>
        <table v-else>
          <thead>
            <tr><th>Device</th><th>Status</th><th>Detected</th><th>Changed Keys</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="e in driftEvents" :key="e.id">
              <td>{{ e.device_name ?? e.device }}</td>
              <td><span :class="`badge badge-${e.status}`">{{ e.status }}</span></td>
              <td class="text-muted">{{ fmt(e.detected_at) }}</td>
              <td class="text-muted">{{ diffKeys(e.diff) }}</td>
              <td>
                <button v-if="e.status === 'new'" @click="openAcknowledge(e)">Acknowledge</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Recent jobs -->
      <div class="card">
        <div class="section-header">
          <h2>Recent Jobs</h2>
          <router-link to="/jobs" class="view-all">View all →</router-link>
        </div>
        <div v-if="loadingJobs" class="text-muted">Loading…</div>
        <div v-else-if="recentJobs.length === 0" class="text-muted empty-state">No recent jobs.</div>
        <table v-else>
          <thead>
            <tr><th>ID</th><th>Policy</th><th>Status</th><th>Started</th></tr>
          </thead>
          <tbody>
            <tr v-for="j in recentJobs" :key="j.id">
              <td>#{{ j.id }}</td>
              <td>{{ j.policy ?? '—' }}</td>
              <td><span :class="`badge badge-${j.status}`">{{ j.status }}</span></td>
              <td class="text-muted">{{ j.started_at ? fmt(j.started_at) : '—' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- Acknowledge modal -->
  <div v-if="acknowledging" class="modal">
    <div class="modal-box modal-sm">
      <h2>Acknowledge Drift</h2>
      <p class="text-muted" style="margin:.25rem 0 .75rem">Device: <strong>{{ acknowledging.device_name ?? acknowledging.device }}</strong></p>
      <label>
        Reason <span style="color:#c00">*</span>
        <textarea
          v-model="ackReason"
          rows="4"
          placeholder="Explain why this drift is expected or acceptable…"
          style="width:100%;margin-top:.35rem;resize:vertical"
        ></textarea>
      </label>
      <p v-if="ackError" class="error" style="margin-top:.4rem">{{ ackError }}</p>
      <div style="margin-top:1rem;display:flex;gap:.5rem">
        <button class="btn-primary" :disabled="ackSaving" @click="submitAcknowledge">
          {{ ackSaving ? 'Saving…' : 'Acknowledge' }}
        </button>
        <button @click="acknowledging = null; ackReason = ''; ackError = ''">Cancel</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const stats = ref({ devices: 0, policies: 0, running_jobs: 0, new_drift: 0 })
const driftEvents = ref([])
const recentJobs = ref([])
const loadingDrift = ref(true)
const loadingJobs = ref(true)

const acknowledging = ref(null)
const ackReason = ref('')
const ackError = ref('')
const ackSaving = ref(false)

function fmt(iso) { return new Date(iso).toLocaleString() }

function diffKeys(diff) {
  if (!diff) return '—'
  const keys = Object.keys(diff)
  if (keys.length === 0) return '—'
  return keys.slice(0, 3).join(', ') + (keys.length > 3 ? ` +${keys.length - 3}` : '')
}

function openAcknowledge(event) {
  acknowledging.value = event
  ackReason.value = ''
  ackError.value = ''
}

async function submitAcknowledge() {
  if (!ackReason.value.trim()) {
    ackError.value = 'A reason is required.'
    return
  }
  ackSaving.value = true
  ackError.value = ''
  try {
    await api.post(`/drift/${acknowledging.value.id}/acknowledge/`, { reason: ackReason.value.trim() })
    acknowledging.value.status = 'acknowledged'
    stats.value.new_drift = Math.max(0, stats.value.new_drift - 1)
    acknowledging.value = null
    ackReason.value = ''
  } catch (e) {
    ackError.value = e.response?.data?.error ?? 'Failed to acknowledge.'
  } finally {
    ackSaving.value = false
  }
}

onMounted(async () => {
  const [devRes, polRes, jobsAllRes, driftRes, jobsRecentRes] = await Promise.all([
    api.get('/devices/'),
    api.get('/policies/'),
    api.get('/jobs/', { params: { status: 'running' } }),
    api.get('/drift/', { params: { status: 'new' } }),
    api.get('/jobs/'),
  ])

  const devices  = devRes.data.results  ?? devRes.data
  const policies = polRes.data.results  ?? polRes.data
  const running  = jobsAllRes.data.results ?? jobsAllRes.data
  const drift    = driftRes.data.results ?? driftRes.data
  const recent   = jobsRecentRes.data.results ?? jobsRecentRes.data

  stats.value = {
    devices:      Array.isArray(devices)  ? devices.length  : 0,
    policies:     Array.isArray(policies) ? policies.length : 0,
    running_jobs: Array.isArray(running)  ? running.length  : 0,
    new_drift:    Array.isArray(drift)    ? drift.length    : 0,
  }

  driftEvents.value = Array.isArray(drift) ? drift : []
  recentJobs.value  = Array.isArray(recent) ? recent.slice(0, 10) : []
  loadingDrift.value = false
  loadingJobs.value  = false
})
</script>

<style scoped>
.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1rem;
  margin-bottom: 1.5rem;
}
.stat-card {
  background: #fff;
  border-radius: 8px;
  padding: 1.25rem 1.5rem;
  box-shadow: 0 1px 3px rgba(0,0,0,.08);
  border-left: 4px solid #4fc3f7;
}
.stat-card-alert { border-left-color: #fc8181; }
.stat-value { font-size: 2rem; font-weight: 700; line-height: 1; }
.stat-label { font-size: .85rem; color: #666; margin-top: .35rem; }
.dashboard-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.25rem;
}
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: .85rem;
}
.section-header h2 { margin: 0; }
.view-all { font-size: .85rem; color: #4fc3f7; text-decoration: none; }
.view-all:hover { text-decoration: underline; }
.empty-state { padding: 1.5rem 0; text-align: center; }
</style>
