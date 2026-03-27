<template>
  <div>
    <h1>Retention Policy</h1>
    <p style="margin-bottom:1rem;color:#555">
      Configure how long collected data is kept. Set any value to <strong>0</strong> to keep forever.
      Pruning runs automatically each day at 03:00 UTC.
    </p>

    <div v-if="loading">Loading…</div>
    <form v-else @submit.prevent="save" style="max-width:480px;background:#fff;padding:1.5rem;border-radius:8px;box-shadow:0 1px 3px rgba(0,0,0,.1)">
      <label>
        Raw Data Retention (days)
        <input v-model.number="form.raw_data_days" type="number" min="0" required />
      </label>
      <label style="margin-top:.75rem">
        Parsed Data Retention (days)
        <input v-model.number="form.parsed_data_days" type="number" min="0" required />
      </label>
      <label style="margin-top:.75rem">
        Job History Retention (days)
        <input v-model.number="form.job_history_days" type="number" min="0" required />
      </label>
      <label style="margin-top:.75rem">
        Log / Error Message Retention (days)
        <input v-model.number="form.log_days" type="number" min="0" required />
      </label>

      <p v-if="saved" style="margin-top:.75rem;color:#155724">Settings saved.</p>
      <p v-if="error" class="error" style="margin-top:.75rem">{{ error }}</p>

      <div style="margin-top:1.25rem">
        <button class="btn-primary" type="submit" :disabled="saving">{{ saving ? 'Saving…' : 'Save' }}</button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const form = ref({ raw_data_days: 90, parsed_data_days: 365, job_history_days: 180, log_days: 90 })
const loading = ref(false)
const saving = ref(false)
const saved = ref(false)
const error = ref('')

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await api.get('/retention/')
    Object.assign(form.value, data)
  } finally {
    loading.value = false
  }
})

async function save() {
  saving.value = true
  saved.value = false
  error.value = ''
  try {
    await api.put('/retention/', form.value)
    saved.value = true
    setTimeout(() => { saved.value = false }, 3000)
  } catch (e) {
    error.value = e.response?.data?.detail ?? 'Save failed.'
  } finally {
    saving.value = false
  }
}
</script>
