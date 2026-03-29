<template>
  <div>
    <div class="text-h5 font-weight-bold mb-5">Drift Events</div>

    <!-- Filters -->
    <v-card rounded="lg" elevation="1" class="mb-5 pa-4">
      <v-row dense align="end">
        <v-col cols="12" sm="6" md="3">
          <v-select v-model="filters.device" label="Device" :items="deviceItems" item-title="title" item-value="value" clearable @update:model-value="applyFilters" />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-select v-model="filters.status" label="Status" :items="['new','acknowledged','resolved']" clearable @update:model-value="applyFilters" />
        </v-col>
        <v-col cols="12" sm="auto">
          <v-btn color="primary" class="mr-2" @click="applyFilters">Refresh</v-btn>
          <v-btn @click="clearFilters">Clear</v-btn>
        </v-col>
      </v-row>
    </v-card>

    <div v-if="store.loading" class="text-medium-emphasis pa-4">Loading…</div>
    <template v-else>
      <v-card v-if="store.events.length" rounded="lg" elevation="1">
        <v-table density="compact">
          <thead>
            <tr>
              <th>Device</th><th>Status</th><th>Detected</th>
              <th>Acknowledged By</th><th>Diff Keys</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="event in store.events" :key="event.id">
              <td class="font-weight-medium">{{ event.device_name ?? event.device }}</td>
              <td><v-chip :color="statusColor(event.status)" size="x-small" label>{{ event.status }}</v-chip></td>
              <td class="text-medium-emphasis text-caption">{{ new Date(event.created_at).toLocaleString() }}</td>
              <td>
                <span v-if="event.acknowledged_by">
                  {{ event.acknowledged_by }}
                  <span v-if="event.acknowledgement_reason" class="text-medium-emphasis text-caption"> — {{ event.acknowledgement_reason }}</span>
                </span>
                <span v-else class="text-medium-emphasis">—</span>
              </td>
              <td class="text-caption text-medium-emphasis">{{ Object.keys(event.diff || {}).join(', ') || '—' }}</td>
              <td>
                <v-btn size="x-small" variant="tonal" class="mr-1" @click="openDiff(event)">View Diff</v-btn>
                <v-btn v-if="event.status === 'new' && reviewedIds.includes(event.id)" size="x-small" variant="tonal" @click="openAcknowledge(event)">Acknowledge</v-btn>
              </td>
            </tr>
          </tbody>
        </v-table>
      </v-card>
      <div v-else class="pa-6 text-center text-medium-emphasis">No drift events.</div>

      <!-- Pagination -->
      <div class="d-flex align-center justify-center ga-2 mt-4">
        <v-btn size="small" variant="text" :disabled="store.page <= 1" @click="store.goPage(store.page - 1)">← Prev</v-btn>
        <span class="text-caption text-medium-emphasis">Page {{ store.page }} of {{ store.totalPages }} &nbsp;({{ store.totalCount }} total)</span>
        <v-btn size="small" variant="text" :disabled="store.page >= store.totalPages" @click="store.goPage(store.page + 1)">Next →</v-btn>
      </div>
    </template>

    <!-- Diff detail dialog -->
    <v-dialog v-model="diffOpen" max-width="1100" scrollable>
      <v-card v-if="selected" rounded="lg">
        <v-card-title class="d-flex justify-space-between align-center">
          <div>
            <span>Drift — {{ selected.device_name ?? selected.device }}</span>
            <v-chip :color="statusColor(selected.status)" size="x-small" label class="ml-2">{{ selected.status }}</v-chip>
          </div>
          <v-btn icon="mdi-close" variant="text" size="small" @click="diffOpen = false" />
        </v-card-title>
        <v-card-subtitle>{{ new Date(selected.created_at).toLocaleString() }}</v-card-subtitle>
        <v-card-text>
          <div v-if="diffLoading" class="text-medium-emphasis pa-4">Loading diff data…</div>
          <DriftDiffViewer v-else :baseline="selected.baseline_data" :current="selected.result_data" :volatile-fields="store.volatileFields" />
        </v-card-text>
      </v-card>
    </v-dialog>

    <!-- Acknowledge dialog -->
    <v-dialog v-model="ackOpen" max-width="460">
      <v-card rounded="lg">
        <v-card-title>Acknowledge Drift</v-card-title>
        <v-card-subtitle v-if="acknowledging">Device: {{ acknowledging.device_name ?? acknowledging.device }}</v-card-subtitle>
        <v-card-text>
          <v-alert v-if="ackError" type="error" variant="tonal" density="compact" class="mb-3">{{ ackError }}</v-alert>
          <v-textarea v-model="ackReason" label="Reason *" rows="4" placeholder="Explain why this drift is expected or acceptable…" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="ackOpen = false">Cancel</v-btn>
          <v-btn color="primary" :loading="ackSaving" @click="submitAcknowledge">Acknowledge</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useDriftStore } from '../stores/drift'
import api from '../api'
import DriftDiffViewer from '../components/DriftDiffViewer.vue'

const store = useDriftStore()
const devices = ref([])
const deviceItems = computed(() => devices.value.map(d => ({ title: d.name, value: d.id })))

const filters = reactive({ device: null, status: '' })

function statusColor(status) {
  return { success: 'success', resolved: 'success', failed: 'error', running: 'info',
           pending: 'warning', new: 'error', acknowledged: 'warning', partial: 'warning',
           cancelled: 'default' }[status] ?? 'default'
}

function applyFilters() {
  store.page = 1
  const p = {}
  if (filters.device) p.device = filters.device
  if (filters.status) p.status = filters.status
  store.fetchEvents(p)
}

function clearFilters() {
  Object.assign(filters, { device: null, status: '' })
  store.page = 1
  store.fetchEvents()
}

const reviewedIds = ref([])

const selected = ref(null)
const diffOpen = ref(false)
const diffLoading = ref(false)

async function openDiff(event) {
  if (!reviewedIds.value.includes(event.id)) {
    reviewedIds.value = [...reviewedIds.value, event.id]
  }
  selected.value = { ...event, baseline_data: null, result_data: null }
  diffOpen.value = true
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
const ackOpen = ref(false)
const ackReason = ref('')
const ackError = ref('')
const ackSaving = ref(false)

function openAcknowledge(event) {
  acknowledging.value = event
  ackReason.value = ''
  ackError.value = ''
  ackOpen.value = true
}

async function submitAcknowledge() {
  if (!ackReason.value.trim()) { ackError.value = 'A reason is required.'; return }
  ackSaving.value = true
  ackError.value = ''
  try {
    await store.acknowledge(acknowledging.value.id, ackReason.value.trim())
    ackOpen.value = false
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
