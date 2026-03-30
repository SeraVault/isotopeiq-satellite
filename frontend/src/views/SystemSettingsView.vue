<template>
  <div>
    <div class="text-h5 font-weight-bold mb-2">System Settings</div>
    <div class="text-body-2 text-medium-emphasis mb-5">
      Runtime configuration. Changes take effect immediately — no restart required.
    </div>

    <div v-if="loading" class="text-medium-emphasis pa-4">Loading…</div>
    <template v-else>
      <v-alert v-if="saved" type="success" variant="tonal" density="compact" class="mb-4" style="max-width:600px">Settings saved.</v-alert>
      <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mb-4" style="max-width:600px">{{ error }}</v-alert>

      <!-- General -->
      <v-card rounded="lg" elevation="1" class="mb-5" style="max-width:600px">
        <v-card-title class="text-body-1 font-weight-bold pt-4 px-4">General</v-card-title>
        <v-card-text>
          <v-text-field
            v-model="form.satellite_url"
            label="Satellite URL"
            hint="Public base URL of this satellite (e.g. https://satellite.example.com)"
            persistent-hint
          />
        </v-card-text>
      </v-card>

      <!-- Syslog -->
      <v-card rounded="lg" elevation="1" class="mb-5" style="max-width:600px">
        <v-card-title class="text-body-1 font-weight-bold pt-4 px-4">
          Syslog Notifications
        </v-card-title>
        <v-card-text>
          <v-switch
            v-model="form.syslog_enabled"
            label="Enable syslog notifications"
            color="primary"
            class="mb-2"
            hide-details
          />
          <v-row dense>
            <v-col cols="8">
              <v-text-field
                v-model="form.syslog_host"
                label="Syslog Host"
                :disabled="!form.syslog_enabled"
              />
            </v-col>
            <v-col cols="4">
              <v-text-field
                v-model.number="form.syslog_port"
                label="Port"
                type="number"
                min="1"
                max="65535"
                :disabled="!form.syslog_enabled"
              />
            </v-col>
            <v-col cols="12">
              <v-select
                v-model="form.syslog_facility"
                :items="facilityOptions"
                label="Facility"
                :disabled="!form.syslog_enabled"
              />
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>

      <v-btn color="primary" :loading="saving" @click="save">Save</v-btn>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const facilityOptions = [
  'kern', 'user', 'mail', 'daemon', 'auth', 'syslog', 'lpr', 'news',
  'uucp', 'cron', 'local0', 'local1', 'local2', 'local3',
  'local4', 'local5', 'local6', 'local7',
]

const form = ref({
  satellite_url: '',
  syslog_enabled: false,
  syslog_host: 'localhost',
  syslog_port: 514,
  syslog_facility: 'local0',
})

const loading = ref(false)
const saving = ref(false)
const saved = ref(false)
const error = ref('')

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await api.get('/settings/')
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
    await api.put('/settings/', form.value)
    saved.value = true
    setTimeout(() => { saved.value = false }, 3000)
  } catch (e) {
    error.value = e.response?.data?.detail ?? 'Save failed.'
  } finally {
    saving.value = false
  }
}
</script>
