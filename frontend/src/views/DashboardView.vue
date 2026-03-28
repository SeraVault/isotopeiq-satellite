<template>
  <div>
    <div class="text-h5 font-weight-bold mb-5">Dashboard</div>

    <!-- Stat cards -->
    <v-row class="mb-5">
      <v-col v-for="stat in statCards" :key="stat.label" cols="12" sm="6" md="3">
        <v-card :border="`${stat.alert ? 'error' : 'primary'} md`" rounded="lg" elevation="1">
          <v-card-text class="pa-4">
            <div class="text-h4 font-weight-bold" :class="stat.alert ? 'text-error' : 'text-primary'">{{ stat.value }}</div>
            <div class="text-body-2 text-medium-emphasis mt-1">{{ stat.label }}</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <v-row>
      <!-- Drift alerts -->
      <v-col cols="12" md="6">
        <v-card rounded="lg" elevation="1">
          <v-card-title class="d-flex justify-space-between align-center pa-4 pb-2">
            <span class="text-body-1 font-weight-bold">Drift Alerts</span>
            <router-link to="/drift" class="text-primary text-decoration-none text-caption">View all →</router-link>
          </v-card-title>
          <v-card-text class="pa-0">
            <div v-if="loadingDrift" class="pa-4 text-medium-emphasis">Loading…</div>
            <div v-else-if="driftEvents.length === 0" class="pa-6 text-center text-medium-emphasis">No unresolved drift detected.</div>
            <v-table v-else density="compact">
              <thead>
                <tr>
                  <th>Device</th><th>Status</th><th>Detected</th><th>Keys</th><th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="e in driftEvents" :key="e.id">
                  <td>{{ e.device_name ?? e.device }}</td>
                  <td><v-chip :color="statusColor(e.status)" size="x-small" label>{{ e.status }}</v-chip></td>
                  <td class="text-medium-emphasis text-caption">{{ fmt(e.created_at) }}</td>
                  <td class="text-medium-emphasis text-caption">{{ diffKeys(e.diff) }}</td>
                  <td>
                    <v-btn v-if="e.status === 'new'" size="x-small" variant="tonal" @click="openAcknowledge(e)">Acknowledge</v-btn>
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- Recent jobs -->
      <v-col cols="12" md="6">
        <v-card rounded="lg" elevation="1">
          <v-card-title class="d-flex justify-space-between align-center pa-4 pb-2">
            <span class="text-body-1 font-weight-bold">Recent Jobs</span>
            <router-link to="/jobs" class="text-primary text-decoration-none text-caption">View all →</router-link>
          </v-card-title>
          <v-card-text class="pa-0">
            <div v-if="loadingJobs" class="pa-4 text-medium-emphasis">Loading…</div>
            <div v-else-if="recentJobs.length === 0" class="pa-6 text-center text-medium-emphasis">No recent jobs.</div>
            <v-table v-else density="compact">
              <thead>
                <tr><th>#</th><th>Policy</th><th>Status</th><th>Started</th></tr>
              </thead>
              <tbody>
                <tr v-for="j in recentJobs" :key="j.id">
                  <td>#{{ j.id }}</td>
                  <td>{{ j.policy_name ?? j.policy ?? '—' }}</td>
                  <td><v-chip :color="statusColor(j.status)" size="x-small" label>{{ j.status }}</v-chip></td>
                  <td class="text-medium-emphasis text-caption">{{ j.started_at ? fmt(j.started_at) : '—' }}</td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Acknowledge dialog -->
    <v-dialog v-model="ackDialog" max-width="460">
      <v-card rounded="lg">
        <v-card-title>Acknowledge Drift</v-card-title>
        <v-card-subtitle v-if="acknowledging">Device: {{ acknowledging.device_name ?? acknowledging.device }}</v-card-subtitle>
        <v-card-text>
          <v-alert v-if="ackError" type="error" variant="tonal" density="compact" class="mb-3">{{ ackError }}</v-alert>
          <v-textarea v-model="ackReason" label="Reason *" rows="4" placeholder="Explain why this drift is expected or acceptable…" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="ackDialog = false">Cancel</v-btn>
          <v-btn color="primary" :loading="ackSaving" @click="submitAcknowledge">Acknowledge</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api'

const stats        = ref({ devices: 0, policies: 0, running_jobs: 0, new_drift: 0 })
const driftEvents  = ref([])
const recentJobs   = ref([])
const loadingDrift = ref(true)
const loadingJobs  = ref(true)

const acknowledging = ref(null)
const ackDialog     = ref(false)
const ackReason     = ref('')
const ackError      = ref('')
const ackSaving     = ref(false)

const statCards = computed(() => [
  { label: 'Devices',          value: stats.value.devices,      alert: false },
  { label: 'Policies',         value: stats.value.policies,     alert: false },
  { label: 'Running Jobs',     value: stats.value.running_jobs, alert: stats.value.running_jobs > 0 },
  { label: 'Unresolved Drift', value: stats.value.new_drift,    alert: stats.value.new_drift > 0 },
])

function fmt(iso) { return new Date(iso).toLocaleString() }

function diffKeys(diff) {
  if (!diff) return '—'
  const keys = Object.keys(diff)
  if (keys.length === 0) return '—'
  return keys.slice(0, 3).join(', ') + (keys.length > 3 ? ` +${keys.length - 3}` : '')
}

function statusColor(status) {
  return { success: 'success', resolved: 'success', failed: 'error', running: 'info',
           pending: 'warning', new: 'error', acknowledged: 'warning', partial: 'warning',
           cancelled: 'default' }[status] ?? 'default'
}

function openAcknowledge(event) {
  acknowledging.value = event
  ackReason.value = ''
  ackError.value  = ''
  ackDialog.value = true
}

async function submitAcknowledge() {
  if (!ackReason.value.trim()) { ackError.value = 'A reason is required.'; return }
  ackSaving.value = true
  ackError.value  = ''
  try {
    await api.post(`/drift/${acknowledging.value.id}/acknowledge/`, { reason: ackReason.value.trim() })
    acknowledging.value.status = 'acknowledged'
    stats.value.new_drift = Math.max(0, stats.value.new_drift - 1)
    ackDialog.value = false
  } catch (e) {
    ackError.value = e.response?.data?.error ?? 'Failed to acknowledge.'
  } finally {
    ackSaving.value = false
  }
}

onMounted(async () => {
  const [devRes, polRes, runRes, driftRes, jobsRes] = await Promise.all([
    api.get('/devices/',  { params: { page_size: 1 } }),
    api.get('/policies/', { params: { page_size: 1 } }),
    api.get('/jobs/',     { params: { status: 'running', page_size: 1 } }),
    api.get('/drift/',    { params: { status: 'new', page_size: 50 } }),
    api.get('/jobs/',     { params: { page_size: 10 } }),
  ])

  stats.value = {
    devices:      devRes.data.count  ?? 0,
    policies:     polRes.data.count  ?? 0,
    running_jobs: runRes.data.count  ?? 0,
    new_drift:    driftRes.data.count ?? 0,
  }

  driftEvents.value  = driftRes.data.results ?? driftRes.data ?? []
  recentJobs.value   = jobsRes.data.results  ?? jobsRes.data  ?? []
  loadingDrift.value = false
  loadingJobs.value  = false
})
</script>
