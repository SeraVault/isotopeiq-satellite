<template>
  <div>
    <div class="text-h5 font-weight-bold mb-6">Dashboard</div>

    <!-- Stat cards -->
    <v-row class="mb-6">
      <v-col v-for="stat in statCards" :key="stat.label" cols="12" sm="6" md="3">
        <v-card rounded="lg" elevation="2" :style="`border-left: 4px solid rgb(var(--v-theme-${stat.color}))`">
          <v-card-text class="pa-4">
            <div class="d-flex align-center justify-space-between">
              <div>
                <div class="text-h3 font-weight-bold" :class="`text-${stat.color}`">{{ stat.value }}</div>
                <div class="text-body-2 text-medium-emphasis mt-1">{{ stat.label }}</div>
              </div>
              <v-icon :icon="stat.icon" :color="stat.color" size="44" style="opacity: 0.25" />
            </div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Main row: Drift alerts + Recent jobs -->
    <v-row class="mb-4">
      <!-- Drift alerts -->
      <v-col cols="12" md="6">
        <v-card rounded="lg" elevation="1" height="100%">
          <v-card-title class="d-flex justify-space-between align-center pa-4 pb-2">
            <div class="d-flex align-center">
              <v-icon icon="mdi-alert-circle-outline" color="error" size="18" class="mr-2" />
              <span class="text-body-1 font-weight-bold">Drift Alerts</span>
            </div>
            <router-link to="/drift" class="text-primary text-decoration-none text-caption">View all →</router-link>
          </v-card-title>
          <v-card-text class="pa-0">
            <div v-if="store.loading" class="pa-4 text-medium-emphasis">Loading…</div>
            <div v-else-if="store.driftEvents.length === 0" class="pa-8 text-center text-medium-emphasis">
              <v-icon icon="mdi-check-circle-outline" color="success" size="48" class="mb-3 d-block mx-auto" />
              No unresolved drift detected.
            </div>
            <v-table v-else density="compact">
              <thead>
                <tr>
                  <th>Device</th><th>Status</th><th>Detected</th><th>Keys</th><th></th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="e in store.driftEvents" :key="e.id">
                  <td class="font-weight-medium">{{ e.device_name ?? e.device }}</td>
                  <td><v-chip :color="statusColor(e.status)" size="x-small" label>{{ e.status }}</v-chip></td>
                  <td class="text-medium-emphasis text-caption">{{ fmt(e.created_at) }}</td>
                  <td class="text-medium-emphasis text-caption">{{ diffKeys(e.diff) }}</td>
                  <td>
                    <router-link to="/drift" class="text-primary text-caption text-decoration-none">Review →</router-link>
                  </td>
                </tr>
              </tbody>
            </v-table>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- Recent jobs with pagination -->
      <v-col cols="12" md="6">
        <v-card rounded="lg" elevation="1" height="100%">
          <v-card-title class="d-flex justify-space-between align-center pa-4 pb-2">
            <div class="d-flex align-center">
              <v-icon icon="mdi-clipboard-list-outline" color="primary" size="18" class="mr-2" />
              <span class="text-body-1 font-weight-bold">Recent Jobs</span>
            </div>
            <router-link to="/jobs" class="text-primary text-decoration-none text-caption">View all →</router-link>
          </v-card-title>
          <v-card-text class="pa-0">
            <div v-if="store.loading" class="pa-4 text-medium-emphasis">Loading…</div>
            <div v-else-if="store.recentJobs.length === 0" class="pa-8 text-center text-medium-emphasis">
              <v-icon icon="mdi-briefcase-outline" color="grey" size="48" class="mb-3 d-block mx-auto" />
              No recent jobs.
            </div>
            <template v-else>
              <v-table density="compact">
                <thead>
                  <tr><th>#</th><th>Device</th><th>Policy</th><th>Status</th><th>Started</th></tr>
                </thead>
                <tbody>
                  <tr v-for="j in pagedJobs" :key="j.id">
                    <td class="text-caption text-medium-emphasis">#{{ j.id }}</td>
                    <td class="font-weight-medium">{{ j.device_name ?? (j.device ? `Device ${j.device}` : '—') }}</td>
                    <td class="text-caption">{{ j.policy_name ?? '—' }}</td>
                    <td><v-chip :color="statusColor(j.status)" size="x-small" label>{{ j.status }}</v-chip></td>
                    <td class="text-medium-emphasis text-caption">{{ j.started_at ? fmt(j.started_at) : '—' }}</td>
                  </tr>
                </tbody>
              </v-table>
              <div class="d-flex align-center justify-space-between px-3 py-1" style="border-top: 1px solid rgba(var(--v-border-color), var(--v-border-opacity))">
                <span class="text-caption text-medium-emphasis">{{ jobPageStart }}–{{ jobPageEnd }} of {{ store.recentJobs.length }}</span>
                <div>
                  <v-btn icon="mdi-chevron-left"  size="x-small" variant="text" :disabled="jobPage === 1"           @click="jobPage--" />
                  <v-btn icon="mdi-chevron-right" size="x-small" variant="text" :disabled="jobPage >= jobPageCount" @click="jobPage++" />
                </div>
              </div>
            </template>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Second row: Drift by device + Job results breakdown + Quick actions -->
    <v-row>
      <!-- Baseline freshness / Last Scanned -->
      <v-col cols="12" md="4">
        <v-card rounded="lg" elevation="1" height="100%">
          <v-card-title class="d-flex justify-space-between align-center pa-4 pb-2">
            <div class="d-flex align-center">
              <v-icon icon="mdi-clock-outline" color="warning" size="18" class="mr-2" />
              <span class="text-body-1 font-weight-bold">Last Scanned</span>
            </div>
            <router-link to="/baselines" class="text-primary text-decoration-none text-caption">View all →</router-link>
          </v-card-title>
          <v-card-text class="pa-0">
            <div v-if="store.loading" class="pa-4 text-medium-emphasis">Loading…</div>
            <div v-else-if="store.baselines.length === 0" class="pa-6 text-center text-medium-emphasis text-caption">
              <v-icon icon="mdi-database-off-outline" color="grey" size="36" class="mb-2 d-block mx-auto" />
              No baselines established yet.
            </div>
            <v-list v-else density="compact" class="py-1">
              <v-list-item
                v-for="b in stalestBaselines"
                :key="b.device"
                :subtitle="fmtAge(b.established_at)"
              >
                <template #title>
                  <span class="text-body-2 font-weight-medium">{{ b.device_name }}</span>
                </template>
                <template #append>
                  <v-chip size="x-small" :color="freshnessColor(b.established_at)" label>{{ fmtRelative(b.established_at) }}</v-chip>
                </template>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- Recent job results breakdown -->
      <v-col cols="12" md="4">
        <v-card rounded="lg" elevation="1" height="100%">
          <v-card-title class="d-flex align-center pa-4 pb-2">
            <v-icon icon="mdi-poll" color="primary" size="18" class="mr-2" />
            <span class="text-body-1 font-weight-bold">Recent Job Results</span>
          </v-card-title>
          <v-card-text v-if="store.loading" class="pa-4 text-medium-emphasis">Loading…</v-card-text>
          <v-card-text v-else-if="store.recentJobs.length === 0" class="pa-6 text-center text-medium-emphasis text-caption">No job data.</v-card-text>
          <v-card-text v-else class="px-4 pt-2 pb-4">
            <div v-for="s in jobStatusBreakdown" :key="s.status" class="mb-3">
              <div class="d-flex justify-space-between text-caption mb-1">
                <span class="font-weight-medium text-capitalize">{{ s.status }}</span>
                <span class="text-medium-emphasis">{{ s.count }} / {{ store.recentJobs.length }}</span>
              </div>
              <v-progress-linear
                :model-value="(s.count / store.recentJobs.length) * 100"
                :color="statusColor(s.status)"
                rounded
                height="6"
                bg-color="surface-variant"
              />
            </div>
          </v-card-text>
        </v-card>
      </v-col>

      <!-- Quick actions -->
      <v-col cols="12" md="4">
        <v-card rounded="lg" elevation="1" height="100%">
          <v-card-title class="d-flex align-center pa-4 pb-2">
            <v-icon icon="mdi-lightning-bolt" color="secondary" size="18" class="mr-2" />
            <span class="text-body-1 font-weight-bold">Quick Actions</span>
          </v-card-title>
          <v-card-text class="d-flex flex-column gap-3 pa-4 pt-2">
            <v-btn to="/devices" prepend-icon="mdi-plus" variant="tonal" color="primary" size="small" block>Add Device</v-btn>
            <v-btn to="/policies" prepend-icon="mdi-file-document-plus-outline" variant="tonal" color="primary" size="small" block>New Policy</v-btn>
            <v-btn
              v-if="store.stats.new_drift > 0"
              to="/drift"
              prepend-icon="mdi-check-all"
              variant="tonal"
              color="error"
              size="small"
              block
            >
              Review {{ store.stats.new_drift }} Drift Alert{{ store.stats.new_drift !== 1 ? 's' : '' }}
            </v-btn>
            <v-btn
              v-else
              to="/baselines"
              prepend-icon="mdi-database-check-outline"
              variant="tonal"
              color="secondary"
              size="small"
              block
            >
              View Baselines
            </v-btn>
            <v-btn to="/jobs" prepend-icon="mdi-clipboard-list-outline" variant="tonal" color="secondary" size="small" block>View All Jobs</v-btn>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>

<script setup>
import { computed, ref, onMounted } from 'vue'
import { useDashboardStore } from '../stores/dashboard'

const store = useDashboardStore()

const statCards = computed(() => [
  { label: 'Managed Devices',  value: store.stats.devices,      color: 'primary',   icon: 'mdi-server-network' },
  { label: 'Active Policies',  value: store.stats.policies,     color: 'secondary', icon: 'mdi-file-document-outline' },
  { label: 'Running Jobs',     value: store.stats.running_jobs, color: store.stats.running_jobs > 0 ? 'warning' : 'success', icon: 'mdi-play-circle-outline' },
  { label: 'Unresolved Drift', value: store.stats.new_drift,    color: store.stats.new_drift > 0    ? 'error'   : 'success', icon: 'mdi-alert-circle-outline' },
])

// Jobs pagination
const jobPage     = ref(1)
const jobsPerPage = 5
const pagedJobs   = computed(() => store.recentJobs.slice((jobPage.value - 1) * jobsPerPage, jobPage.value * jobsPerPage))
const jobPageCount = computed(() => Math.ceil(store.recentJobs.length / jobsPerPage))
const jobPageStart = computed(() => (jobPage.value - 1) * jobsPerPage + 1)
const jobPageEnd   = computed(() => Math.min(jobPage.value * jobsPerPage, store.recentJobs.length))

// Derived: stalest baselines first (most overdue scan at the top), limited to 6
const stalestBaselines = computed(() =>
  [...store.baselines].sort((a, b) => new Date(a.established_at) - new Date(b.established_at)).slice(0, 6)
)

// Derived: breakdown of recent job statuses
const jobStatusBreakdown = computed(() => {
  const counts = {}
  for (const j of store.recentJobs) {
    counts[j.status] = (counts[j.status] ?? 0) + 1
  }
  return Object.entries(counts)
    .map(([status, count]) => ({ status, count }))
    .sort((a, b) => b.count - a.count)
})

function fmt(iso) { return new Date(iso).toLocaleString() }

function fmtAge(iso) { return `Last scanned ${fmtRelative(iso)}` }

function fmtRelative(iso) {
  const diffMs = Date.now() - new Date(iso).getTime()
  const days = Math.floor(diffMs / 86400000)
  if (days === 0) return 'Today'
  if (days === 1) return '1 day ago'
  if (days < 30)  return `${days} days ago`
  const months = Math.floor(days / 30)
  return months === 1 ? '1 month ago' : `${months} months ago`
}

function freshnessColor(iso) {
  const days = (Date.now() - new Date(iso).getTime()) / 86400000
  if (days <= 1)  return 'success'
  if (days <= 7)  return 'info'
  if (days <= 30) return 'warning'
  return 'error'
}

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

onMounted(() => store.refresh())
</script>
