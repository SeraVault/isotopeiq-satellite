<template>
  <v-app>
    <template v-if="isLoggedIn">
      <!-- Sidebar -->
      <v-navigation-drawer permanent width="220" color="secondary">
        <!-- Brand -->
        <div class="px-4 py-4 d-flex align-center ga-2 border-b border-white-darken-4">
          <v-icon color="primary" size="24">mdi-hexagon-outline</v-icon>
          <span class="text-white font-weight-bold text-body-1">IsotopeIQ</span>
        </div>

        <v-list density="compact" nav class="pt-2">
          <v-list-subheader class="text-uppercase text-caption" style="color:#5a6a8a">Overview</v-list-subheader>
          <v-list-item to="/dashboard" prepend-icon="mdi-view-dashboard-outline" title="Dashboard" active-color="primary" />

          <v-list-subheader class="text-uppercase text-caption" style="color:#5a6a8a">Infrastructure</v-list-subheader>
          <v-list-item to="/devices" prepend-icon="mdi-server" title="Devices" active-color="primary" />
          <v-list-item to="/scripts" prepend-icon="mdi-code-braces" title="Scripts" active-color="primary" />
          <v-list-item to="/policies" prepend-icon="mdi-shield-check-outline" title="Policies" active-color="primary" />

          <v-list-subheader class="text-uppercase text-caption" style="color:#5a6a8a">Operations</v-list-subheader>
          <v-list-item to="/jobs" prepend-icon="mdi-play-circle-outline" title="Job Monitor" active-color="primary">
            <template #append>
              <v-badge v-if="runningJobs > 0" :content="runningJobs" color="primary" inline />
            </template>
          </v-list-item>
          <v-list-item to="/drift" prepend-icon="mdi-lightning-bolt" title="Drift" active-color="primary">
            <template #append>
              <v-badge v-if="newDrift > 0" :content="newDrift" color="error" inline />
            </template>
          </v-list-item>
          <v-list-item to="/baselines" prepend-icon="mdi-database-check-outline" title="Baselines" active-color="primary" />

          <v-list-subheader class="text-uppercase text-caption" style="color:#5a6a8a">System</v-list-subheader>
          <v-list-item to="/audit" prepend-icon="mdi-format-list-bulleted" title="Audit Log" active-color="primary" />
          <v-list-item to="/retention" prepend-icon="mdi-clock-outline" title="Retention" active-color="primary" />
        </v-list>

        <!-- Footer -->
        <template #append>
          <v-divider />
          <div class="d-flex align-center justify-space-between px-4 py-3">
            <span class="text-caption" style="color:#a0aec0">{{ username }}</span>
            <v-btn icon="mdi-logout" variant="text" size="small" color="error" @click="logout" title="Sign out" />
          </div>
        </template>
      </v-navigation-drawer>
    </template>

    <!-- Main content -->
    <v-main :style="isLoggedIn ? '' : 'padding: 0'">
      <v-container fluid class="pa-6">
        <router-view />
      </v-container>
    </v-main>
  </v-app>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import api, { isLoggedIn, clearTokens } from './api'

const router   = useRouter()
const username = ref(localStorage.getItem('username') || '')
const runningJobs = ref(0)
const newDrift    = ref(0)

let pollTimer = null

async function pollBadges() {
  if (!isLoggedIn.value) return
  try {
    const [jobsRes, driftRes] = await Promise.all([
      api.get('/jobs/',  { params: { status: 'running', page_size: 1 } }),
      api.get('/drift/', { params: { status: 'new',     page_size: 1 } }),
    ])
    runningJobs.value = jobsRes.data.count  ?? 0
    newDrift.value    = driftRes.data.count ?? 0
  } catch { /* interceptor handles token expiry */ }
}

watch(isLoggedIn, (val) => {
  if (!val) {
    if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
    router.push('/login')
  }
})

onMounted(() => {
  if (isLoggedIn.value) {
    pollBadges()
    pollTimer = setInterval(pollBadges, 15000)
  }
})

onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })

function logout() {
  clearTokens()
  router.push('/login')
}
</script>
