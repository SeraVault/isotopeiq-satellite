<template>
  <div>
    <div class="text-h5 font-weight-bold mb-2">System Settings</div>
    <div class="text-body-2 text-medium-emphasis mb-5">
      Runtime configuration. Changes take effect immediately — no restart required.
    </div>

    <div v-if="loading" class="text-medium-emphasis pa-4">Loading…</div>
    <template v-else>
      <v-alert v-if="saved" type="success" variant="tonal" density="compact" class="mb-4" style="max-width:660px">Settings saved.</v-alert>
      <v-alert v-if="error" type="error" variant="tonal" density="compact" class="mb-4" style="max-width:660px">{{ error }}</v-alert>

      <!-- General -->
      <v-card rounded="lg" elevation="1" class="mb-5" style="max-width:660px">
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
      <v-card rounded="lg" elevation="1" class="mb-5" style="max-width:660px">
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

      <!-- Email -->
      <v-card rounded="lg" elevation="1" class="mb-5" style="max-width:660px">
        <v-card-title class="text-body-1 font-weight-bold pt-4 px-4">
          Email Notifications
        </v-card-title>
        <v-card-text>
          <v-switch
            v-model="form.email_enabled"
            label="Enable email notifications"
            color="primary"
            class="mb-2"
            hide-details
          />
          <v-row dense>
            <v-col cols="8">
              <v-text-field
                v-model="form.email_host"
                label="SMTP Host"
                :disabled="!form.email_enabled"
              />
            </v-col>
            <v-col cols="4">
              <v-text-field
                v-model.number="form.email_port"
                label="Port"
                type="number"
                min="1"
                max="65535"
                :disabled="!form.email_enabled"
              />
            </v-col>
            <v-col cols="12">
              <v-checkbox
                v-model="form.email_use_tls"
                label="Use STARTTLS"
                density="compact"
                hide-details
                :disabled="!form.email_enabled"
                class="mb-2"
              />
            </v-col>
            <v-col cols="6">
              <v-text-field
                v-model="form.email_username"
                label="SMTP Username"
                autocomplete="off"
                :disabled="!form.email_enabled"
              />
            </v-col>
            <v-col cols="6">
              <v-text-field
                v-model="form.email_password"
                label="SMTP Password"
                type="password"
                autocomplete="new-password"
                :disabled="!form.email_enabled"
                :hint="serverData.email_password_set ? 'Leave blank to keep existing password' : ''"
                persistent-hint
              />
            </v-col>
            <v-col cols="6">
              <v-text-field
                v-model="form.email_from"
                label="From Address"
                placeholder="isotopeiq@example.com"
                :disabled="!form.email_enabled"
              />
            </v-col>
            <v-col cols="6">
              <v-text-field
                v-model="form.email_recipients"
                label="Recipients"
                hint="Comma-separated email addresses"
                persistent-hint
                :disabled="!form.email_enabled"
              />
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>

      <!-- FTP / SFTP -->
      <v-card rounded="lg" elevation="1" class="mb-5" style="max-width:660px">
        <v-card-title class="text-body-1 font-weight-bold pt-4 px-4">
          FTP / SFTP Export
        </v-card-title>
        <v-card-text>
          <v-switch
            v-model="form.ftp_enabled"
            label="Enable FTP/SFTP baseline export"
            color="primary"
            class="mb-2"
            hide-details
          />
          <v-row dense>
            <v-col cols="12" sm="4">
              <v-select
                v-model="form.ftp_protocol"
                :items="ftpProtocolOptions"
                label="Protocol"
                :disabled="!form.ftp_enabled"
              />
            </v-col>
            <v-col cols="12" sm="5">
              <v-text-field
                v-model="form.ftp_host"
                label="Host"
                :disabled="!form.ftp_enabled"
              />
            </v-col>
            <v-col cols="12" sm="3">
              <v-text-field
                v-model.number="form.ftp_port"
                label="Port"
                type="number"
                min="1"
                max="65535"
                :disabled="!form.ftp_enabled"
              />
            </v-col>
            <v-col cols="6">
              <v-text-field
                v-model="form.ftp_username"
                label="Username"
                autocomplete="off"
                :disabled="!form.ftp_enabled"
              />
            </v-col>
            <v-col cols="6">
              <v-text-field
                v-model="form.ftp_password"
                label="Password"
                type="password"
                autocomplete="new-password"
                :disabled="!form.ftp_enabled"
                :hint="serverData.ftp_password_set ? 'Leave blank to keep existing password' : ''"
                persistent-hint
              />
            </v-col>
            <v-col cols="12">
              <v-text-field
                v-model="form.ftp_remote_path"
                label="Remote Path"
                placeholder="/"
                hint="Directory where baseline JSON files will be deposited"
                persistent-hint
                :disabled="!form.ftp_enabled"
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
const ftpProtocolOptions = [
  { title: 'SFTP (SSH File Transfer)',  value: 'sftp' },
  { title: 'FTP',                       value: 'ftp'  },
]

const form = ref({
  satellite_url: '',
  syslog_enabled: false,
  syslog_host: 'localhost',
  syslog_port: 514,
  syslog_facility: 'local0',
  email_enabled: false,
  email_host: 'localhost',
  email_port: 587,
  email_use_tls: true,
  email_username: '',
  email_password: '',
  email_from: '',
  email_recipients: '',
  ftp_enabled: false,
  ftp_protocol: 'sftp',
  ftp_host: 'localhost',
  ftp_port: 22,
  ftp_username: '',
  ftp_password: '',
  ftp_remote_path: '/',
})

// Tracks server-side state (e.g. whether passwords are already set)
const serverData = ref({ email_password_set: false, ftp_password_set: false })

const loading = ref(false)
const saving  = ref(false)
const saved   = ref(false)
const error   = ref('')

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await api.get('/settings/')
    serverData.value = data
    // Populate form with all non-password fields; passwords are write-only on the server
    Object.assign(form.value, {
      ...data,
      email_password: '',
      ftp_password:   '',
    })
  } finally {
    loading.value = false
  }
})

async function save() {
  saving.value = true
  saved.value  = false
  error.value  = ''
  try {
    const payload = { ...form.value }
    // Don't send blank passwords — server will keep the existing value
    if (!payload.email_password) delete payload.email_password
    if (!payload.ftp_password)   delete payload.ftp_password
    const { data } = await api.patch('/settings/', payload)
    serverData.value = data
    saved.value = true
    setTimeout(() => { saved.value = false }, 3000)
  } catch (e) {
    error.value = e.response?.data?.detail ?? 'Save failed.'
  } finally {
    saving.value = false
  }
}
</script>
