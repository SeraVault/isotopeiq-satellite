<template>
  <div>
    <div class="text-h5 font-weight-bold mb-5">Baselines</div>

    <!-- Filters -->
    <v-card rounded="lg" elevation="1" class="mb-5 pa-4">
      <v-row dense align="end">
        <v-col cols="12" sm="6" md="3">
          <v-select v-model="filters.device" label="Device" :items="deviceItems" item-title="title" item-value="value" clearable @update:model-value="applyFilters" />
        </v-col>
        <v-col cols="12" sm="auto">
          <v-btn color="primary" class="mr-2" @click="applyFilters">Refresh</v-btn>
          <v-btn @click="clearFilters">Clear</v-btn>
        </v-col>
      </v-row>
    </v-card>

    <div v-if="loading" class="text-medium-emphasis pa-4">Loading…</div>
    <template v-else>
      <v-card v-if="baselines.length" rounded="lg" elevation="1">
        <v-table density="compact">
          <thead>
            <tr>
              <th>Device</th><th>Established</th><th>Established By</th><th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="b in baselines" :key="b.id">
              <td class="font-weight-medium">{{ b.device_name ?? b.device }}</td>
              <td class="text-medium-emphasis text-caption">{{ fmt(b.established_at) }}</td>
              <td class="text-medium-emphasis">{{ b.established_by }}</td>
              <td>
                <v-btn size="x-small" variant="tonal" @click="viewBaseline(b)">View Data</v-btn>
              </td>
            </tr>
          </tbody>
        </v-table>
      </v-card>
      <div v-else class="pa-6 text-center text-medium-emphasis">No baselines yet. Run a policy to establish one.</div>

      <!-- Pagination -->
      <div class="d-flex align-center justify-center ga-2 mt-4">
        <v-btn size="small" variant="text" :disabled="page <= 1" @click="goPage(page - 1)">← Prev</v-btn>
        <span class="text-caption text-medium-emphasis">Page {{ page }} of {{ totalPages }} &nbsp;({{ totalCount }} total)</span>
        <v-btn size="small" variant="text" :disabled="page >= totalPages" @click="goPage(page + 1)">Next →</v-btn>
      </div>
    </template>

    <!-- Baseline data dialog -->
    <v-dialog v-model="viewOpen" max-width="900" scrollable>
      <v-card v-if="viewing" rounded="lg">
        <v-card-title class="d-flex justify-space-between align-center">
          <span>Baseline — {{ viewing.device_name ?? viewing.device }}</span>
          <v-btn icon="mdi-close" variant="text" size="small" @click="viewOpen = false" />
        </v-card-title>
        <v-card-subtitle>Established {{ fmt(viewing.established_at) }} by {{ viewing.established_by }}</v-card-subtitle>
        <v-card-text>
          <CanonicalViewer :data="viewing.parsed_data" />
        </v-card-text>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import api from '../api'
import CanonicalViewer from '../components/CanonicalViewer.vue'

const PAGE_SIZE = 50
const baselines  = ref([])
const loading    = ref(false)
const viewing    = ref(null)
const viewOpen   = ref(false)
const devices    = ref([])
const page       = ref(1)
const totalCount = ref(0)
const totalPages = ref(1)
const filters    = reactive({ device: null })

const deviceItems = computed(() => devices.value.map(d => ({ title: d.name, value: d.id })))

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
function clearFilters()  { filters.device = null; page.value = 1; load() }
function goPage(n)       { page.value = n; load() }

function viewBaseline(b) { viewing.value = b; viewOpen.value = true }

onMounted(async () => {
  const { data } = await api.get('/devices/', { params: { page_size: 500 } })
  devices.value = data.results ?? data
  load()
})
</script>
