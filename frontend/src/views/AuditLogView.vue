<template>
  <div>
    <h1>Audit Log</h1>

    <!-- Filters -->
    <div style="display:flex;flex-wrap:wrap;gap:.75rem;margin-bottom:1rem;align-items:flex-end">
      <label>
        Username
        <input v-model="filters.username" placeholder="Filter by user" @keyup.enter="load" />
      </label>
      <label>
        Action
        <select v-model="filters.action" @change="load">
          <option value="">All</option>
          <option v-for="a in actions" :key="a" :value="a">{{ a }}</option>
        </select>
      </label>
      <label>
        Resource
        <input v-model="filters.resource_type" placeholder="e.g. devices" @keyup.enter="load" />
      </label>
      <label>
        From
        <input type="datetime-local" v-model="filters.after" @change="load" />
      </label>
      <label>
        To
        <input type="datetime-local" v-model="filters.before" @change="load" />
      </label>
      <button @click="load">Search</button>
      <button @click="clear">Clear</button>
    </div>

    <div v-if="loading" class="text-muted">Loading…</div>
    <template v-else>
      <table>
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>User</th>
            <th>Action</th>
            <th>Resource</th>
            <th>Path</th>
            <th>Status</th>
            <th>IP</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="entry in entries" :key="entry.id">
            <td class="text-muted" style="white-space:nowrap">{{ fmt(entry.timestamp) }}</td>
            <td>{{ entry.username || '—' }}</td>
            <td><span :class="`badge badge-${actionBadge(entry.action)}`">{{ entry.action }}</span></td>
            <td>
              <span v-if="entry.resource_type">
                {{ entry.resource_type }}<span v-if="entry.resource_id" class="text-muted">/{{ entry.resource_id }}</span>
              </span>
              <span v-else class="text-muted">—</span>
            </td>
            <td class="text-muted" style="font-size:.8rem">{{ entry.method }} {{ entry.path }}</td>
            <td>
              <span v-if="entry.status_code" :class="`badge badge-${statusBadge(entry.status_code)}`">
                {{ entry.status_code }}
              </span>
              <span v-else class="text-muted">—</span>
            </td>
            <td class="text-muted" style="font-size:.8rem">{{ entry.ip_address || '—' }}</td>
          </tr>
        </tbody>
      </table>

      <PaginationBar :page="page" :total-pages="totalPages" :total-count="totalCount" @go="goPage" />
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import api from '../api'
import PaginationBar from '../components/PaginationBar.vue'

const entries = ref([])
const loading = ref(true)
const page = ref(1)
const totalPages = ref(1)
const totalCount = ref(0)
const PAGE_SIZE = 50

const actions = ['login', 'logout', 'create', 'update', 'delete', 'action']

const filters = reactive({
  username: '',
  action: '',
  resource_type: '',
  after: '',
  before: '',
})

function fmt(iso) { return new Date(iso).toLocaleString() }

function actionBadge(action) {
  return { login: 'success', logout: 'pending', create: 'running', update: 'acknowledged', delete: 'failed', action: 'partial' }[action] ?? 'pending'
}

function statusBadge(code) {
  if (code >= 500) return 'failed'
  if (code >= 400) return 'new'
  if (code >= 200) return 'success'
  return 'pending'
}

function buildParams() {
  const p = { page: page.value, page_size: PAGE_SIZE }
  if (filters.username)      p.username      = filters.username
  if (filters.action)        p.action        = filters.action
  if (filters.resource_type) p.resource_type = filters.resource_type
  if (filters.after)         p.timestamp_after  = new Date(filters.after).toISOString()
  if (filters.before)        p.timestamp_before = new Date(filters.before).toISOString()
  return p
}

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/audit/', { params: buildParams() })
    entries.value = data.results ?? data
    totalCount.value = data.count ?? entries.value.length
    totalPages.value = Math.max(1, Math.ceil(totalCount.value / PAGE_SIZE))
  } finally {
    loading.value = false
  }
}

function goPage(n) {
  page.value = n
  load()
}

function clear() {
  Object.assign(filters, { username: '', action: '', resource_type: '', after: '', before: '' })
  page.value = 1
  load()
}

onMounted(load)
</script>
