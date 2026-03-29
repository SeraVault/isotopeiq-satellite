<template>
  <div>
    <div class="d-flex align-center mb-4">
      <div class="text-h5 font-weight-bold">Drift Events</div>
      <v-spacer />
      <v-btn variant="tonal" prepend-icon="mdi-help-circle-outline" @click="showHelp = true">How it works</v-btn>
    </div>

    <!-- How it works dialog -->
    <v-dialog v-model="showHelp" max-width="720" scrollable>
      <v-card rounded="lg">
        <v-card-title class="d-flex align-center pt-4 pb-2">
          <v-icon icon="mdi-compare-horizontal" class="mr-2" color="primary" />
          Drift Detection
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" @click="showHelp = false" />
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-5" style="font-size:0.92rem;line-height:1.7">

          <p class="mb-3">
            <strong>Drift</strong> is any difference between a device's current configuration and its
            stored <strong>baseline</strong> snapshot. IsotopeIQ Satellite detects, records, and
            surfaces these differences so you can decide whether a change was expected or requires
            investigation.
          </p>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">1. Baseline snapshot</div>
          <p class="mb-3">
            The first time a policy runs successfully for a device, the parsed collection output is
            stored as the authoritative baseline. All future collections for that policy+device pair
            are compared against this snapshot. You can view and manage baselines on the
            <strong>Baselines</strong> page.
          </p>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">2. Comparison &amp; diff</div>
          <p class="mb-3">
            Each subsequent collection is diffed section-by-section against the baseline. Changes
            are classified as <em>changed</em>, <em>added</em>, or <em>removed</em> at the field
            or array-item level. Click <strong>View Diff</strong> on any event to inspect the
            side-by-side comparison.
          </p>
          <p class="mb-0">
            Fields covered by a <strong>volatile rule</strong> are silently excluded before comparison
            so expected, high-churn values (e.g. disk free space, PIDs, entropy pool) never
            trigger false positives. Use the
            <v-icon icon="mdi-eye-off-outline" size="x-small" /> ignore button inside any diff
            to permanently promote a noisy field to a volatile rule.
          </p>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">3. Event lifecycle</div>
          <v-table density="compact" class="mb-3 rounded-lg" style="border:1px solid rgba(0,0,0,.12)">
            <tbody>
              <tr>
                <td class="font-weight-medium" style="width:30%">new</td>
                <td>Drift was detected and has not yet been reviewed.</td>
              </tr>
              <tr>
                <td class="font-weight-medium">acknowledged</td>
                <td>A user has reviewed the event and recorded a reason — the change was expected or accepted.</td>
              </tr>
              <tr>
                <td class="font-weight-medium">resolved</td>
                <td>The device's configuration has returned to match the baseline on a subsequent collection.</td>
              </tr>
            </tbody>
          </v-table>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">Volatile rules</div>
          <p class="mb-0">
            Volatile rules tell Satellite which fields to ignore during comparison. They are managed
            on the <strong>Volatile Rules</strong> page and applied globally across all devices.
            Rules can target a top-level section field, a per-item field in an array section, a
            nested sub-field, or a specific key in key-value sections like <code>sysctl</code>.
          </p>

        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-3">
          <v-spacer />
          <v-btn color="primary" variant="tonal" @click="showHelp = false">Got it</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-data-table-server
      v-model:options="tableOptions"
      :headers="headers"
      :items="store.events"
      :items-length="store.totalCount"
      :loading="store.loading"
      :items-per-page-options="[25, 50, 100]"
      density="compact"
      rounded="lg"
      elevation="1"
      no-data-text="No drift events."
      @update:options="onTableOptions"
    >
      <!-- Filters embedded in table top slot -->
      <template #top>
        <v-row dense align="end" class="pa-3 pb-0">
          <v-col cols="12" sm="6" md="3">
            <v-select v-model="filters.device" label="Device" :items="deviceItems" item-title="title" item-value="value"
              clearable density="compact" hide-details variant="outlined" @update:model-value="resetAndFetch" />
          </v-col>
          <v-col cols="12" sm="6" md="3">
            <v-select v-model="filters.status" label="Status" :items="['new','acknowledged','resolved']"
              clearable density="compact" hide-details variant="outlined" @update:model-value="resetAndFetch" />
          </v-col>
          <v-col cols="12" sm="auto" class="d-flex align-center">
            <v-btn size="small" variant="tonal" @click="clearFilters">Clear</v-btn>
          </v-col>
        </v-row>
      </template>

      <template #item.device_name="{ item }">
        <span class="font-weight-medium">{{ item.device_name ?? item.device }}</span>
      </template>

      <template #item.status="{ item }">
        <v-chip :color="statusColor(item.status)" size="x-small" label>{{ item.status }}</v-chip>
      </template>

      <template #item.created_at="{ item }">
        <span class="text-medium-emphasis text-caption">{{ new Date(item.created_at).toLocaleString() }}</span>
      </template>

      <template #item.acknowledged_by="{ item }">
        <span v-if="item.acknowledged_by">
          {{ item.acknowledged_by }}
          <span v-if="item.acknowledgement_reason" class="text-medium-emphasis text-caption"> — {{ item.acknowledgement_reason }}</span>
        </span>
        <span v-else class="text-medium-emphasis">—</span>
      </template>

      <template #item.diff="{ item }">
        <span class="text-caption text-medium-emphasis">{{ Object.keys(item.diff || {}).join(', ') || '—' }}</span>
      </template>

      <template #item.actions="{ item }">
        <v-btn size="x-small" variant="tonal" class="mr-1" @click="openDiff(item)">View Diff</v-btn>
        <v-btn v-if="item.status === 'new' && reviewedIds.includes(item.id)" size="x-small" variant="tonal" @click="openAcknowledge(item)">Acknowledge</v-btn>
      </template>
    </v-data-table-server>

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
          <DriftDiffViewer
            v-else
            :baseline="selected.baseline_data"
            :current="selected.result_data"
            :volatile-fields="store.volatileFields"
            @rule-created="onRuleCreated"
          />
        </v-card-text>
        <v-card-actions>
          <v-btn v-if="selected.status === 'new'" color="primary" variant="tonal" @click="acknowledgeFromDiff">Acknowledge</v-btn>
          <v-spacer />
          <v-btn @click="diffOpen = false">Close</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Acknowledge dialog -->
    <v-dialog v-model="ackOpen" max-width="460" persistent>
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
import { ref, reactive, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useDriftStore } from '../stores/drift'
import api from '../api'
import DriftDiffViewer from '../components/DriftDiffViewer.vue'

const store = useDriftStore()
const showHelp = ref(false)
const devices = ref([])
const deviceItems = computed(() => devices.value.map(d => ({ title: d.name, value: d.id })))
const filters = reactive({ device: null, status: '' })

const headers = [
  { title: 'Device',         key: 'device_name',     sortable: true  },
  { title: 'Status',         key: 'status',           sortable: true  },
  { title: 'Detected',       key: 'created_at',       sortable: true  },
  { title: 'Acknowledged By',key: 'acknowledged_by',  sortable: false },
  { title: 'Diff Keys',      key: 'diff',             sortable: false },
  { title: 'Actions',        key: 'actions',          sortable: false },
]

// Maps Vuetify column keys to DRF ordering field names
const SORT_FIELD = {
  device_name: 'device__name',
  status:      'status',
  created_at:  'created_at',
}

const tableOptions = ref({ page: 1, itemsPerPage: 25, sortBy: [{ key: 'created_at', order: 'desc' }] })

function buildParams(options = tableOptions.value) {
  const params = {
    page:      options.page,
    page_size: options.itemsPerPage,
  }
  if (filters.device) params.device = filters.device
  if (filters.status) params.status = filters.status
  if (options.sortBy?.length) {
    const { key, order } = options.sortBy[0]
    const field = SORT_FIELD[key] ?? key
    params.ordering = order === 'desc' ? `-${field}` : field
  }
  return params
}

function onTableOptions(options) {
  tableOptions.value = options
  store.fetchEvents(buildParams(options))
}

function resetAndFetch() {
  const opts = { ...tableOptions.value, page: 1 }
  tableOptions.value = opts
  store.fetchEvents(buildParams(opts))
}

function clearFilters() {
  Object.assign(filters, { device: null, status: '' })
  resetAndFetch()
}

function statusColor(status) {
  return {
    new: 'error', acknowledged: 'warning', resolved: 'success',
    success: 'success', failed: 'error', running: 'info',
    pending: 'warning', partial: 'warning', cancelled: 'default',
  }[status] ?? 'default'
}

// ── Diff dialog ───────────────────────────────────────────────────────────────

const reviewedIds = ref([])
const selected = ref(null)
const diffOpen = ref(false)
const diffLoading = ref(false)

async function openDiff(event) {
  if (!reviewedIds.value.includes(event.id)) {
    reviewedIds.value = [...reviewedIds.value, event.id]
  }
  selected.value = { ...event }
  diffOpen.value = true
  diffLoading.value = true
  try {
    const [detailRes] = await Promise.all([
      api.get(`/drift/${event.id}/`),
      store.fetchVolatileFields(),
    ])
    selected.value = detailRes.data
  } finally {
    diffLoading.value = false
  }
}

// ── Acknowledge dialog ────────────────────────────────────────────────────────

function onRuleCreated() {
  // Force re-fetch volatile fields on next open (clears the cache so the new rule is shown)
  store.volatileFields = null
  store.fetchVolatileFields()
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

async function acknowledgeFromDiff() {
  const event = selected.value
  diffOpen.value = false
  await nextTick()
  setTimeout(() => openAcknowledge(event), 150)
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

// ── Lifecycle ─────────────────────────────────────────────────────────────────

onMounted(async () => {
  const { data } = await api.get('/devices/', { params: { page_size: 500 } })
  devices.value = data.results ?? data
  // Initial fetch — onTableOptions will also fire from v-data-table-server mount,
  // but fetch here ensures devices are loaded first.
  store.startPolling()
})

onUnmounted(() => {
  store.stopPolling()
})
</script>
