<template>
  <div>
    <div class="text-h5 font-weight-bold mb-5">Job Monitor</div>

    <v-tabs v-model="activeTab" class="mb-5">
      <v-tab value="policy">Policy Jobs</v-tab>
      <v-tab value="script">Script Job Runs</v-tab>
    </v-tabs>

    <v-window v-model="activeTab">
      <!-- ── POLICY JOBS TAB ─────────────────────────────────────────── -->
      <v-window-item value="policy">

    <!-- Filters -->
    <v-card rounded="lg" elevation="1" class="mb-5 pa-4">
      <v-row dense align="end">
        <v-col cols="12" sm="6" md="2">
          <DeviceAutocomplete v-model="filters.device" @update:model-value="onDeviceSelect" />
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

    <v-data-table-server
      v-model:options="tableOptions"
      :headers="headers"
      :items="store.jobs"
      :items-length="store.totalCount"
      :loading="store.loading"
      :items-per-page-options="[25, 50, 100]"
      density="compact"
      rounded="lg"
      elevation="1"
      no-data-text="No jobs found."
      hover
      @update:options="onTableOptions"
    >
      <template #item.id="{ item }">
        <span class="text-medium-emphasis">#{{ item.id }}</span>
      </template>
      <template #item.device_name="{ item }">
        <span class="font-weight-medium">{{ item.device_name ?? (item.device ? `Device ${item.device}` : '—') }}</span>
      </template>
      <template #item.policy_name="{ item }">{{ item.policy_name ?? '—' }}</template>
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
          v-if="item.status === 'running' || item.status === 'pending'"
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

    <!-- Job detail dialog -->
    <v-dialog v-model="detailOpen" max-width="760" scrollable>
      <v-card v-if="selected" rounded="lg">
        <v-card-title class="d-flex justify-space-between align-center">
          <div>
            <span>{{ selected.device_name ?? (selected.device ? `Device ${selected.device}` : `Job #${selected.id}`) }}</span>
            <v-chip :color="statusColor(selected.status)" size="x-small" label class="ml-2">{{ selected.status }}</v-chip>
          </div>
          <v-btn icon="mdi-close" variant="text" size="small" @click="detailOpen = false" />
        </v-card-title>
        <v-card-subtitle>
          {{ selected.policy_name ? `Policy: ${selected.policy_name}` : 'Ad-hoc' }}
          · triggered by {{ selected.triggered_by }}
          · {{ selected.started_at ? fmt(selected.started_at) : '—' }}
        </v-card-subtitle>
        <v-card-text>
          <!-- Single device result, shown inline -->
          <template v-if="selected.device_results && selected.device_results.length">
            <div v-for="result in selected.device_results" :key="result.id">
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

      </v-window-item>

      <!-- ── SCRIPT JOB RUNS TAB ─────────────────────────────────────── -->
      <v-window-item value="script">
        <div class="d-flex align-center justify-space-between mb-4">
          <div class="text-caption text-medium-emphasis">Results from ad-hoc and policy-triggered script job executions.</div>
          <v-btn size="small" variant="tonal" prepend-icon="mdi-refresh" :loading="sjRuns.loading" @click="loadSjRuns">Refresh</v-btn>
        </div>
        <v-data-table
          :headers="sjRunHeaders"
          :items="sjRuns.items"
          :loading="sjRuns.loading"
          density="compact"
          rounded="lg"
          elevation="1"
          :items-per-page="25"
          no-data-text="No script job runs yet."
          hover
        >
          <template #item.script_job_name="{ item }">
            <span class="font-weight-medium">{{ item.script_job_name }}</span>
          </template>
          <template #item.device_name="{ item }">{{ item.device_name || '(server-only)' }}</template>
          <template #item.status="{ item }">
            <v-chip :color="statusColor(item.status)" size="x-small" label>{{ item.status }}</v-chip>
          </template>
          <template #item.started_at="{ item }">
            <span class="text-caption text-medium-emphasis">{{ item.started_at ? fmt(item.started_at) : '—' }}</span>
          </template>
          <template #item.duration="{ item }">
            <span class="text-caption text-medium-emphasis">{{ duration(item) }}</span>
          </template>
          <template #item.actions="{ item }">
            <v-btn size="x-small" variant="tonal" @click="openSjDetail(item)">Details</v-btn>
          </template>
        </v-data-table>
      </v-window-item>
    </v-window>

    <!-- Script job run detail dialog -->
    <v-dialog v-model="sjDetailOpen" max-width="760" scrollable>
      <v-card v-if="sjSelected" rounded="lg">
        <v-card-title class="d-flex justify-space-between align-center">
          <div>
            <span>{{ sjSelected.script_job_name }}</span>
            <v-chip :color="statusColor(sjSelected.status)" size="x-small" label class="ml-2">{{ sjSelected.status }}</v-chip>
          </div>
          <v-btn icon="mdi-close" variant="text" size="small" @click="sjDetailOpen = false" />
        </v-card-title>
        <v-card-subtitle>
          Device: {{ sjSelected.device_name || '(server-only)' }}
          · triggered by {{ sjSelected.triggered_by }}
          · {{ sjSelected.started_at ? fmt(sjSelected.started_at) : '—' }}
        </v-card-subtitle>
        <v-card-text>
          <v-alert v-if="sjSelected.error_message" type="error" variant="tonal" density="compact" class="mb-4">
            {{ sjSelected.error_message }}
          </v-alert>
          <template v-if="sjSelected.step_outputs?.length">
            <div v-for="step in sjSelected.step_outputs" :key="step.order" class="mb-4">
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
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useJobsStore } from '../stores/jobs'
import api from '../api'
import DeviceAutocomplete from '../components/DeviceAutocomplete.vue'

const route = useRoute()

const store = useJobsStore()

const headers = [
  { title: '#',            key: 'id',           sortable: false },
  { title: 'Device',       key: 'device_name',  sortable: true  },
  { title: 'Policy',       key: 'policy_name',  sortable: false },
  { title: 'Triggered By', key: 'triggered_by', sortable: false },
  { title: 'Status',       key: 'status',       sortable: false },
  { title: 'Started',      key: 'started_at',   sortable: true  },
  { title: 'Duration',     key: 'duration',     sortable: false },
  { title: '',             key: 'actions',      sortable: false, align: 'end' },
]

const SORT_FIELD = {
  device_name: 'device__name',
  started_at:  'started_at',
}

const tableOptions = ref({ page: 1, itemsPerPage: 25, sortBy: [{ key: 'started_at', order: 'desc' }] })

function buildParams(options = tableOptions.value) {
  const params = { page: options.page, page_size: options.itemsPerPage }
  if (filters.device)         params.device         = filters.device
  if (filters.policy)         params.policy         = filters.policy
  if (filters.status)         params.status         = filters.status
  if (filters.created_after)  params.created_after  = new Date(filters.created_after).toISOString()
  if (filters.created_before) params.created_before = new Date(filters.created_before).toISOString()
  if (options.sortBy?.length) {
    const { key, order } = options.sortBy[0]
    const field = SORT_FIELD[key] ?? key
    params.ordering = order === 'desc' ? `-${field}` : field
  }
  return params
}

function onTableOptions(options) {
  tableOptions.value = options
  store.fetchJobs(buildParams(options))
}

function resetAndFetch() {
  const opts = { ...tableOptions.value, page: 1 }
  tableOptions.value = opts
  store.fetchJobs(buildParams(opts))
}

const selectedId = ref(null)
const detailOpen = ref(false)

const confirmDialog = ref({ open: false, message: '', resolve: () => {} })
function askConfirm(message) {
  return new Promise(resolve => {
    confirmDialog.value = { open: true, message, resolve: (val) => { confirmDialog.value.open = false; resolve(val) } }
  })
}

// Local ref holds the full detail (raw_output/parsed_output) from the detail endpoint.
// We do NOT derive it from the store because the list-poll serializer strips those fields.
const selected = ref(null)

// When the poll refreshes store.jobs, merge only lightweight fields into the detail ref
// so the modal shows live status without losing the rich data we fetched from the detail endpoint.
watch(() => store.jobs, (jobs) => {
  if (!selected.value) return
  const fresh = jobs.find(j => j.id === selected.value.id)
  if (fresh) {
    selected.value = {
      ...selected.value,
      status:      fresh.status,
      started_at:  fresh.started_at,
      finished_at: fresh.finished_at,
    }
  }
}, { deep: true })

const policies = ref([])
const statuses = ['pending', 'running', 'success', 'partial', 'failed', 'cancelled']

function onDeviceSelect() {
  applyFilters()
}
const policyItems = computed(() => policies.value.map(p => ({ title: p.name, value: p.id })))

const filters = reactive({
  device: null, policy: null,
  status:         route.query.status || '',
  created_after:  '',
  created_before: '',
})

function statusColor(status) {
  return { success: 'success', resolved: 'success', failed: 'error', running: 'info',
           pending: 'warning', new: 'error', acknowledged: 'warning', partial: 'warning',
           cancelled: 'default' }[status] ?? 'default'
}

function resultColor(status) {
  return { success: 'success', failed: 'error', running: 'info', partial: 'warning' }[status] ?? 'default'
}

function applyFilters() { resetAndFetch() }
function clearFilters() {
  Object.assign(filters, { device: null, policy: null, status: '', created_after: '', created_before: '' })
  resetAndFetch()
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
  selected.value  = data
  selectedId.value = data.id
  detailOpen.value = true
}

async function cancel(job) {
  if (!await askConfirm(`Cancel job ${job.id}?`)) return
  await api.post(`/jobs/${job.id}/cancel/`)
  applyFilters()
  if (selectedId.value === job.id) detailOpen.value = false
}

// ── Script Job Runs tab ──────────────────────────────────────────────────────
const activeTab = ref(route.query.tab === 'script' ? 'script' : 'policy')

const sjRunHeaders = [
  { title: 'Script Job',   key: 'script_job_name', sortable: false },
  { title: 'Device',       key: 'device_name',     sortable: false },
  { title: 'Triggered By', key: 'triggered_by',    sortable: false },
  { title: 'Status',       key: 'status',          sortable: false },
  { title: 'Started',      key: 'started_at',      sortable: false },
  { title: 'Duration',     key: 'duration',        sortable: false },
  { title: '',             key: 'actions',         sortable: false, align: 'end' },
]

const sjRuns = ref({ items: [], loading: false })
const sjDetailOpen = ref(false)
const sjSelected = ref(null)

async function loadSjRuns() {
  sjRuns.value.loading = true
  try {
    const res = await api.get('/scripts/script-jobs/results/', { params: { page_size: 100, ordering: '-started_at' } })
    sjRuns.value.items = res.data?.results ?? res.data ?? []
  } finally {
    sjRuns.value.loading = false
  }
}

function openSjDetail(item) {
  sjSelected.value = item
  sjDetailOpen.value = true
}

// Refresh script job runs on tab switch and every 10s while on that tab
let sjPollTimer = null
watch(activeTab, (tab) => {
  clearInterval(sjPollTimer)
  if (tab === 'script') {
    loadSjRuns()
    sjPollTimer = setInterval(loadSjRuns, 10_000)
  }
}, { immediate: true })

onMounted(async () => {
  const { data } = await api.get('/policies/')
  policies.value = data.results ?? data
  applyFilters()
  store.startPolling()
})
onUnmounted(() => {
  store.stopPolling()
  clearInterval(sjPollTimer)
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
