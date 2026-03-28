<template>
  <div>
    <h1>Drift Events</h1>
    <button @click="store.fetchEvents()">Refresh</button>

    <div v-if="store.loading">Loading…</div>
    <table v-else>
      <thead>
        <tr><th>Device</th><th>Status</th><th>Detected</th><th>Acknowledged By</th><th>Diff Keys</th><th>Actions</th></tr>
      </thead>
      <tbody>
        <tr v-for="event in store.events" :key="event.id">
          <td>{{ event.device_name ?? event.device }}</td>
          <td><span :class="`badge badge-${event.status}`">{{ event.status }}</span></td>
          <td>{{ new Date(event.created_at).toLocaleString() }}</td>
          <td>
            <span v-if="event.acknowledged_by">
              {{ event.acknowledged_by }}
              <span v-if="event.acknowledgement_reason" class="text-muted" style="font-size:.8rem"> — {{ event.acknowledgement_reason }}</span>
            </span>
            <span v-else class="text-muted">—</span>
          </td>
          <td>{{ Object.keys(event.diff).join(', ') || '—' }}</td>
          <td>
            <button @click="openDiff(event)">View Diff</button>
            <button v-if="event.status === 'new'" @click="openAcknowledge(event)">Acknowledge</button>
            <button v-if="event.status !== 'resolved'" @click="store.resolve(event.id)">Resolve</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-if="!store.loading && !store.events.length">No drift events.</p>

    <!-- Diff detail modal -->
    <div v-if="selected" class="modal">
      <div class="modal-box modal-xl">
        <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:1rem;margin-bottom:.75rem">
          <div>
            <h2 style="margin:0">Drift — {{ selected.device_name ?? selected.device }}</h2>
            <p style="margin:.25rem 0 0;color:#666;font-size:.85rem">
              <span :class="`badge badge-${selected.status}`">{{ selected.status }}</span>
              &nbsp; {{ new Date(selected.created_at).toLocaleString() }}
            </p>
          </div>
          <button @click="selected = null">✕ Close</button>
        </div>
        <div v-if="diffLoading" class="text-muted" style="padding:1rem 0">Loading diff data…</div>
        <DriftDiffViewer v-else :baseline="selected.baseline_data" :current="selected.result_data" :volatile-fields="store.volatileFields" />
      </div>
    </div>

    <!-- Acknowledge modal -->
    <div v-if="acknowledging" class="modal">
      <div class="modal-box modal-sm">
        <h2>Acknowledge Drift</h2>
        <p class="text-muted" style="margin:.25rem 0 .75rem">Device: <strong>{{ acknowledging.device }}</strong></p>
        <label>
          Reason <span style="color:#c00">*</span>
          <textarea
            v-model="ackReason"
            rows="4"
            placeholder="Explain why this drift is expected or acceptable…"
            style="width:100%;margin-top:.35rem;resize:vertical"
          ></textarea>
        </label>
        <p v-if="ackError" class="error" style="margin-top:.4rem">{{ ackError }}</p>
        <div style="margin-top:1rem;display:flex;gap:.5rem">
          <button class="btn-primary" :disabled="ackSaving" @click="submitAcknowledge">
            {{ ackSaving ? 'Saving…' : 'Acknowledge' }}
          </button>
          <button @click="acknowledging = null; ackReason = ''; ackError = ''">Cancel</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useDriftStore } from '../stores/drift'
import api from '../api'
import DriftDiffViewer from '../components/DriftDiffViewer.vue'

const store = useDriftStore()
const selected = ref(null)
const diffLoading = ref(false)

async function openDiff(event) {
  selected.value = { ...event, baseline_data: null, result_data: null }
  diffLoading.value = true
  try {
    const [baselineRes, resultRes] = await Promise.all([
      api.get('/baselines/', { params: { device: event.device } }),
      api.get(`/jobs/results/${event.job_result}/`),
      store.fetchVolatileFields(),
    ])
    const baselines = baselineRes.data.results ?? baselineRes.data
    selected.value = {
      ...event,
      baseline_data: baselines[0]?.parsed_data ?? null,
      result_data: resultRes.data.parsed_output ?? null,
    }
  } finally {
    diffLoading.value = false
  }
}

const acknowledging = ref(null)
const ackReason = ref('')
const ackError = ref('')
const ackSaving = ref(false)

function openAcknowledge(event) {
  acknowledging.value = event
  ackReason.value = ''
  ackError.value = ''
}

async function submitAcknowledge() {
  if (!ackReason.value.trim()) {
    ackError.value = 'A reason is required.'
    return
  }
  ackSaving.value = true
  ackError.value = ''
  try {
    await store.acknowledge(acknowledging.value.id, ackReason.value.trim())
    acknowledging.value = null
    ackReason.value = ''
  } catch (e) {
    ackError.value = e.response?.data?.error ?? 'Failed to acknowledge.'
  } finally {
    ackSaving.value = false
  }
}

onMounted(() => store.fetchEvents())
</script>
