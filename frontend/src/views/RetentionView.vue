<template>
  <div>
    <div class="text-h5 font-weight-bold mb-2">Retention Policy</div>
    <div class="text-body-2 text-medium-emphasis mb-5">
      Configure how long collected data is kept. Set any value to <strong>0</strong> to keep forever.
      Pruning runs automatically each day at 03:00 UTC.
    </div>

    <div v-if="loading" class="text-medium-emphasis pa-4">Loading…</div>
    <v-card v-else rounded="lg" elevation="1" style="max-width:500px">
      <v-card-text>
        <v-alert v-if="saved" type="success" variant="tonal" density="compact" class="mb-4">Settings saved.</v-alert>
        <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mb-4">{{ error }}</v-alert>
        <v-row dense>
          <v-col cols="12">
            <v-text-field v-model.number="form.raw_data_days" label="Raw Data Retention (days)" type="number" min="0" required />
          </v-col>
          <v-col cols="12">
            <v-text-field v-model.number="form.parsed_data_days" label="Parsed Data Retention (days)" type="number" min="0" required />
          </v-col>
          <v-col cols="12">
            <v-text-field v-model.number="form.job_history_days" label="Job History Retention (days)" type="number" min="0" required />
          </v-col>
          <v-col cols="12">
            <v-text-field v-model.number="form.log_days" label="Log / Error Message Retention (days)" type="number" min="0" required />
          </v-col>
        </v-row>
      </v-card-text>
      <v-card-actions class="px-4 pb-4">
        <v-btn color="primary" :loading="saving" @click="save">Save</v-btn>
      </v-card-actions>
    </v-card>
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
