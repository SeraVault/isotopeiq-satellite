<template>
  <v-app>
    <!-- Sidebar -->
    <v-navigation-drawer v-if="isLoggedIn" v-model="drawer" :rail="rail" permanent width="220" color="secondary">
      <!-- Brand -->
      <div class="px-3 py-4 d-flex align-center ga-2 border-b border-white-darken-4">
        <v-icon color="primary" size="26">mdi-hexagon-outline</v-icon>
        <div v-if="!rail" class="d-flex flex-column ml-1" style="line-height:1.15">
          <span class="text-white font-weight-bold" style="font-size:0.95rem;letter-spacing:0.02em">IsotopeIQ</span>
          <span style="font-size:0.7rem;color:#7a9cc4;letter-spacing:0.08em;text-transform:uppercase">Satellite</span>
        </div>
        <v-btn
          v-if="!rail"
          icon="mdi-chevron-left"
          variant="text"
          size="small"
          color="white"
          class="ml-auto"
          @click="rail = true"
        />
      </div>

      <!-- Expand button when collapsed -->
      <div v-if="rail" class="d-flex justify-center pt-2">
        <v-btn icon="mdi-chevron-right" variant="text" size="small" color="white" @click="rail = false" />
      </div>

      <v-list density="compact" nav class="pt-2">
        <v-list-subheader v-if="!rail" class="text-uppercase text-caption" style="color:#5a6a8a">Overview</v-list-subheader>
        <v-list-item to="/dashboard" prepend-icon="mdi-view-dashboard-outline" title="Dashboard" color="primary" />

        <v-list-subheader v-if="!rail" class="text-uppercase text-caption" style="color:#5a6a8a">Configuration</v-list-subheader>
        <v-list-item to="/devices" prepend-icon="mdi-server" title="Devices" color="primary" />
        <v-list-item to="/policies" prepend-icon="mdi-shield-check-outline" title="Policies" color="primary" />
        <v-list-item to="/scripts" prepend-icon="mdi-code-braces" title="Scripts" color="primary" />
        <v-list-item to="/agent-download" prepend-icon="mdi-download-box-outline" title="Agent Download" color="primary" />

        <v-list-subheader v-if="!rail" class="text-uppercase text-caption" style="color:#5a6a8a">Operations</v-list-subheader>
        <v-list-item to="/jobs" prepend-icon="mdi-play-circle-outline" color="primary">
          <template #title>
            <span>Job Monitor</span>
            <v-chip v-if="runningJobs > 0" size="x-small" color="primary" class="ml-2">{{ runningJobs }}</v-chip>
          </template>
        </v-list-item>
        <v-list-item to="/drift" prepend-icon="mdi-lightning-bolt" color="primary">
          <template #title>
            <span>Drift</span>
            <v-chip v-if="newDrift > 0" size="x-small" color="error" class="ml-2">{{ newDrift }}</v-chip>
          </template>
        </v-list-item>
        <v-list-item to="/baselines" prepend-icon="mdi-database-check-outline" title="Baselines" color="primary" />

        <v-list-subheader v-if="!rail" class="text-uppercase text-caption" style="color:#5a6a8a">Administration</v-list-subheader>
        <v-list-item to="/drift-exclusions" prepend-icon="mdi-tune" title="Drift Exclusions" color="primary" />
        <v-list-item to="/users" prepend-icon="mdi-account-group-outline" title="Users" color="primary" />
        <v-list-item to="/audit" prepend-icon="mdi-format-list-bulleted" title="Audit Log" color="primary" />
        <v-list-item to="/system-settings" prepend-icon="mdi-cog-outline" title="System Settings" color="primary" />
      </v-list>

      <!-- Footer -->
      <template #append>
        <v-divider />
        <div class="d-flex align-center justify-space-between px-3 py-3">
          <span v-if="!rail" class="text-caption" style="color:#a0aec0">{{ username }}</span>
          <v-btn icon="mdi-logout" variant="text" size="small" color="error" @click="logout" title="Sign out" />
        </div>
      </template>
    </v-navigation-drawer>

    <!-- Main content -->
    <v-main :style="isLoggedIn ? '' : 'padding: 0'">
      <router-view v-if="isEditorRoute" />
      <v-container v-else fluid class="pa-6">
        <router-view />
      </v-container>
    </v-main>
  </v-app>
</template>

<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { isLoggedIn, clearTokens } from './api'
import { useDashboardStore } from './stores/dashboard'

const router   = useRouter()
const route    = useRoute()
const isEditorRoute = computed(() => route.path === '/scripts/new' || route.path.endsWith('/edit'))
const username = ref(localStorage.getItem('username') || '')
const dashboardStore = useDashboardStore()

const drawer = ref(true)
const rail   = ref(false)
const isSuperuser = ref(!!localStorage.getItem('is_superuser'))

// Keep isSuperuser in sync if localStorage changes (e.g. after re-login)
window.addEventListener('storage', () => {
  isSuperuser.value = !!localStorage.getItem('is_superuser')
})

// All badges derive from the central dashboard store.
// Immediate mutations (WS messages, acknowledge, resolve) patch dashboardStore.stats directly.
const runningJobs = computed(() => dashboardStore.stats.running_jobs)
const newDrift    = computed(() => dashboardStore.stats.new_drift)

let pollTimer = null

async function pollBadges() {
  if (!isLoggedIn.value) return
  // Single call — refreshes all counts, badges, and dashboard panels.
  dashboardStore.refresh()
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
    pollTimer = setInterval(pollBadges, 3000)
  }
})

onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })

function logout() {
  clearTokens()
  router.push('/login')
}
</script>
