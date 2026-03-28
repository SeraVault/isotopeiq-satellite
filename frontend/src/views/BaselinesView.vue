<template>
  <div>
    <h1>Baselines</h1>
    <button @click="load">Refresh</button>

    <div v-if="loading">Loading…</div>
    <table v-else-if="baselines.length">
      <thead>
        <tr>
          <th>Device</th>
          <th>Established</th>
          <th>Established By</th>
          <th>Source Job Result</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="b in baselines" :key="b.id">
          <td>{{ b.device }}</td>
          <td>{{ fmt(b.established_at) }}</td>
          <td>{{ b.established_by }}</td>
          <td>{{ b.source_result ?? '—' }}</td>
          <td>
            <button @click="viewBaseline(b)">View Data</button>
            <button @click="openPromote(b)">Promote Result…</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else>No baselines yet. Run a policy to establish one.</p>

    <!-- Baseline data modal -->
    <div v-if="viewing" class="modal">
      <div class="modal-box modal-xl">
        <div style="display:flex;align-items:baseline;justify-content:space-between;margin-bottom:.25rem">
          <h2>Baseline — Device {{ viewing.device }}</h2>
          <button @click="viewing = null">✕ Close</button>
        </div>
        <p style="color:#666;margin:.25rem 0 1rem;font-size:.85rem">
          Established {{ fmt(viewing.established_at) }} by {{ viewing.established_by }}
        </p>
        <CanonicalViewer :data="viewing.parsed_data" />
      </div>
    </div>

    <!-- Promote modal -->
    <div v-if="promoting" class="modal">
      <div class="modal-box modal-sm">
        <h2>Promote New Baseline — Device {{ promoting.device }}</h2>
        <p style="margin-bottom:.75rem">Enter the Job Result ID whose parsed output should become the new baseline.</p>
        <label>
          Job Result ID
          <input v-model.number="promoteResultId" type="number" min="1" />
        </label>
        <p v-if="promoteError" class="error" style="margin-top:.5rem">{{ promoteError }}</p>
        <div style="margin-top:1rem">
          <button class="btn-primary" @click="doPromote" :disabled="!promoteResultId">Promote</button>
          <button @click="promoting = null; promoteError = ''">Cancel</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'
import CanonicalViewer from '../components/CanonicalViewer.vue'

const baselines = ref([])
const loading = ref(false)
const viewing = ref(null)
const promoting = ref(null)
const promoteResultId = ref(null)
const promoteError = ref('')

function fmt(iso) { return new Date(iso).toLocaleString() }

async function load() {
  loading.value = true
  try {
    const { data } = await api.get('/baselines/')
    baselines.value = data.results ?? data
  } finally {
    loading.value = false
  }
}

onMounted(load)

function viewBaseline(b) { viewing.value = b }

function openPromote(b) {
  promoting.value = b
  promoteResultId.value = null
  promoteError.value = ''
}

async function doPromote() {
  promoteError.value = ''
  try {
    const { data } = await api.post(`/baselines/${promoting.value.id}/promote/`, {
      result_id: promoteResultId.value,
    })
    const idx = baselines.value.findIndex(b => b.id === promoting.value.id)
    if (idx !== -1) baselines.value[idx] = data
    promoting.value = null
  } catch (e) {
    promoteError.value = e.response?.data?.error ?? 'Promotion failed.'
  }
}
</script>
