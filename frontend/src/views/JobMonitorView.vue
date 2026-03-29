<template>
  <div>
    <div class="text-h5 font-weight-bold mb-5">Job Monitor</div>

    <!-- Filters -->
    <v-card rounded="lg" elevation="1" class="mb-5 pa-4">
      <v-row dense align="end">
        <v-col cols="12" sm="6" md="2">
          <v-select v-model="filters.device" label="Device" :items="deviceItems" item-title="title" item-value="value" clearable @update:model-value="applyFilters" />
        </v-col>
        <v-col cols="12" sm="6" md="2">
          <v-select v-model="filters.policy" label="Policy" :items="policyItems" item-title="title" item-value="value" clearable @update:model-value="applyFilters" />
        </v-col>
        <v-col cols="12" sm="6" md="2">
          <v-select v-model="filters.status" label="Status" :items="statuses" clearable @update:model-value="applyFilters" />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-text-field v-model="filters.created_after" label="From" type="datetime-local" @change="applyFilters" />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-text-field v-model="filters.created_before" label="To" type="datetime-local" @change="applyFilters" />
        </v-col>
        <v-col cols="12" sm="auto">
          <v-btn color="primary" class="mr-2" @click="applyFilters">Refresh</v-btn>
          <v-btn @click="clearFilters">Clear</v-btn>
        </v-col>
      </v-row>
    </v-card>

    <div v-if="store.loading" class="text-medium-emphasis pa-4">Loading…</div>
    <template v-else>
      <v-card v-if="store.jobs.length" rounded="lg" elevation="1">
        <v-table density="compact">
          <thead>
            <tr>
              <th>#</th><th>Policy</th><th>Triggered By</th><th>Status</th>
              <th>Started</th><th>Duration</th><th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in store.jobs" :key="job.id">
              <td class="text-medium-emphasis">#{{ job.id }}</td>
              <td>{{ job.policy_name ?? (job.policy ? `Policy ${job.policy}` : '—') }}</td>
              <td>{{ job.triggered_by }}</td>
              <td>
                <v-chip :color="statusColor(job.status)" size="x-small" label>{{ job.status }}</v-chip>
                <span v-if="job.status === 'running' && job.current_device" class="text-medium-emphasis text-caption ml-2">
                  ↳ {{ job.current_device }}
                </span>
              </td>
              <td class="text-medium-emphasis text-caption">{{ job.started_at ? fmt(job.started_at) : '—' }}</td>
              <td class="text-medium-emphasis text-caption">{{ duration(job) }}</td>
              <td>
                <v-btn size="x-small" variant="tonal" class="mr-1" @click="openDetail(job)">Details</v-btn>
                <v-btn
                  v-if="job.status === 'running' || job.status === 'pending'"
                  size="x-small" color="error" variant="tonal"
                  @click="cancel(job)"
                >Cancel</v-btn>
              </td>
            </tr>
          </tbody>
        </v-table>
      </v-card>
      <div v-else class="pa-6 text-center text-medium-emphasis">No jobs found.</div>

      <!-- Pagination -->
      <div class="d-flex align-center justify-center ga-2 mt-4">
        <v-btn size="small" variant="text" :disabled="store.page <= 1" @click="store.goPage(store.page - 1)">← Prev</v-btn>
        <span class="text-caption text-medium-emphasis">Page {{ store.page }} of {{ store.totalPages }} &nbsp;({{ store.totalCount }} total)</span>
        <v-btn size="small" variant="text" :disabled="store.page >= store.totalPages" @click="store.goPage(store.page + 1)">Next →</v-btn>
      </div>
    </template>

    <!-- Job detail dialog -->
    <v-dialog v-model="detailOpen" max-width="760" scrollable>
      <v-card v-if="selected" rounded="lg">
        <v-card-title class="d-flex justify-space-between align-center">
          <div>
            <span>Job #{{ selected.id }}</span>
            <v-chip :color="statusColor(selected.status)" size="x-small" label class="ml-2">{{ selected.status }}</v-chip>
          </div>
          <v-btn icon="mdi-close" variant="text" size="small" @click="detailOpen = false" />
        </v-card-title>
        <v-card-subtitle>
          {{ selected.policy_name ?? (selected.policy ? `Policy ${selected.policy}` : 'Push job') }}
          · triggered by {{ selected.triggered_by }}
          · {{ selected.started_at ? fmt(selected.started_at) : '—' }}
        </v-card-subtitle>
        <v-card-text>
          <v-card
            v-for="result in selected.device_results"
            :key="result.id"
            :border="`${resultColor(result.status)} md`"
            rounded="lg"
            class="mb-3"
          >
            <v-card-title class="d-flex align-center ga-2 pa-3 pb-2">
              <span class="text-body-2 font-weight-bold">{{ result.device_name ?? `Device ${result.device}` }}</span>
              <v-chip :color="statusColor(result.status)" size="x-small" label>{{ result.status }}</v-chip>
              <span class="text-caption text-medium-emphasis ml-auto">
                {{ result.started_at ? fmt(result.started_at) : '' }}
                {{ result.finished_at ? '→ ' + fmt(result.finished_at) : '' }}
              </span>
            </v-card-title>
            <v-card-text class="pa-3 pt-0">
              <v-alert v-if="result.error_message" type="error" variant="tonal" density="compact" class="mb-2">
                {{ result.error_message }}
              </v-alert>
              <v-expansion-panels variant="accordion">
                <v-expansion-panel title="Raw Output">
                  <template #text>
                    <pre class="result-pre">{{ result.raw_output || '(empty)' }}</pre>
                  </template>
                </v-expansion-panel>
                <v-expansion-panel title="Parsed Output">
                  <template #text>
                    <pre class="result-pre">{{ result.parsed_output ? JSON.stringify(result.parsed_output, null, 2) : '(none)' }}</pre>
                  </template>
                </v-expansion-panel>
                <v-expansion-panel v-if="result.drift_event" :title="`Drift Detected (${result.drift_event.status})`">
                  <template #text>
                    <pre class="result-pre">{{ JSON.stringify(result.drift_event.diff, null, 2) }}</pre>
                  </template>
                </v-expansion-panel>
              </v-expansion-panels>
              <div v-if="!result.drift_event && result.status === 'success'" class="text-success text-body-2 mt-2">
                ✓ No drift detected
              </div>
            </v-card-text>
          </v-card>
        </v-card-text>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import { useJobsStore } from '../stores/jobs'
import api from '../api'

const store = useJobsStore()
const selectedId = ref(null)
const detailOpen = ref(false)

// Derived from the store so every WS patch is immediately visible in the modal.
const selected = computed(() =>
  selectedId.value == null ? null : store.jobs.find(j => j.id === selectedId.value) ?? null
)

const devices = ref([])
const policies = ref([])
const statuses = ['pending', 'running', 'success', 'partial', 'failed', 'cancelled']

const deviceItems = computed(() => devices.value.map(d => ({ title: d.hostname, value: d.id })))
const policyItems = computed(() => policies.value.map(p => ({ title: p.name, value: p.id })))

const filters = reactive({
  device: null, policy: null, status: '',
  created_after: '', created_before: '',
})

function statusColor(status) {
  return { success: 'success', resolved: 'success', failed: 'error', running: 'info',
           pending: 'warning', new: 'error', acknowledged: 'warning', partial: 'warning',
           cancelled: 'default' }[status] ?? 'default'
}

function resultColor(status) {
  return { success: 'success', failed: 'error', running: 'info', partial: 'warning' }[status] ?? 'default'
}

function buildParams() {
  const p = {}
  if (filters.device)         p.device         = filters.device
  if (filters.policy)         p.policy         = filters.policy
  if (filters.status)         p.status         = filters.status
  if (filters.created_after)  p.created_after  = new Date(filters.created_after).toISOString()
  if (filters.created_before) p.created_before = new Date(filters.created_before).toISOString()
  return p
}

function applyFilters() { store.page = 1; store.fetchJobs(buildParams()) }
function clearFilters() {
  Object.assign(filters, { device: null, policy: null, status: '', created_after: '', created_before: '' })
  store.page = 1
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
  // Merge full detail (device_results etc.) back into the store so the
  // computed `selected` stays in sync with future WS patches.
  const idx = store.jobs.findIndex(j => j.id === data.id)
  if (idx !== -1) {
    store.jobs[idx] = { ...store.jobs[idx], ...data }
  } else {
    store.jobs.unshift(data)
  }
  selectedId.value = data.id
  detailOpen.value = true
}

async function cancel(job) {
  if (!confirm(`Cancel job ${job.id}?`)) return
  await api.post(`/jobs/${job.id}/cancel/`)
  applyFilters()
  if (selectedId.value === job.id) detailOpen.value = false
}

onMounted(async () => {
  const [dRes, pRes] = await Promise.all([
    api.get('/devices/'),
    api.get('/policies/'),
  ])
  devices.value  = dRes.data.results ?? dRes.data
  policies.value = pRes.data.results ?? pRes.data
  store.fetchJobs()
  store.connectWebSocket()
})
onUnmounted(() => store.disconnectWebSocket())
</script>

<style scoped>
.result-pre {
  background: #13131f;
  color: #cdd6f4;
  border-radius: 4px;
  padding: .65rem .75rem;
  font-size: .8rem;
  line-height: 1.5;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 300px;
}
</style>
