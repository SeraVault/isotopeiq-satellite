<template>
  <div>
    <h1>Job Monitor</h1>

    <!-- Filters -->
    <div class="card filter-bar">
      <label>
        Device
        <select v-model="filters.device" @change="applyFilters">
          <option value="">All</option>
          <option v-for="d in devices" :key="d.id" :value="d.id">{{ d.hostname }}</option>
        </select>
      </label>
      <label>
        Policy
        <select v-model="filters.policy" @change="applyFilters">
          <option value="">All</option>
          <option v-for="p in policies" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
      </label>
      <label>
        Script
        <select v-model="filters.script" @change="applyFilters">
          <option value="">All</option>
          <option v-for="s in scripts" :key="s.id" :value="s.id">{{ s.name }}</option>
        </select>
      </label>
      <label>
        Status
        <select v-model="filters.status" @change="applyFilters">
          <option value="">All</option>
          <option v-for="s in statuses" :key="s" :value="s">{{ s }}</option>
        </select>
      </label>
      <label>
        From
        <input type="datetime-local" v-model="filters.created_after" @change="applyFilters" />
      </label>
      <label>
        To
        <input type="datetime-local" v-model="filters.created_before" @change="applyFilters" />
      </label>
      <div class="filter-actions">
        <button @click="applyFilters" class="btn-primary">Refresh</button>
        <button @click="clearFilters">Clear</button>
      </div>
    </div>

    <div v-if="store.loading" class="text-muted" style="padding:1rem 0">Loading…</div>
    <table v-else-if="store.jobs.length">
      <thead>
        <tr>
          <th>#</th>
          <th>Policy</th>
          <th>Triggered By</th>
          <th>Status</th>
          <th>Started</th>
          <th>Duration</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="job in store.jobs" :key="job.id">
          <td class="text-muted">{{ job.id }}</td>
          <td>{{ job.policy_name ?? job.policy ?? '—' }}</td>
          <td>{{ job.triggered_by }}</td>
          <td><span :class="`badge badge-${job.status}`">{{ job.status }}</span></td>
          <td>{{ job.started_at ? fmt(job.started_at) : '—' }}</td>
          <td>{{ duration(job) }}</td>
          <td>
            <button @click="openDetail(job)">Details</button>
            <button
              v-if="job.status === 'running' || job.status === 'pending'"
              class="btn-danger"
              @click="cancel(job)"
            >Cancel</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else class="text-muted">No jobs found.</p>

    <!-- Job detail modal -->
    <div v-if="selected" class="modal">
      <div class="modal-box modal-lg">

        <!-- Header -->
        <div class="detail-header">
          <div>
            <h2 style="margin:0">Job #{{ selected.id }}</h2>
            <p class="text-muted" style="margin:.2rem 0 0">
              {{ selected.policy_name ?? (selected.policy ? `Policy ${selected.policy}` : 'Push job') }}
              &middot; triggered by <strong>{{ selected.triggered_by }}</strong>
              &middot; {{ selected.started_at ? fmt(selected.started_at) : '—' }}
            </p>
          </div>
          <div style="display:flex;align-items:center;gap:.75rem">
            <span :class="`badge badge-${selected.status}`" style="font-size:.9rem;padding:.25rem .7rem">{{ selected.status }}</span>
            <button @click="selected = null">✕ Close</button>
          </div>
        </div>

        <!-- Device results -->
        <div
          v-for="result in selected.device_results"
          :key="result.id"
          class="device-result"
          :class="`device-result--${result.status}`"
        >
          <div class="device-result-header">
            <span class="device-result-name">{{ result.device_name ?? `Device ${result.device}` }}</span>
            <span :class="`badge badge-${result.status}`">{{ result.status }}</span>
            <span class="text-muted" style="margin-left:auto;font-size:.8rem">
              {{ result.started_at ? fmt(result.started_at) : '' }}
              {{ result.finished_at ? '→ ' + fmt(result.finished_at) : '' }}
            </span>
          </div>

          <div v-if="result.error_message" class="result-error">
            {{ result.error_message }}
          </div>

          <div class="result-accordions">
            <details>
              <summary>Raw Output</summary>
              <pre>{{ result.raw_output || '(empty)' }}</pre>
            </details>
            <details>
              <summary>Parsed Output</summary>
              <pre>{{ result.parsed_output ? JSON.stringify(result.parsed_output, null, 2) : '(none)' }}</pre>
            </details>
            <details v-if="result.drift_event" open>
              <summary>
                Drift Detected
                <span :class="`badge badge-${result.drift_event.status}`" style="margin-left:.5rem">{{ result.drift_event.status }}</span>
              </summary>
              <pre>{{ JSON.stringify(result.drift_event.diff, null, 2) }}</pre>
            </details>
            <p v-else-if="result.status === 'success'" class="no-drift">✓ No drift detected</p>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { useJobsStore } from '../stores/jobs'
import api from '../api'

const store = useJobsStore()
const selected = ref(null)

const devices = ref([])
const policies = ref([])
const scripts = ref([])
const statuses = ['pending', 'running', 'success', 'partial', 'failed', 'cancelled']

const filters = reactive({
  device: '', policy: '', script: '', status: '',
  created_after: '', created_before: '',
})

function buildParams() {
  const p = {}
  if (filters.device)         p.device         = filters.device
  if (filters.policy)         p.policy         = filters.policy
  if (filters.script)         p.script         = filters.script
  if (filters.status)         p.status         = filters.status
  if (filters.created_after)  p.created_after  = new Date(filters.created_after).toISOString()
  if (filters.created_before) p.created_before = new Date(filters.created_before).toISOString()
  return p
}

function applyFilters() { store.fetchJobs(buildParams()) }
function clearFilters() {
  Object.assign(filters, { device: '', policy: '', script: '', status: '', created_after: '', created_before: '' })
  store.fetchJobs()
}

function fmt(iso) { return new Date(iso).toLocaleString() }

function duration(job) {
  if (!job.started_at || !job.finished_at) return '—'
  const ms = new Date(job.finished_at) - new Date(job.started_at)
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`
}

async function openDetail(job) {
  const { data } = await api.get(`/jobs/${job.id}/`)
  selected.value = data
}

async function cancel(job) {
  if (!confirm(`Cancel job ${job.id}?`)) return
  await api.post(`/jobs/${job.id}/cancel/`)
  applyFilters()
  if (selected.value?.id === job.id) selected.value = null
}

onMounted(async () => {
  const [dRes, pRes, sRes] = await Promise.all([
    api.get('/devices/'),
    api.get('/policies/'),
    api.get('/scripts/'),
  ])
  devices.value  = dRes.data.results  ?? dRes.data
  policies.value = pRes.data.results  ?? pRes.data
  scripts.value  = sRes.data.results  ?? sRes.data
  store.fetchJobs()
  store.connectWebSocket()
})
onUnmounted(() => store.disconnectWebSocket())
</script>

<style scoped>
/* Filter bar */
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: .75rem;
  align-items: flex-end;
  margin-bottom: 1.25rem;
  padding: 1rem 1.25rem;
}
.filter-bar label {
  display: flex;
  flex-direction: column;
  font-size: .8rem;
  font-weight: 600;
  color: #555;
  gap: .25rem;
  margin: 0;
}
.filter-bar select,
.filter-bar input {
  padding: .35rem .6rem;
  border: 1px solid #d0d0d0;
  border-radius: 5px;
  font-size: .875rem;
  background: #fff;
  min-width: 130px;
  margin: 0;
}
.filter-actions {
  display: flex;
  gap: .4rem;
  align-items: flex-end;
  padding-bottom: 1px;
}

/* Detail modal header */
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  margin-bottom: 1.25rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #eee;
}

/* Device result blocks */
.device-result {
  border: 1px solid #e8e8e8;
  border-radius: 8px;
  margin-bottom: .75rem;
  overflow: hidden;
}
.device-result--success { border-left: 4px solid #28a745; }
.device-result--failed  { border-left: 4px solid #dc3545; }
.device-result--running { border-left: 4px solid #17a2b8; }
.device-result--partial { border-left: 4px solid #ffc107; }

.device-result-header {
  display: flex;
  align-items: center;
  gap: .6rem;
  padding: .6rem 1rem;
  background: #fafafa;
  border-bottom: 1px solid #f0f0f0;
}
.device-result-name {
  font-weight: 600;
  font-size: .9rem;
}

.result-error {
  margin: .6rem 1rem;
  padding: .55rem .75rem;
  background: #fff5f5;
  border: 1px solid #fcc;
  border-radius: 5px;
  color: #c00;
  font-size: .85rem;
}

.result-accordions {
  padding: .5rem 1rem .75rem;
}
.result-accordions details {
  margin-top: .4rem;
}
.result-accordions summary {
  cursor: pointer;
  font-size: .85rem;
  font-weight: 600;
  color: #445;
  padding: .3rem .1rem;
  user-select: none;
}
.result-accordions summary:hover { color: #4fc3f7; }
.result-accordions pre {
  margin-top: .4rem;
}

.no-drift {
  margin-top: .5rem;
  font-size: .83rem;
  color: #28a745;
  font-weight: 500;
}
</style>
