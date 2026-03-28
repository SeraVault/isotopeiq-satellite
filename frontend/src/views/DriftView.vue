<template>
  <div>
    <h1>Drift Events</h1>

    <div class="card filter-bar">
      <label>
        Device
        <select v-model="filters.device" @change="applyFilters">
          <option value="">All</option>
          <option v-for="d in devices" :key="d.id" :value="d.id">{{ d.name }}</option>
        </select>
      </label>
      <label>
        Status
        <select v-model="filters.status" @change="applyFilters">
          <option value="">All</option>
          <option value="new">New</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="resolved">Resolved</option>
        </select>
      </label>
      <div class="filter-actions">
        <button @click="applyFilters">Refresh</button>
        <button @click="clearFilters">Clear</button>
      </div>
    </div>

    <div v-if="store.loading">Loading…</div>
    <template v-else>
      <table v-if="store.events.length">
        <thead>
          <tr><th>Device</th><th>Status</th><th>Detected</th><th>Acknowledged By</th><th>Diff Keys</th><th>Actions</th></tr>
        </thead>
        <tbody>
          <tr v-for="event in store.events" :key="event.id">
            <td>{{ event.device_name ?? event.device }}</td>
            <td><span :class="`badge badge-${event.status}`">{{ event.status }}</span></td>
            <td>{{ new Date(event.created_at).toLocaleString() }}</td>
            <td>
              <span v-if="event.acknowledged_by">
                {{ event.acknowledged_by }}
                <span v-if="event.acknowledgement_reason" class="text-muted" style="font-size:.8rem"> — {{ event.acknowledgement_reason }}</span>
              </span>
              <span v-else class="text-muted">—</span>
            </td>
            <td>{{ Object.keys(event.diff).join(', ') || '—' }}</td>
            <td>
              <button @click="openDiff(event)">View Diff</button>
              <button v-if="event.status === 'new'" @click="openAcknowledge(event)">Acknowledge</button>
              <button v-if="event.status !== 'resolved'" @click="store.resolve(event.id)">Resolve</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="text-muted">No drift events.</p>
      <PaginationBar :page="store.page" :total-pages="store.totalPages" :total-count="store.totalCount" @go="store.goPage" />
    </template>

    <!-- Diff detail modal -->
    <div v-if="selected" class="modal">
      <div class="modal-box modal-xl">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;margin-bottom:.75rem">
          <div>
            <h2 style="margin:0">Drift — {{ selected.device_name ?? selected.device }}</h2>
            <p style="margin:.25rem 0 0;color:#666;font-size:.85rem">
              <span :class="`badge badge-${selected.status}`">{{ selected.status }}</span>
              &nbsp; {{ new Date(selected.created_at).toLocaleString() }}
            </p>
          </div>
          <button @click="selected = null">✕ Close</button>
        </div>
        <div v-if="diffLoading" class="text-muted" style="padding:1rem 0">Loading diff data…</div>
        <DriftDiffViewer v-else :baseline="selected.baseline_data" :current="selected.result_data" :volatile-fields="store.volatileFields" />
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
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useDriftStore } from '../stores/drift'
import api from '../api'
import DriftDiffViewer from '../components/DriftDiffViewer.vue'
import PaginationBar from '../components/PaginationBar.vue'

const store = useDriftStore()
const devices = ref([])

const filters = reactive({ device: '', status: '' })

function applyFilters() {
  store.page = 1
  const p = {}
  if (filters.device) p.device = filters.device
  if (filters.status) p.status = filters.status
  store.fetchEvents(p)
}

function clearFilters() {
  Object.assign(filters, { device: '', status: '' })
  store.page = 1
  store.fetchEvents()
}

const selected = ref(null)
const diffLoading = ref(false)

async function openDiff(event) {
  selected.value = { ...event, baseline_data: null, result_data: null }
  diffLoading.value = true
  try {
    const [baselineRes, resultRes] = await Promise.all([
      api.get('/baselines/', { params: { device: event.device } }),
      api.get(`/jobs/results/${event.job_result}/`),
      store.fetchVolatileFields(),
    ])
    const baselines = baselineRes.data.results ?? baselineRes.data
    selected.value = {
      ...event,
      baseline_data: baselines[0]?.parsed_data ?? null,
      result_data: resultRes.data.parsed_output ?? null,
    }
  } finally {
    diffLoading.value = false
  }
}

const acknowledging = ref(null)
const ackReason = ref('')
const ackError = ref('')
const ackSaving = ref(false)

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
    await store.acknowledge(acknowledging.value.id, ackReason.value.trim())
    acknowledging.value = null
    ackReason.value = ''
  } catch (e) {
    ackError.value = e.response?.data?.error ?? 'Failed to acknowledge.'
  } finally {
    ackSaving.value = false
  }
}

onMounted(async () => {
  const { data } = await api.get('/devices/', { params: { page_size: 500 } })
  devices.value = data.results ?? data
  store.fetchEvents()
})
</script>

<style scoped>
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
</style>
