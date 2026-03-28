<template>
  <div>
    <h1>Baselines</h1>

    <div class="card filter-bar">
      <label>
        Device
        <select v-model="filters.device" @change="applyFilters">
          <option value="">All</option>
          <option v-for="d in devices" :key="d.id" :value="d.id">{{ d.name }}</option>
        </select>
      </label>
      <div class="filter-actions">
        <button @click="applyFilters">Refresh</button>
        <button @click="clearFilters">Clear</button>
      </div>
    </div>

    <div v-if="loading">Loading…</div>
    <template v-else>
      <table v-if="baselines.length">
        <thead>
          <tr>
            <th>Device</th>
            <th>Established</th>
            <th>Established By</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in baselines" :key="b.id">
            <td>{{ b.device_name ?? b.device }}</td>
            <td>{{ fmt(b.established_at) }}</td>
            <td>{{ b.established_by }}</td>
            <td>
              <button @click="viewBaseline(b)">View Data</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else>No baselines yet. Run a policy to establish one.</p>
      <PaginationBar :page="page" :total-pages="totalPages" :total-count="totalCount" @go="goPage" />
    </template>

    <!-- Baseline data modal -->
    <div v-if="viewing" class="modal">
      <div class="modal-box modal-xl">
        <div style="display:flex;align-items:baseline;justify-content:space-between;margin-bottom:.25rem">
          <h2>Baseline — {{ viewing.device_name ?? viewing.device }}</h2>
          <button @click="viewing = null">✕ Close</button>
        </div>
        <p style="color:#666;margin:.25rem 0 1rem;font-size:.85rem">
          Established {{ fmt(viewing.established_at) }} by {{ viewing.established_by }}
        </p>
        <CanonicalViewer :data="viewing.parsed_data" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import api from '../api'
import CanonicalViewer from '../components/CanonicalViewer.vue'
import PaginationBar from '../components/PaginationBar.vue'

const PAGE_SIZE = 50
const baselines  = ref([])
const loading    = ref(false)
const viewing    = ref(null)
const devices    = ref([])
const page       = ref(1)
const totalCount = ref(0)
const totalPages = ref(1)
const filters    = reactive({ device: '' })

function fmt(iso) { return new Date(iso).toLocaleString() }

async function load() {
  loading.value = true
  try {
    const params = { page: page.value, page_size: PAGE_SIZE }
    if (filters.device) params.device = filters.device
    const { data } = await api.get('/baselines/', { params })
    baselines.value  = data.results ?? data
    totalCount.value = data.count ?? baselines.value.length
    totalPages.value = Math.max(1, Math.ceil(totalCount.value / PAGE_SIZE))
  } finally {
    loading.value = false
  }
}

function applyFilters() { page.value = 1; load() }
function clearFilters()  { filters.device = ''; page.value = 1; load() }
function goPage(n)       { page.value = n; load() }

function viewBaseline(b) { viewing.value = b }

onMounted(async () => {
  const { data } = await api.get('/devices/', { params: { page_size: 500 } })
  devices.value = data.results ?? data
  load()
})
</script>

<style scoped>
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: .75rem;
  align-items: flex-end;
  margin-bottom: 1.25rem;
  padding: 1rem 1.25rem;
}
.filter-bar label {
  display: flex;
  flex-direction: column;
  font-size: .8rem;
  font-weight: 600;
  color: #555;
  gap: .25rem;
  margin: 0;
}
.filter-bar select {
  padding: .35rem .6rem;
  border: 1px solid #d0d0d0;
  border-radius: 5px;
  font-size: .875rem;
  background: #fff;
  min-width: 160px;
  margin: 0;
}
.filter-actions {
  display: flex;
  gap: .4rem;
  align-items: flex-end;
  padding-bottom: 1px;
}
</style>
