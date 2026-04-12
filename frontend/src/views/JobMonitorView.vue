<template>
  <div>
    <div class="text-h5 font-weight-bold mb-5">Job Monitor</div>

    <!-- Filters -->
    <v-card rounded="lg" elevation="1" class="mb-5 pa-4">
      <v-row dense align="end">
        <v-col cols="12" sm="6" md="2">
          <DeviceAutocomplete v-model="filters.device" @update:model-value="applyFilters" />
        </v-col>
        <v-col cols="12" sm="6" md="2">
          <v-select v-model="filters.type" label="Type" :items="typeItems" clearable @update:model-value="applyFilters" />
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

    <v-data-table-server
      v-model:options="tableOptions"
      :headers="headers"
      :items="jobs.items"
      :items-length="jobs.total"
      :loading="jobs.loading"
      :items-per-page-options="[25, 50, 100]"
      density="compact"
      rounded="lg"
      elevation="1"
      no-data-text="No jobs found."
      hover
      @update:options="onTableOptions"
    >
      <template #item.record_type="{ item }">
        <v-chip
          :color="item.record_type === 'policy_job' ? 'blue-darken-1' : 'purple-darken-1'"
          size="x-small" label
        >{{ item.record_type === 'policy_job' ? 'Policy Job' : 'Bundle Run' }}</v-chip>
      </template>
      <template #item.device_name="{ item }">
        <span class="font-weight-medium">{{ item.device_name ?? '—' }}</span>
      </template>
      <template #item.source="{ item }">{{ item.source }}</template>
      <template #item.status="{ item }">
        <v-chip :color="statusColor(item.status)" size="x-small" label>{{ item.status }}</v-chip>
      </template>
      <template #item.started_at="{ item }">
        <span class="text-medium-emphasis text-caption">{{ item.started_at ? fmt(item.started_at) : '—' }}</span>
      </template>
      <template #item.duration="{ item }">
        <span class="text-medium-emphasis text-caption">{{ duration(item) }}</span>
      </template>
      <template #item.actions="{ item }">
        <v-btn size="x-small" variant="tonal" class="mr-1" @click="openDetail(item)">Details</v-btn>
        <v-btn
          v-if="item.record_type === 'policy_job' && (item.status === 'running' || item.status === 'pending')"
          size="x-small" color="error" variant="tonal"
          @click="cancel(item)"
        >Cancel</v-btn>
      </template>
    </v-data-table-server>

    <!-- Confirm dialog -->
    <v-dialog v-model="confirmDialog.open" max-width="400" persistent>
      <v-card rounded="lg">
        <v-card-title class="pt-4">Confirm</v-card-title>
        <v-card-text>{{ confirmDialog.message }}</v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="confirmDialog.resolve(false)">Cancel</v-btn>
          <v-btn color="error" variant="tonal" @click="confirmDialog.resolve(true)">Confirm</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Policy job detail dialog -->
    <v-dialog v-model="policyDetailOpen" max-width="760" scrollable>
      <v-card v-if="policySelected" rounded="lg">
        <v-card-title class="d-flex justify-space-between align-center">
          <div>
            <span>{{ policySelected.device_name ?? `Job #${policySelected.id}` }}</span>
            <v-chip :color="statusColor(policySelected.status)" size="x-small" label class="ml-2">{{ policySelected.status }}</v-chip>
          </div>
          <v-btn icon="mdi-close" variant="text" size="small" @click="policyDetailOpen = false" />
        </v-card-title>
        <v-card-subtitle>
          {{ policySelected.policy_name ? `Policy: ${policySelected.policy_name}` : 'Ad-hoc' }}
          · triggered by {{ policySelected.triggered_by }}
          · {{ policySelected.started_at ? fmt(policySelected.started_at) : '—' }}
        </v-card-subtitle>
        <v-card-text>
          <template v-if="policySelected.device_results?.length">
            <div v-for="result in policySelected.device_results" :key="result.id">
              <div class="d-flex align-center ga-2 mb-3">
                <v-chip :color="statusColor(result.status)" size="x-small" label>{{ result.status }}</v-chip>
                <span class="text-caption text-medium-emphasis">
                  {{ result.started_at ? fmt(result.started_at) : '' }}
                  {{ result.finished_at ? ' → ' + fmt(result.finished_at) : '' }}
                </span>
              </div>
              <v-alert v-if="result.error_message" type="error" variant="tonal" density="compact" class="mb-3">
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
            </div>
          </template>
          <div v-else class="text-medium-emphasis pa-2">No result data yet.</div>
        </v-card-text>
      </v-card>
    </v-dialog>

    <!-- Bundle run detail dialog -->
    <v-dialog v-model="bundleDetailOpen" max-width="760" scrollable>
      <v-card v-if="bundleSelected" rounded="lg">
        <v-card-title class="d-flex justify-space-between align-center">
          <div>
            <span>{{ bundleSelected.script_job_name }}</span>
            <v-chip :color="statusColor(bundleSelected.status)" size="x-small" label class="ml-2">{{ bundleSelected.status }}</v-chip>
          </div>
          <v-btn icon="mdi-close" variant="text" size="small" @click="bundleDetailOpen = false" />
        </v-card-title>
        <v-card-subtitle>
          Device: {{ bundleSelected.device_name || '(server-only)' }}
          · triggered by {{ bundleSelected.triggered_by }}
          · {{ bundleSelected.started_at ? fmt(bundleSelected.started_at) : '—' }}
        </v-card-subtitle>
        <v-card-text>
          <v-alert v-if="bundleSelected.error_message" type="error" variant="tonal" density="compact" class="mb-4">
            {{ bundleSelected.error_message }}
          </v-alert>
          <template v-if="bundleSelected.step_outputs?.length">
            <div v-for="step in bundleSelected.step_outputs" :key="step.order" class="mb-4">
              <div class="d-flex align-center ga-2 mb-1">
                <span class="text-caption font-weight-bold text-medium-emphasis text-uppercase">Step {{ step.order + 1 }} — {{ step.script }}</span>
                <v-chip size="x-small" label :color="step.run_on === 'client' ? 'blue-darken-1' : 'purple-darken-1'">{{ step.run_on === 'client' ? 'Push to device' : 'Run on Satellite' }}</v-chip>
              </div>
              <pre class="result-pre">{{ step.output || '(empty)' }}</pre>
            </div>
          </template>
          <div v-else class="text-medium-emphasis pa-2">No step output recorded.</div>
        </v-card-text>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted } from 'vue'
import api from '../api'
import DeviceAutocomplete from '../components/DeviceAutocomplete.vue'

const headers = [
  { title: 'Type',         key: 'record_type',  sortable: false },
  { title: 'Device',       key: 'device_name',  sortable: false },
  { title: 'Source',       key: 'source',       sortable: false },
  { title: 'Triggered By', key: 'triggered_by', sortable: false },
  { title: 'Status',       key: 'status',       sortable: false },
  { title: 'Started',      key: 'started_at',   sortable: false },
  { title: 'Duration',     key: 'duration',     sortable: false },
  { title: '',             key: 'actions',      sortable: false, align: 'end' },
]

const typeItems = [
  { title: 'Policy Jobs', value: 'policy_job' },
  { title: 'Bundle Runs', value: 'bundle_run' },
]
const statuses = ['pending', 'running', 'success', 'partial', 'failed', 'cancelled']

const filters = reactive({
  device: null,
  type: null,
  status: '',
  created_after: '',
  created_before: '',
})

const tableOptions = ref({ page: 1, itemsPerPage: 25, sortBy: [] })
const jobs = ref({ items: [], total: 0, loading: false })

// True when any row is still running/pending — drives poll interval
const hasActiveJobs = computed(() =>
  jobs.value.items.some(j => j.status === 'running' || j.status === 'pending')
)

// Merge incoming rows into the existing reactive array in-place so Vuetify
// only patches DOM rows that actually changed, avoiding full-table flicker.
function mergeItems(incoming) {
  const key = (r) => `${r.record_type}:${r.record_id}`
  const incomingKeys = new Set(incoming.map(key))
  for (let i = jobs.value.items.length - 1; i >= 0; i--) {
    if (!incomingKeys.has(key(jobs.value.items[i]))) jobs.value.items.splice(i, 1)
  }
  incoming.forEach((item, idx) => {
    const existing = jobs.value.items.findIndex(c => key(c) === key(item))
    if (existing !== -1) {
      Object.assign(jobs.value.items[existing], item)
    } else {
      jobs.value.items.splice(idx, 0, item)
    }
  })
}

function buildParams(options = tableOptions.value) {
  const params = { page: options.page, page_size: options.itemsPerPage }
  if (filters.device)         params.device         = filters.device
  if (filters.type)           params.type           = filters.type
  if (filters.status)         params.status         = filters.status
  if (filters.created_after)  params.created_after  = new Date(filters.created_after).toISOString()
  if (filters.created_before) params.created_before = new Date(filters.created_before).toISOString()
  return params
}

async function loadJobs(options = tableOptions.value, showSpinner = true) {
  if (showSpinner) jobs.value.loading = true
  try {
    const { data } = await api.get('/jobs/unified/', { params: buildParams(options) })
    mergeItems(data.results ?? [])
    jobs.value.total = data.count ?? 0
  } finally {
    if (showSpinner) jobs.value.loading = false
  }
}

function onTableOptions(options) {
  tableOptions.value = options
  loadJobs(options)
}

function applyFilters() {
  const opts = { ...tableOptions.value, page: 1 }
  tableOptions.value = opts
  loadJobs(opts)
}

function clearFilters() {
  Object.assign(filters, { device: null, type: null, status: '', created_after: '', created_before: '' })
  applyFilters()
}

// ── Detail dialogs ────────────────────────────────────────────────────────────
const policyDetailOpen = ref(false)
const policySelected   = ref(null)
const bundleDetailOpen = ref(false)
const bundleSelected   = ref(null)

const confirmDialog = ref({ open: false, message: '', resolve: () => {} })
function askConfirm(message) {
  return new Promise(resolve => {
    confirmDialog.value = { open: true, message, resolve: (val) => { confirmDialog.value.open = false; resolve(val) } }
  })
}

async function openDetail(item) {
  if (item.record_type === 'policy_job') {
    const { data } = await api.get(`/jobs/${item.record_id}/`)
    policySelected.value   = data
    policyDetailOpen.value = true
  } else {
    const { data } = await api.get(`/scripts/script-jobs/results/${item.record_id}/`)
    bundleSelected.value   = data
    bundleDetailOpen.value = true
  }
}

async function cancel(item) {
  if (!await askConfirm(`Cancel job ${item.record_id}?`)) return
  await api.post(`/jobs/${item.record_id}/cancel/`)
  applyFilters()
}

// ── Helpers ───────────────────────────────────────────────────────────────────
function statusColor(status) {
  return { success: 'success', resolved: 'success', failed: 'error', running: 'info',
           pending: 'warning', new: 'error', acknowledged: 'warning', partial: 'warning',
           cancelled: 'default' }[status] ?? 'default'
}

function fmt(iso) { return new Date(iso).toLocaleString() }

function duration(job) {
  if (!job.started_at || !job.finished_at) return '—'
  const ms = new Date(job.finished_at) - new Date(job.started_at)
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`
}

// ── Polling ───────────────────────────────────────────────────────────────────
// Poll silently every 5s while active jobs exist, every 30s otherwise.
let pollTimer = null

function schedulePoll() {
  clearInterval(pollTimer)
  const interval = hasActiveJobs.value ? 5_000 : 30_000
  pollTimer = setInterval(() => {
    loadJobs(tableOptions.value, false)  // silent — no spinner
    schedulePoll()                       // re-schedule with updated interval
  }, interval)
}

onMounted(() => {
  loadJobs().then(schedulePoll)
})

onUnmounted(() => {
  clearInterval(pollTimer)
})
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
