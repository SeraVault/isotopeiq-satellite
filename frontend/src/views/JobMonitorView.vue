<template>
  <div>
    <h1>Job Monitor</h1>

    <!-- Filters — SRD §15.4: Device, Policy, Script, Status, Date -->
    <div style="display:flex;flex-wrap:wrap;gap:.75rem;margin-bottom:1rem;align-items:flex-end">
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
      <button @click="clearFilters">Clear</button>
      <button @click="applyFilters">Refresh</button>
    </div>

    <div v-if="store.loading">Loading…</div>
    <table v-else>
      <thead>
        <tr><th>ID</th><th>Policy</th><th>Triggered By</th><th>Status</th><th>Started</th><th>Finished</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="job in store.jobs" :key="job.id">
          <td>{{ job.id }}</td>
          <td>{{ job.policy ?? '—' }}</td>
          <td>{{ job.triggered_by }}</td>
          <td><span :class="`badge badge-${job.status}`">{{ job.status }}</span></td>
          <td>{{ job.started_at ? fmt(job.started_at) : '—' }}</td>
          <td>{{ job.finished_at ? fmt(job.finished_at) : '—' }}</td>
          <td>
            <button @click="selected = job">Details</button>
            <button
              v-if="job.status === 'running' || job.status === 'pending'"
              @click="cancel(job)"
              style="color:#c00;border-color:#c00"
            >Cancel</button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Job detail modal -->
    <div v-if="selected" class="modal">
      <div class="modal-box modal-lg">
        <h2>Job {{ selected.id }} — <span :class="`badge badge-${selected.status}`">{{ selected.status }}</span></h2>
        <p style="color:#666;margin:.25rem 0 1rem">{{ selected.policy ? `Policy ${selected.policy}` : 'Push job' }} &middot; {{ selected.triggered_by }}</p>

        <div
          v-for="result in selected.device_results"
          :key="result.id"
          style="margin-top:1rem;border:1px solid #eee;border-radius:6px;padding:1rem"
        >
          <strong>Device {{ result.device }}</strong>
          <span :class="`badge badge-${result.status}`" style="margin-left:.5rem">{{ result.status }}</span>

          <p v-if="result.error_message" class="error" style="margin-top:.5rem">{{ result.error_message }}</p>

          <details style="margin-top:.5rem"><summary>Raw Output</summary><pre>{{ result.raw_output || '(empty)' }}</pre></details>
          <details style="margin-top:.5rem"><summary>Parsed Output</summary><pre>{{ JSON.stringify(result.parsed_output, null, 2) || '(none)' }}</pre></details>

          <!-- Drift results — SRD §15.4 -->
          <details v-if="result.drift_event" style="margin-top:.5rem" open>
            <summary>
              Drift Detected
              <span :class="`badge badge-${result.drift_event.status}`" style="margin-left:.4rem">{{ result.drift_event.status }}</span>
            </summary>
            <pre>{{ JSON.stringify(result.drift_event.diff, null, 2) }}</pre>
          </details>
          <p v-else-if="result.status === 'success'" style="margin-top:.5rem;color:#555;font-size:.85rem">No drift detected.</p>
        </div>

        <div style="margin-top:1rem">
          <button @click="selected = null">Close</button>
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
  device: '',
  policy: '',
  script: '',
  status: '',
  created_after: '',
  created_before: '',
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

function applyFilters() {
  store.fetchJobs(buildParams())
}

function clearFilters() {
  Object.assign(filters, { device: '', policy: '', script: '', status: '', created_after: '', created_before: '' })
  store.fetchJobs()
}

function fmt(iso) { return new Date(iso).toLocaleString() }

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
