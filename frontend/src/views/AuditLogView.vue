<template>
  <div>
    <div class="text-h5 font-weight-bold mb-5">Audit Log</div>

    <!-- Filters -->
    <v-card rounded="lg" elevation="1" class="mb-5 pa-4">
      <v-row dense align="end">
        <v-col cols="12" sm="6" md="2">
          <v-text-field v-model="filters.username" label="Username" placeholder="Filter by user" @keyup.enter="load" />
        </v-col>
        <v-col cols="12" sm="6" md="2">
          <v-select v-model="filters.action" label="Action" :items="actions" clearable @update:model-value="load" />
        </v-col>
        <v-col cols="12" sm="6" md="2">
          <v-text-field v-model="filters.resource_type" label="Resource" placeholder="e.g. devices" @keyup.enter="load" />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-text-field v-model="filters.after" label="From" type="datetime-local" @change="load" />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-text-field v-model="filters.before" label="To" type="datetime-local" @change="load" />
        </v-col>
        <v-col cols="12" sm="auto">
          <v-btn color="primary" class="mr-2" @click="load">Search</v-btn>
          <v-btn @click="clear">Clear</v-btn>
        </v-col>
      </v-row>
    </v-card>

    <div v-if="loading" class="text-medium-emphasis pa-4">Loading…</div>
    <template v-else>
      <v-card rounded="lg" elevation="1">
        <v-table density="compact">
          <thead>
            <tr>
              <th>Timestamp</th><th>User</th><th>Action</th>
              <th>Resource</th><th>Path</th><th>Status</th><th>IP</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="entry in entries" :key="entry.id">
              <td class="text-medium-emphasis text-caption" style="white-space:nowrap">{{ fmt(entry.timestamp) }}</td>
              <td>{{ entry.username || '—' }}</td>
              <td><v-chip :color="actionColor(entry.action)" size="x-small" label>{{ entry.action }}</v-chip></td>
              <td>
                <span v-if="entry.resource_type">
                  {{ entry.resource_type }}<span v-if="entry.resource_id" class="text-medium-emphasis">/{{ entry.resource_id }}</span>
                </span>
                <span v-else class="text-medium-emphasis">—</span>
              </td>
              <td class="text-medium-emphasis text-caption">{{ entry.method }} {{ entry.path }}</td>
              <td>
                <v-chip v-if="entry.status_code" :color="statusCodeColor(entry.status_code)" size="x-small" label>
                  {{ entry.status_code }}
                </v-chip>
                <span v-else class="text-medium-emphasis">—</span>
              </td>
              <td class="text-medium-emphasis text-caption">{{ entry.ip_address || '—' }}</td>
            </tr>
          </tbody>
        </v-table>
      </v-card>

      <!-- Pagination -->
      <div class="d-flex align-center justify-center ga-2 mt-4">
        <v-btn size="small" variant="text" :disabled="page <= 1" @click="goPage(page - 1)">← Prev</v-btn>
        <span class="text-caption text-medium-emphasis">Page {{ page }} of {{ totalPages }} &nbsp;({{ totalCount }} total)</span>
        <v-btn size="small" variant="text" :disabled="page >= totalPages" @click="goPage(page + 1)">Next →</v-btn>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import api from '../api'

const entries = ref([])
const loading = ref(true)
const page = ref(1)
const totalPages = ref(1)
const totalCount = ref(0)
const PAGE_SIZE = 50

const actions = ['login', 'logout', 'create', 'update', 'delete', 'action']

const filters = reactive({
  username: '', action: '', resource_type: '', after: '', before: '',
})

function fmt(iso) { return new Date(iso).toLocaleString() }

function actionColor(action) {
  return { login: 'success', logout: 'default', create: 'info', update: 'warning', delete: 'error', action: 'primary' }[action] ?? 'default'
}

function statusCodeColor(code) {
  if (code >= 500) return 'error'
  if (code >= 400) return 'warning'
  if (code >= 200) return 'success'
  return 'default'
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

function goPage(n) { page.value = n; load() }

function clear() {
  Object.assign(filters, { username: '', action: '', resource_type: '', after: '', before: '' })
  page.value = 1
  load()
}

onMounted(load)
</script>
