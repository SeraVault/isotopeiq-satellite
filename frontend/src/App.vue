<template>
  <div id="app" :class="isLoggedIn ? 'layout' : 'layout-full'">

    <!-- Sidebar -->
    <aside v-if="isLoggedIn" class="sidebar">
      <div class="sidebar-brand">
        <span class="brand-icon">⬡</span>
        <span class="brand-name">IsotopeIQ</span>
      </div>

      <nav class="sidebar-nav">
        <div class="nav-section-label">Overview</div>
        <router-link to="/dashboard" class="nav-item">
          <span class="nav-icon">▦</span> Dashboard
        </router-link>

        <div class="nav-section-label">Infrastructure</div>
        <router-link to="/devices" class="nav-item">
          <span class="nav-icon">⬡</span> Devices
        </router-link>
        <router-link to="/scripts" class="nav-item">
          <span class="nav-icon">⌥</span> Scripts
        </router-link>
        <router-link to="/policies" class="nav-item">
          <span class="nav-icon">≡</span> Policies
        </router-link>

        <div class="nav-section-label">Operations</div>
        <router-link to="/jobs" class="nav-item">
          <span class="nav-icon">▶</span> Job Monitor
          <span v-if="runningJobs > 0" class="nav-badge">{{ runningJobs }}</span>
        </router-link>
        <router-link to="/drift" class="nav-item">
          <span class="nav-icon">⚡</span> Drift
          <span v-if="newDrift > 0" class="nav-badge nav-badge-alert">{{ newDrift }}</span>
        </router-link>
        <router-link to="/baselines" class="nav-item">
          <span class="nav-icon">◎</span> Baselines
        </router-link>

        <div class="nav-section-label">System</div>
        <router-link to="/audit" class="nav-item">
          <span class="nav-icon">☰</span> Audit Log
        </router-link>
        <router-link to="/retention" class="nav-item">
          <span class="nav-icon">⏱</span> Retention
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <span class="sidebar-user">{{ username }}</span>
        <button class="logout-btn" @click="logout" title="Sign out">⏻</button>
      </div>
    </aside>

    <!-- Main content -->
    <main class="main-content">
      <router-view />
    </main>

  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import api, { isLoggedIn, clearTokens } from './api'

const router = useRouter()
const username = ref(localStorage.getItem('username') || '')
const runningJobs = ref(0)
const newDrift = ref(0)

let pollTimer = null

async function pollBadges() {
  if (!isLoggedIn.value) return
  try {
    const [jobsRes, driftRes] = await Promise.all([
      api.get('/jobs/', { params: { status: 'running' } }),
      api.get('/drift/', { params: { status: 'new' } }),
    ])
    const jobs = jobsRes.data.results ?? jobsRes.data
    const drift = driftRes.data.results ?? driftRes.data
    runningJobs.value = Array.isArray(jobs) ? jobs.length : 0
    newDrift.value = Array.isArray(drift) ? drift.length : 0
  } catch {
    // silently ignore — if token expired, the interceptor calls clearTokens()
    // which triggers the watch below to stop polling and redirect
  }
}

// When the interceptor clears tokens (refresh failed), stop polling and redirect
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

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})

function logout() {
  clearTokens()
  router.push('/login')
}
</script>

<style>
/* ── Reset ───────────────────────────────────────────────────────────────── */
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: system-ui, -apple-system, sans-serif; background: #f0f2f5; color: #222; }

/* ── Layout ──────────────────────────────────────────────────────────────── */
.layout {
  display: grid;
  grid-template-columns: 220px 1fr;
  min-height: 100vh;
}
.layout-full { min-height: 100vh; }

/* ── Sidebar ─────────────────────────────────────────────────────────────── */
.sidebar {
  background: #16213e;
  color: #c8d0e0;
  display: flex;
  flex-direction: column;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
}
.sidebar-brand {
  display: flex;
  align-items: center;
  gap: .6rem;
  padding: 1.25rem 1.25rem 1rem;
  font-size: 1.1rem;
  font-weight: 700;
  color: #fff;
  border-bottom: 1px solid rgba(255,255,255,.08);
}
.brand-icon { font-size: 1.4rem; color: #4fc3f7; }
.sidebar-nav { flex: 1; padding: .75rem 0; }
.nav-section-label {
  font-size: .7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: .08em;
  color: #5a6a8a;
  padding: 1rem 1.25rem .3rem;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: .6rem;
  padding: .5rem 1.25rem;
  color: #a0aec0;
  text-decoration: none;
  font-size: .9rem;
  border-radius: 0;
  transition: background .15s, color .15s;
  position: relative;
}
.nav-item:hover { background: rgba(255,255,255,.06); color: #e2e8f0; }
.nav-item.router-link-active {
  background: rgba(79,195,247,.12);
  color: #4fc3f7;
  border-left: 3px solid #4fc3f7;
}
.nav-icon { width: 1.1rem; text-align: center; font-style: normal; opacity: .7; }
.nav-badge {
  margin-left: auto;
  background: #4fc3f7;
  color: #16213e;
  font-size: .7rem;
  font-weight: 700;
  padding: .1rem .45rem;
  border-radius: 999px;
}
.nav-badge-alert { background: #fc8181; color: #fff; }
.sidebar-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: .85rem 1.25rem;
  border-top: 1px solid rgba(255,255,255,.08);
  font-size: .85rem;
}
.sidebar-user { color: #a0aec0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.logout-btn {
  background: transparent;
  border: none;
  color: #5a6a8a;
  cursor: pointer;
  font-size: 1.1rem;
  padding: .2rem;
  line-height: 1;
}
.logout-btn:hover { color: #fc8181; background: transparent; }

/* ── Main content ────────────────────────────────────────────────────────── */
.main-content { padding: 2rem; overflow-y: auto; }

/* ── Typography ──────────────────────────────────────────────────────────── */
h1 { margin-bottom: 1.25rem; font-size: 1.5rem; }
h2 { margin-bottom: 1rem; font-size: 1.2rem; }

/* ── Cards ───────────────────────────────────────────────────────────────── */
.card {
  background: #fff;
  border-radius: 8px;
  padding: 1.25rem;
  box-shadow: 0 1px 3px rgba(0,0,0,.08);
}

/* ── Tables ──────────────────────────────────────────────────────────────── */
table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
th, td { padding: .65rem 1rem; text-align: left; border-bottom: 1px solid #f0f0f0; }
th { background: #fafafa; font-weight: 600; font-size: .85rem; color: #555; text-transform: uppercase; letter-spacing: .04em; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #fafcff; }

/* ── Buttons ─────────────────────────────────────────────────────────────── */
button { padding: .38rem .85rem; border: 1px solid #d0d0d0; border-radius: 5px; cursor: pointer; background: #fff; font-size: .875rem; transition: background .15s; margin-right: .3rem; }
button:hover { background: #f0f2f5; }
button.btn-primary { background: #4fc3f7; border-color: #4fc3f7; color: #fff; }
button.btn-primary:hover { background: #29b6f6; }
button.btn-danger { background: #fff; border-color: #fc8181; color: #c00; }
button.btn-danger:hover { background: #fff5f5; }

/* ── Modals ──────────────────────────────────────────────────────────────── */
.modal { position: fixed; inset: 0; background: rgba(0,0,0,.45); display: flex; align-items: center; justify-content: center; z-index: 200; padding: 1rem; }
.modal-box { background: #fff; border-radius: 10px; padding: 1.75rem; width: 100%; max-height: 90vh; overflow-y: auto; box-shadow: 0 8px 32px rgba(0,0,0,.22); }
.modal-box.modal-sm { max-width: 420px; }
.modal-box.modal-md { max-width: 650px; }
.modal-box.modal-lg { max-width: 900px; }
.modal-box.modal-xl { max-width: 1200px; }

/* ── Forms ───────────────────────────────────────────────────────────────── */
form label, .form-label { display: block; margin-bottom: .75rem; font-size: .9rem; }
form input, form select, form textarea,
.form-input { display: block; width: 100%; margin-top: .25rem; padding: .45rem .65rem; border: 1px solid #d0d0d0; border-radius: 5px; font-size: .9rem; }
form input:focus, form select:focus, form textarea:focus { outline: none; border-color: #4fc3f7; box-shadow: 0 0 0 2px rgba(79,195,247,.2); }

/* ── Badges ──────────────────────────────────────────────────────────────── */
.badge { display: inline-block; padding: .18rem .55rem; border-radius: 999px; font-size: .78rem; font-weight: 600; }
.badge-success, .badge-resolved { background: #d4edda; color: #155724; }
.badge-failed  { background: #f8d7da; color: #721c24; }
.badge-running { background: #d1ecf1; color: #0c5460; }
.badge-pending { background: #fff3cd; color: #856404; }
.badge-new     { background: #f8d7da; color: #721c24; }
.badge-acknowledged { background: #ffeeba; color: #856404; }
.badge-partial { background: #ffeeba; color: #856404; }
.badge-cancelled { background: #e2e8f0; color: #4a5568; }

/* ── Code / Pre ──────────────────────────────────────────────────────────── */
pre { background: #1e1e1e; color: #d4d4d4; padding: 1rem; border-radius: 6px; overflow: auto; font-size: .82rem; line-height: 1.5; }

/* ── Misc ────────────────────────────────────────────────────────────────── */
.error { color: #c00; font-size: .875rem; }
.text-muted { color: #888; font-size: .85rem; }
.tabs { display: flex; gap: 0; margin-bottom: 1.25rem; border-bottom: 2px solid #e8e8e8; }
.tab { padding: .5rem 1.1rem; cursor: pointer; border-bottom: 2px solid transparent; margin-bottom: -2px; font-size: .9rem; color: #666; }
.tab.active { border-bottom-color: #4fc3f7; color: #16213e; font-weight: 600; }
</style>
