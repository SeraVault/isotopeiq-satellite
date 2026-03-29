<template>
  <div>
    <div class="text-h5 font-weight-bold mb-5">Audit Log</div>

    <!-- Filters -->
    <v-card rounded="lg" elevation="1" class="mb-5 pa-4">
      <v-row dense align="end">
        <v-col cols="12" sm="6" md="2">
          <v-text-field v-model="filters.username" label="Username" placeholder="Filter by user" @keyup.enter="resetAndFetch" />
        </v-col>
        <v-col cols="12" sm="6" md="2">
          <v-select v-model="filters.action" label="Action" :items="actions" clearable @update:model-value="load" />
        </v-col>
        <v-col cols="12" sm="6" md="2">
          <v-text-field v-model="filters.resource_type" label="Resource" placeholder="e.g. devices" @keyup.enter="resetAndFetch" />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-text-field v-model="filters.after" label="From" type="datetime-local" @change="resetAndFetch" />
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-text-field v-model="filters.before" label="To" type="datetime-local" @change="resetAndFetch" />
        </v-col>
        <v-col cols="12" sm="auto">
          <v-btn color="primary" class="mr-2" @click="resetAndFetch">Search</v-btn>
          <v-btn @click="clear">Clear</v-btn>
        </v-col>
      </v-row>
    </v-card>

    <v-data-table-server
      v-model:options="tableOptions"
      :headers="headers"
      :items="entries"
      :items-length="totalCount"
      :loading="loading"
      :items-per-page-options="[25, 50, 100]"
      density="compact"
      rounded="lg"
      elevation="1"
      no-data-text="No audit entries."
      @update:options="onTableOptions"
    >
      <template #item.timestamp="{ item }">
        <span class="text-medium-emphasis text-caption" style="white-space:nowrap">{{ fmt(item.timestamp) }}</span>
      </template>
      <template #item.action="{ item }">
        <v-chip :color="actionColor(item.action)" size="x-small" label>{{ item.action }}</v-chip>
      </template>
      <template #item.resource_type="{ item }">
        <span v-if="item.resource_type">
          {{ item.resource_type }}<span v-if="item.resource_id" class="text-medium-emphasis">/{{ item.resource_id }}</span>
        </span>
        <span v-else class="text-medium-emphasis">—</span>
      </template>
      <template #item.path="{ item }">
        <span class="text-medium-emphasis text-caption">{{ item.method }} {{ item.path }}</span>
      </template>
      <template #item.status_code="{ item }">
        <v-chip v-if="item.status_code" :color="statusCodeColor(item.status_code)" size="x-small" label>
          {{ item.status_code }}
        </v-chip>
        <span v-else class="text-medium-emphasis">—</span>
      </template>
      <template #item.ip_address="{ item }">
        <span class="text-medium-emphasis text-caption">{{ item.ip_address || '—' }}</span>
      </template>
    </v-data-table-server>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import api from '../api'

const headers = [
  { title: 'Timestamp', key: 'timestamp',     sortable: true  },
  { title: 'User',      key: 'username',       sortable: false },
  { title: 'Action',    key: 'action',         sortable: false },
  { title: 'Resource',  key: 'resource_type',  sortable: false },
  { title: 'Path',      key: 'path',           sortable: false },
  { title: 'Status',    key: 'status_code',    sortable: false },
  { title: 'IP',        key: 'ip_address',     sortable: false },
]

const SORT_FIELD = { timestamp: 'timestamp' }

const entries    = ref([])
const loading    = ref(false)
const totalCount = ref(0)

const tableOptions = ref({ page: 1, itemsPerPage: 50, sortBy: [{ key: 'timestamp', order: 'desc' }] })

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

function buildParams(options = tableOptions.value) {
  const p = { page: options.page, page_size: options.itemsPerPage }
  if (filters.username)      p.username         = filters.username
  if (filters.action)        p.action           = filters.action
  if (filters.resource_type) p.resource_type    = filters.resource_type
  if (filters.after)         p.timestamp_after  = new Date(filters.after).toISOString()
  if (filters.before)        p.timestamp_before = new Date(filters.before).toISOString()
  if (options.sortBy?.length) {
    const { key, order } = options.sortBy[0]
    const field = SORT_FIELD[key] ?? key
    p.ordering = order === 'desc' ? `-${field}` : field
  }
  return p
}

async function load(params) {
  loading.value = true
  try {
    const { data } = await api.get('/audit/', { params })
    entries.value = data.results ?? data
    totalCount.value = data.count ?? entries.value.length
  } finally {
    loading.value = false
  }
}

function onTableOptions(options) {
  tableOptions.value = options
  load(buildParams(options))
}

function resetAndFetch() {
  const opts = { ...tableOptions.value, page: 1 }
  tableOptions.value = opts
  load(buildParams(opts))
}

function clear() {
  Object.assign(filters, { username: '', action: '', resource_type: '', after: '', before: '' })
  resetAndFetch()
}

onMounted(() => { /* initial load triggered by @update:options */ })
</script>
