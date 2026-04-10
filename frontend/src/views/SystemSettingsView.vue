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

      <!-- Agent Security -->
      <v-card rounded="lg" elevation="1" class="mb-5" style="max-width:660px">
        <v-card-title class="text-body-1 font-weight-bold pt-4 px-4">Agent Security</v-card-title>
        <v-card-text>
          <div class="text-body-2 text-medium-emphasis mb-3">
            Agents verify this shared secret on every request via the
            <code>X-Agent-Secret</code> header. Leave blank to disable
            secret enforcement. Re-download and reinstall the agent bundle
            on all devices after changing this value.
          </div>
          <v-text-field
            v-model="form.agent_secret"
            label="Agent Secret"
            :placeholder="serverData.agent_secret_set ? '(secret is set — enter new value to change)' : 'Enter shared secret'"
            type="password"
            autocomplete="new-password"
            hint="Shared secret included in the agent bundle and checked on every /collect and /run request"
            persistent-hint
            clearable
          >
            <template #append-inner>
              <v-btn
                size="small"
                variant="text"
                density="compact"
                title="Generate a random secret"
                @click="generateSecret"
              >Generate</v-btn>
            </template>
          </v-text-field>
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

      <!-- Data Retention -->
      <v-card rounded="lg" elevation="1" class="mb-5" style="max-width:660px">
        <v-card-title class="text-body-1 font-weight-bold pt-4 px-4">Data Retention</v-card-title>
        <v-card-text>
          <div class="text-body-2 text-medium-emphasis mb-4">
            Set to <strong>0</strong> to disable pruning for that category (keep forever).
            The cleanup task runs nightly.
          </div>
          <v-row dense>
            <v-col cols="12" sm="6">
              <v-text-field
                v-model.number="form.raw_data_days"
                label="Raw collection output (days)"
                type="number" min="0"
                hint="Raw stdout from collection scripts"
                persistent-hint
              />
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field
                v-model.number="form.parsed_data_days"
                label="Parsed / canonical JSON (days)"
                type="number" min="0"
                hint="Parsed baseline snapshots"
                persistent-hint
              />
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field
                v-model.number="form.job_history_days"
                label="Job history (days)"
                type="number" min="0"
                hint="Job run records"
                persistent-hint
              />
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field
                v-model.number="form.log_days"
                label="Job logs (days)"
                type="number" min="0"
                hint="Stdout / stderr captured during runs"
                persistent-hint
              />
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>

      <!-- LDAP -->
      <v-card rounded="lg" elevation="1" class="mb-5" style="max-width:660px">
        <v-card-title class="text-body-1 font-weight-bold pt-4 px-4">
          LDAP Authentication
        </v-card-title>
        <v-card-text>
          <v-switch
            v-model="form.ldap_enabled"
            label="Enable LDAP authentication"
            color="primary"
            class="mb-2"
            hide-details
          />
          <v-row dense>
            <v-col cols="12">
              <v-text-field
                v-model="form.ldap_server_uri"
                label="Server URI"
                placeholder="ldap://ldap.example.com:389"
                hint="Use ldaps:// for SSL, ldap:// with Start TLS, or ldap:// for plain"
                persistent-hint
                :disabled="!form.ldap_enabled"
              />
            </v-col>
            <v-col cols="12">
              <v-checkbox
                v-model="form.ldap_start_tls"
                label="Use StartTLS"
                density="compact"
                hide-details
                :disabled="!form.ldap_enabled"
                class="mb-2"
              />
            </v-col>
            <v-col cols="12">
              <v-text-field
                v-model="form.ldap_bind_dn"
                label="Bind DN"
                placeholder="cn=readonly,dc=example,dc=com"
                autocomplete="off"
                :disabled="!form.ldap_enabled"
              />
            </v-col>
            <v-col cols="12">
              <v-text-field
                v-model="form.ldap_bind_password"
                label="Bind Password"
                type="password"
                autocomplete="new-password"
                :disabled="!form.ldap_enabled"
                :hint="serverData.ldap_bind_password_set ? 'Leave blank to keep existing password' : ''"
                persistent-hint
              />
            </v-col>
            <v-col cols="12">
              <v-divider class="my-2" />
              <div class="text-caption text-medium-emphasis mb-3">User Search</div>
            </v-col>
            <v-col cols="12">
              <v-text-field
                v-model="form.ldap_user_search_base"
                label="User Search Base DN"
                placeholder="ou=users,dc=example,dc=com"
                :disabled="!form.ldap_enabled"
              />
            </v-col>
            <v-col cols="12">
              <v-text-field
                v-model="form.ldap_user_search_filter"
                label="User Search Filter"
                placeholder="(uid=%(user)s)"
                :disabled="!form.ldap_enabled"
              />
            </v-col>
            <v-col cols="12">
              <v-divider class="my-2" />
              <div class="text-caption text-medium-emphasis mb-3">Group Search (optional)</div>
            </v-col>
            <v-col cols="12">
              <v-text-field
                v-model="form.ldap_group_search_base"
                label="Group Search Base DN"
                placeholder="ou=groups,dc=example,dc=com"
                :disabled="!form.ldap_enabled"
              />
            </v-col>
            <v-col cols="12">
              <v-text-field
                v-model="form.ldap_superuser_group"
                label="Superuser Group DN"
                placeholder="cn=admins,ou=groups,dc=example,dc=com"
                hint="Members of this group become Django superusers"
                persistent-hint
                :disabled="!form.ldap_enabled"
              />
            </v-col>
            <v-col cols="12">
              <v-text-field
                v-model="form.ldap_staff_group"
                label="Staff Group DN"
                placeholder="cn=staff,ou=groups,dc=example,dc=com"
                hint="Members of this group get Django staff (admin) access"
                persistent-hint
                :disabled="!form.ldap_enabled"
              />
            </v-col>
            <v-col cols="12">
              <v-divider class="my-2" />
              <div class="text-caption text-medium-emphasis mb-3">Attribute Mapping</div>
            </v-col>
            <v-col cols="4">
              <v-text-field
                v-model="form.ldap_attr_first_name"
                label="First Name Attr"
                placeholder="givenName"
                :disabled="!form.ldap_enabled"
              />
            </v-col>
            <v-col cols="4">
              <v-text-field
                v-model="form.ldap_attr_last_name"
                label="Last Name Attr"
                placeholder="sn"
                :disabled="!form.ldap_enabled"
              />
            </v-col>
            <v-col cols="4">
              <v-text-field
                v-model="form.ldap_attr_email"
                label="Email Attr"
                placeholder="mail"
                :disabled="!form.ldap_enabled"
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
  agent_secret: '',
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
  ldap_enabled: false,
  ldap_server_uri: '',
  ldap_bind_dn: '',
  ldap_bind_password: '',
  ldap_start_tls: false,
  ldap_user_search_base: '',
  ldap_user_search_filter: '(uid=%(user)s)',
  ldap_group_search_base: '',
  ldap_attr_first_name: 'givenName',
  ldap_attr_last_name: 'sn',
  ldap_attr_email: 'mail',
  ldap_superuser_group: '',
  ldap_staff_group: '',
  // retention
  raw_data_days: 90,
  parsed_data_days: 365,
  job_history_days: 180,
  log_days: 90,
})

// Tracks server-side state (e.g. whether passwords are already set)
const serverData = ref({ email_password_set: false, ftp_password_set: false, ldap_bind_password_set: false, agent_secret_set: false })

const loading = ref(false)
const saving  = ref(false)
const saved   = ref(false)
const error   = ref('')

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await api.get('/settings/')
    serverData.value = data
    Object.assign(form.value, {
      ...data,
      email_password:     '',
      ftp_password:       '',
      ldap_bind_password: '',
      agent_secret:       '',
    })
  } finally {
    loading.value = false
  }
})

function generateSecret() {
  const bytes = new Uint8Array(32)
  crypto.getRandomValues(bytes)
  form.value.agent_secret = Array.from(bytes).map(b => b.toString(16).padStart(2, '0')).join('')
}

async function save() {
  saving.value = true
  saved.value  = false
  error.value  = ''
  try {
    const payload = { ...form.value }
    // Don't send blank passwords — server will keep the existing value
    if (!payload.email_password)     delete payload.email_password
    if (!payload.ftp_password)       delete payload.ftp_password
    if (!payload.ldap_bind_password) delete payload.ldap_bind_password
    if (!payload.agent_secret)       delete payload.agent_secret
    const { data } = await api.patch('/settings/', payload)
    serverData.value = data
    Object.assign(form.value, {
      ...data,
      email_password:     '',
      ftp_password:       '',
      ldap_bind_password: '',
      agent_secret:       '',
    })
    saved.value = true
    setTimeout(() => { saved.value = false }, 3000)
  } catch (e) {
    error.value = e.response?.data?.detail ?? 'Save failed.'
  } finally {
    saving.value = false
  }
}
</script>
