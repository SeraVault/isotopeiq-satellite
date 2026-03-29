<template>
  <div>
    <div class="d-flex align-center mb-4">
      <div class="text-h5 font-weight-bold">Baselines</div>
      <v-spacer />
      <v-btn variant="tonal" prepend-icon="mdi-help-circle-outline" @click="showHelp = true">How it works</v-btn>
    </div>

    <!-- How it works dialog -->
    <v-dialog v-model="showHelp" max-width="720" scrollable>
      <v-card rounded="lg">
        <v-card-title class="d-flex align-center pt-4 pb-2">
          <v-icon icon="mdi-camera-outline" class="mr-2" color="primary" />
          Baselines
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" @click="showHelp = false" />
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-5" style="font-size:0.92rem;line-height:1.7">

          <p class="mb-3">
            A <strong>baseline</strong> is a point-in-time snapshot of a device's canonical
            configuration. All future collections for the same policy+device pair are compared
            against this snapshot to detect <strong>drift</strong>.
          </p>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">How a baseline is established</div>
          <p class="mb-3">
            When a job completes successfully and no baseline exists yet for that device + policy
            combination, Satellite automatically stores the parsed output as the baseline.
            Baselines are never overwritten automatically — only a manual re-baseline action
            replaces them, giving you full control over the comparison reference point.
          </p>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">What is stored</div>
          <p class="mb-3">
            The baseline stores the fully <em>parsed</em> canonical JSON document produced by the
            parser script — not raw collector output. This means the diff engine works with
            structured, normalised data (e.g. services as an array of objects, sysctl as key-value
            pairs) rather than raw text.
          </p>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">Viewing &amp; re-baselining</div>
          <p class="mb-3">
            Click <strong>View Data</strong> to open the full canonical snapshot in an interactive
            section viewer so you can inspect every field stored in the baseline.
          </p>
          <p class="mb-0">
            To re-baseline a device, go to the <strong>Drift</strong> page and acknowledge the
            relevant drift event — from there you can promote the current collection result as the
            new baseline reference.
          </p>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">Relationship to drift</div>
          <p class="mb-0">
            Every <strong>Drift Event</strong> references the baseline that was active when the
            difference was detected. If you re-baseline a device, new events will be measured
            against the updated snapshot; historical events retain a reference to the baseline
            that was in place at the time they were created.
          </p>

        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-3">
          <v-spacer />
          <v-btn color="primary" variant="tonal" @click="showHelp = false">Got it</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

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

    <v-data-table-server
      v-model:options="tableOptions"
      :headers="headers"
      :items="baselines"
      :items-length="totalCount"
      :loading="loading"
      :items-per-page-options="[25, 50, 100]"
      density="compact"
      rounded="lg"
      elevation="1"
      no-data-text="No baselines yet. Run a policy to establish one."
      @update:options="onTableOptions"
    >
      <template #item.device_name="{ item }">
        <span class="font-weight-medium">{{ item.device_name ?? item.device }}</span>
      </template>
      <template #item.established_at="{ item }">
        <span class="text-medium-emphasis text-caption">{{ fmt(item.established_at) }}</span>
      </template>
      <template #item.actions="{ item }">
        <v-btn size="x-small" variant="tonal" @click="viewBaseline(item)">View Data</v-btn>
      </template>
    </v-data-table-server>

    <!-- Baseline data dialog -->
    <v-dialog v-model="viewOpen" max-width="1200" scrollable>
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

const showHelp = ref(false)

const headers = [
  { title: 'Device',          key: 'device_name',    sortable: true  },
  { title: 'Established',     key: 'established_at', sortable: true  },
  { title: 'Established By',  key: 'established_by', sortable: false },
  { title: '',                key: 'actions',        sortable: false, align: 'end' },
]

const SORT_FIELD = {
  device_name:    'device__name',
  established_at: 'established_at',
}

const baselines  = ref([])
const loading    = ref(false)
const viewing    = ref(null)
const viewOpen   = ref(false)
const devices    = ref([])
const totalCount = ref(0)
const filters    = reactive({ device: null })

const tableOptions = ref({ page: 1, itemsPerPage: 50, sortBy: [{ key: 'established_at', order: 'desc' }] })

const deviceItems = computed(() => devices.value.map(d => ({ title: d.name, value: d.id })))

function fmt(iso) { return new Date(iso).toLocaleString() }

function buildParams(options = tableOptions.value) {
  const params = { page: options.page, page_size: options.itemsPerPage }
  if (filters.device) params.device = filters.device
  if (options.sortBy?.length) {
    const { key, order } = options.sortBy[0]
    const field = SORT_FIELD[key] ?? key
    params.ordering = order === 'desc' ? `-${field}` : field
  }
  return params
}

async function load(params) {
  loading.value = true
  try {
    const { data } = await api.get('/baselines/', { params })
    baselines.value  = data.results ?? data
    totalCount.value = data.count ?? baselines.value.length
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

function applyFilters() { resetAndFetch() }
function clearFilters()  { filters.device = null; resetAndFetch() }

async function viewBaseline(b) {
  viewing.value = b
  viewOpen.value = true
  if (!b.parsed_data) {
    const { data } = await api.get(`/baselines/${b.id}/`)
    viewing.value = data
  }
}

onMounted(async () => {
  const { data } = await api.get('/devices/', { params: { page_size: 500 } })
  devices.value = data.results ?? data
  // initial load triggered by @update:options
})
</script>
