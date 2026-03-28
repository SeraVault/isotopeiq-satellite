<template>
  <div>
    <div class="text-h5 font-weight-bold mb-4">Devices</div>

    <v-tabs v-model="activeTab" color="primary" class="mb-4">
      <v-tab value="devices">Devices</v-tab>
      <v-tab value="credentials">Credentials</v-tab>
    </v-tabs>

    <!-- ── DEVICES TAB ──────────────────────────────────────────────────── -->
    <v-window v-model="activeTab">
      <v-window-item value="devices">

        <!-- Filter bar -->
        <v-card elevation="1" rounded="lg" class="mb-4 pa-4">
          <v-row dense align="center">
            <v-col cols="12" sm="3">
              <v-text-field v-model="deviceSearch" label="Search" placeholder="name, hostname, FQDN…" prepend-inner-icon="mdi-magnify" clearable @keyup.enter="applyDeviceFilters" @click:clear="clearDeviceFilters" />
            </v-col>
            <v-col cols="6" sm="2">
              <v-select v-model="deviceOsType" label="OS" :items="osItems" @update:modelValue="applyDeviceFilters" />
            </v-col>
            <v-col cols="6" sm="2">
              <v-select v-model="deviceConnType" label="Connection" :items="connItems" @update:modelValue="applyDeviceFilters" />
            </v-col>
            <v-col cols="6" sm="2">
              <v-select v-model="deviceActive" label="Active" :items="activeItems" @update:modelValue="applyDeviceFilters" />
            </v-col>
            <v-col cols="6" sm="3" class="d-flex ga-2 justify-end">
              <v-btn @click="clearDeviceFilters" variant="outlined">Clear</v-btn>
              <v-btn color="primary" prepend-icon="mdi-plus" @click="openNewDevice">Add Device</v-btn>
            </v-col>
          </v-row>
        </v-card>

        <!-- Snackbar for test/collect result -->
        <v-snackbar v-model="snackbar.show" :color="snackbar.ok ? 'success' : 'error'" timeout="6000" location="bottom right">
          {{ snackbar.msg }}
        </v-snackbar>

        <v-card elevation="1" rounded="lg">
          <v-data-table
            :headers="deviceHeaders"
            :items="devStore.devices"
            :loading="devStore.loading"
            hide-default-footer
            hover
            @click:row="(_, { item }) => openViewer(item)"
          >
            <template #item.is_active="{ item }">
              <v-chip :color="item.is_active ? 'success' : 'default'" size="x-small" label>{{ item.is_active ? 'Yes' : 'No' }}</v-chip>
            </template>
            <template #item.credential="{ item }">{{ credName(item.credential) }}</template>
            <template #item.actions="{ item }">
              <div class="d-flex ga-1" @click.stop>
                <v-btn size="x-small" variant="tonal" :loading="testing === item.id" @click="testConn(item)">Test</v-btn>
                <v-btn size="x-small" variant="tonal" color="primary" :loading="collecting === item.id" @click="collect(item)">Collect</v-btn>
                <v-btn size="x-small" variant="tonal" @click="openEditDevice(item)">Edit</v-btn>
                <v-btn size="x-small" variant="tonal" color="error" @click="removeDevice(item.id)">Delete</v-btn>
              </div>
            </template>
          </v-data-table>
          <div class="d-flex align-center justify-space-between px-4 py-2 border-t">
            <span class="text-caption text-medium-emphasis">{{ devStore.totalCount }} total</span>
            <v-pagination v-model="devStore.page" :length="devStore.totalPages" density="compact" @update:modelValue="devStore.goPage" />
          </div>
        </v-card>

        <!-- Device form dialog -->
        <v-dialog v-model="deviceForm.show" max-width="700" scrollable>
          <v-card rounded="lg">
            <v-card-title>{{ deviceForm.id ? 'Edit' : 'Add' }} Device</v-card-title>
            <v-card-text>
              <v-row dense>
                <v-col cols="12" sm="6"><v-text-field v-model="deviceForm.name" label="Name *" /></v-col>
                <v-col cols="12" sm="6"><v-text-field v-model="deviceForm.hostname" label="Hostname / IP *" /></v-col>
                <v-col cols="12" sm="6"><v-text-field v-model="deviceForm.fqdn" label="FQDN" placeholder="optional" /></v-col>
                <v-col cols="12" sm="6"><v-text-field v-model.number="deviceForm.port" label="Port" type="number" :placeholder="String(defaultPort(deviceForm.connection_type))" /></v-col>
                <v-col cols="12" sm="6">
                  <v-select v-model="deviceForm.device_type" label="Device Type" :items="deviceTypeItems" />
                </v-col>
                <v-col cols="12" sm="6">
                  <v-select v-model="deviceForm.os_type" label="OS Type" :items="osTypeItems" />
                </v-col>
                <v-col cols="12" sm="6">
                  <v-select v-model="deviceForm.connection_type" label="Connection Type" :items="connTypeItems" @update:modelValue="onConnectionTypeChange" />
                </v-col>
                <v-col cols="12" sm="6">
                  <v-select v-model="deviceForm.credential" label="Credential" :items="credentialItems" clearable />
                </v-col>
                <v-col v-if="deviceForm.connection_type === 'ssh'" cols="12">
                  <v-text-field v-model="deviceForm.host_key" label="SSH Host Key (optional)" placeholder="base64 public key — run: ssh-keyscan -t rsa <hostname>" style="font-family:monospace" />
                </v-col>
              </v-row>

              <v-expansion-panels class="mt-2" variant="accordion">
                <v-expansion-panel title="Inline credentials (fallback)">
                  <v-expansion-panel-text>
                    <v-row dense>
                      <v-col cols="6"><v-text-field v-model="deviceForm.username" label="Username" autocomplete="off" /></v-col>
                      <v-col cols="6"><v-text-field v-model="deviceForm.password" label="Password" type="password" autocomplete="new-password" /></v-col>
                    </v-row>
                  </v-expansion-panel-text>
                </v-expansion-panel>
              </v-expansion-panels>

              <v-text-field v-model="deviceForm.tagsRaw" label="Tags (comma-separated)" placeholder="prod, linux, web" class="mt-3" />
              <v-textarea v-model="deviceForm.notes" label="Notes" rows="2" class="mt-1" />
              <v-checkbox v-model="deviceForm.is_active" label="Active" density="compact" hide-details />

              <v-alert v-if="deviceForm.error" type="error" variant="tonal" density="compact" class="mt-3">{{ deviceForm.error }}</v-alert>

              <v-alert v-if="deviceForm.testResult" :type="deviceForm.testResult.ok ? 'success' : 'error'" variant="tonal" density="compact" class="mt-3">
                <div class="font-weight-bold">{{ deviceForm.testResult.ok ? 'Connection successful' : 'Connection failed' }}</div>
                <pre v-if="deviceForm.testResult.detail" class="mt-1" style="background:transparent;padding:0;font-size:.82rem;white-space:pre-wrap;word-break:break-word">{{ deviceForm.testResult.detail }}</pre>
              </v-alert>
            </v-card-text>
            <v-card-actions>
              <v-btn
                variant="tonal"
                :loading="deviceForm.testing"
                :disabled="!deviceForm.hostname || !canTestConnection(deviceForm.connection_type)"
                @click="testConnInModal"
              >Test Connection</v-btn>
              <v-spacer />
              <v-btn @click="deviceForm.show = false">Cancel</v-btn>
              <v-btn color="primary" @click="saveDevice">Save</v-btn>
            </v-card-actions>
          </v-card>
        </v-dialog>

        <!-- Device viewer dialog -->
        <v-dialog v-model="viewerOpen" max-width="1200" scrollable>
          <v-card v-if="viewer.device" rounded="lg">
            <v-card-title>
              {{ viewer.device.name }}
              <div class="text-caption text-medium-emphasis font-weight-regular">{{ viewer.device.hostname }} · {{ viewer.device.device_type }} · {{ viewer.device.os_type }}</div>
            </v-card-title>
            <v-tabs v-model="viewer.tab" color="primary" density="compact" class="border-b">
              <v-tab value="info">Info</v-tab>
              <v-tab value="baseline" @click="loadBaseline">Baseline</v-tab>
            </v-tabs>
            <v-card-text>
              <v-window v-model="viewer.tab">
                <v-window-item value="info">
                  <v-table density="compact">
                    <tbody>
                      <tr v-for="row in infoRows(viewer.device)" :key="row.label">
                        <td class="font-weight-medium text-no-wrap pr-6" style="width:160px">{{ row.label }}</td>
                        <td>{{ row.value }}</td>
                      </tr>
                    </tbody>
                  </v-table>
                </v-window-item>
                <v-window-item value="baseline">
                  <div v-if="viewer.baselineLoading" class="pa-4 text-medium-emphasis">Loading baseline…</div>
                  <div v-else-if="!viewer.baseline" class="pa-4 text-medium-emphasis">No baseline established yet. Run a policy against this device first.</div>
                  <div v-else>
                    <p class="text-caption text-medium-emphasis mb-3">Established {{ fmt(viewer.baseline.established_at) }} by {{ viewer.baseline.established_by }}</p>
                    <CanonicalViewer :data="viewer.baseline.parsed_data" />
                  </div>
                </v-window-item>
              </v-window>
            </v-card-text>
            <v-card-actions>
              <v-spacer />
              <v-btn @click="viewerOpen = false">Close</v-btn>
            </v-card-actions>
          </v-card>
        </v-dialog>
      </v-window-item>

      <!-- ── CREDENTIALS TAB ──────────────────────────────────────────── -->
      <v-window-item value="credentials">
        <div class="d-flex justify-end mb-3">
          <v-btn color="primary" prepend-icon="mdi-plus" @click="openNewCred">Add Credential</v-btn>
        </div>

        <v-card elevation="1" rounded="lg">
          <v-data-table
            :headers="credHeaders"
            :items="credentials"
            :loading="credLoading"
            hide-default-footer
          >
            <template #item.actions="{ item }">
              <div class="d-flex ga-1">
                <v-btn size="x-small" variant="tonal" icon="mdi-pencil" @click="openEditCred(item)" />
                <v-btn size="x-small" color="error" variant="tonal" icon="mdi-delete" @click="removeCred(item.id)" />
              </div>
            </template>
          </v-data-table>
        </v-card>

        <!-- Credential dialog -->
        <v-dialog v-model="credForm.show" max-width="480" scrollable>
          <v-card rounded="lg">
            <v-card-title>{{ credForm.id ? 'Edit' : 'Add' }} Credential</v-card-title>
            <v-card-text>
              <v-text-field v-model="credForm.name" label="Name *" class="mb-2" />
              <v-select v-model="credForm.credential_type" label="Type" :items="credTypeItems" class="mb-2" />
              <v-text-field v-if="credForm.credential_type !== 'api_token'" v-model="credForm.username" label="Username" class="mb-2" />
              <v-text-field v-if="credForm.credential_type === 'password'" v-model="credForm.password" label="Password" type="password" autocomplete="new-password" placeholder="leave blank to keep existing" class="mb-2" />
              <v-textarea v-if="credForm.credential_type === 'private_key'" v-model="credForm.private_key" label="Private Key (PEM)" rows="8" style="font-family:monospace;font-size:.82rem" placeholder="-----BEGIN ... PRIVATE KEY-----&#10;...&#10;-----END ... PRIVATE KEY-----" class="mb-2" />
              <v-text-field v-if="credForm.credential_type === 'api_token'" v-model="credForm.token" label="Token" type="password" autocomplete="new-password" placeholder="leave blank to keep existing" class="mb-2" />
              <v-textarea v-model="credForm.notes" label="Notes" rows="2" />
              <v-alert v-if="credForm.error" type="error" variant="tonal" density="compact" class="mt-3">{{ credForm.error }}</v-alert>
            </v-card-text>
            <v-card-actions>
              <v-spacer />
              <v-btn @click="credForm.show = false">Cancel</v-btn>
              <v-btn color="primary" @click="saveCred">Save</v-btn>
            </v-card-actions>
          </v-card>
        </v-dialog>
      </v-window-item>
    </v-window>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useDevicesStore } from '../stores/devices'
import api from '../api'
import CanonicalViewer from '../components/CanonicalViewer.vue'

const devStore = useDevicesStore()

// ── filter state ────────────────────────────────────────────────────────────
const deviceSearch   = ref('')
const deviceOsType   = ref('')
const deviceConnType = ref('')
const deviceActive   = ref('')

const osItems     = [{ title: 'All', value: '' }, { title: 'Linux', value: 'linux' }, { title: 'Windows', value: 'windows' }, { title: 'macOS', value: 'macos' }, { title: 'Network', value: 'network' }]
const connItems   = [{ title: 'All', value: '' }, { title: 'SSH', value: 'ssh' }, { title: 'WinRM', value: 'winrm' }, { title: 'Telnet', value: 'telnet' }, { title: 'Push', value: 'push' }]
const activeItems = [{ title: 'All', value: '' }, { title: 'Yes', value: 'true' }, { title: 'No', value: 'false' }]

function deviceFilterParams() {
  const p = {}
  if (deviceSearch.value)   p.search           = deviceSearch.value
  if (deviceOsType.value)   p.os_type          = deviceOsType.value
  if (deviceConnType.value) p.connection_type   = deviceConnType.value
  if (deviceActive.value)   p.is_active         = deviceActive.value
  return p
}

function applyDeviceFilters() { devStore.page = 1; devStore.fetchDevices(deviceFilterParams()) }
function clearDeviceFilters() {
  deviceSearch.value = ''; deviceOsType.value = ''; deviceConnType.value = ''; deviceActive.value = ''
  devStore.page = 1; devStore.fetchDevices()
}

// ── table headers ────────────────────────────────────────────────────────────
const deviceHeaders = [
  { title: 'Name',       key: 'name' },
  { title: 'Hostname',   key: 'hostname' },
  { title: 'Type',       key: 'device_type' },
  { title: 'OS',         key: 'os_type' },
  { title: 'Connection', key: 'connection_type' },
  { title: 'Credential', key: 'credential' },
  { title: 'Active',     key: 'is_active' },
  { title: '',           key: 'actions', sortable: false, align: 'end' },
]

const credHeaders = [
  { title: 'Name',     key: 'name' },
  { title: 'Type',     key: 'credential_type' },
  { title: 'Username', key: 'username' },
  { title: 'Notes',    key: 'notes' },
  { title: '',         key: 'actions', sortable: false, align: 'end' },
]

// ── tabs ─────────────────────────────────────────────────────────────────────
const activeTab = ref('devices')

// ── snackbar ─────────────────────────────────────────────────────────────────
const snackbar = ref({ show: false, ok: true, msg: '' })
function showSnack(ok, msg) { snackbar.value = { show: true, ok, msg } }

// ── device viewer ─────────────────────────────────────────────────────────────
const viewerOpen = ref(false)
const viewer     = ref({ device: null, tab: 'info', baseline: null, baselineLoading: false })

function fmt(iso) { return new Date(iso).toLocaleString() }

function infoRows(d) {
  return [
    { label: 'Name',        value: d.name },
    { label: 'Hostname',    value: d.hostname },
    { label: 'FQDN',        value: d.fqdn || '—' },
    { label: 'Port',        value: d.port },
    { label: 'Device Type', value: d.device_type },
    { label: 'OS Type',     value: d.os_type },
    { label: 'Connection',  value: d.connection_type },
    { label: 'Credential',  value: credName(d.credential) },
    { label: 'Active',      value: d.is_active ? 'Yes' : 'No' },
    ...(d.tags?.length ? [{ label: 'Tags',  value: d.tags.join(', ') }] : []),
    ...(d.notes         ? [{ label: 'Notes', value: d.notes }]          : []),
  ]
}

function openViewer(device) {
  viewer.value = { device, tab: 'info', baseline: null, baselineLoading: false }
  viewerOpen.value = true
}

async function loadBaseline() {
  if (viewer.value.baseline !== null || viewer.value.baselineLoading) return
  viewer.value.baselineLoading = true
  try {
    const { data } = await api.get('/baselines/', { params: { device: viewer.value.device.id } })
    viewer.value.baseline = (data.results ?? data)[0] ?? null
  } finally {
    viewer.value.baselineLoading = false
  }
}

// ── credentials ───────────────────────────────────────────────────────────────
const credentials = ref([])
const credLoading = ref(false)

const credentialItems = computed(() => [
  { title: '— none (use inline fields) —', value: null },
  ...credentials.value.map(c => ({ title: `${c.name} (${c.credential_type})`, value: c.id })),
])

const credTypeItems = [
  { title: 'Username / Password', value: 'password' },
  { title: 'Username / Private Key', value: 'private_key' },
  { title: 'API Token', value: 'api_token' },
]

async function loadCredentials() {
  credLoading.value = true
  try {
    const { data } = await api.get('/devices/credentials/', { params: { page_size: 500 } })
    credentials.value = data.results ?? data
  } finally {
    credLoading.value = false
  }
}

function credName(credId) {
  if (!credId) return '—'
  const c = credentials.value.find(c => c.id === credId)
  return c ? c.name : `#${credId}`
}

const credForm = ref(blankCred())
function blankCred() {
  return { show: false, id: null, name: '', credential_type: 'password', username: '', password: '', private_key: '', token: '', notes: '', error: '' }
}
function openNewCred()  { credForm.value = { ...blankCred(), show: true } }
function openEditCred(c) {
  credForm.value = { ...blankCred(), show: true, id: c.id, name: c.name, credential_type: c.credential_type, username: c.username || '', notes: c.notes || '' }
}

async function saveCred() {
  credForm.value.error = ''
  const payload = { name: credForm.value.name, credential_type: credForm.value.credential_type, username: credForm.value.username, notes: credForm.value.notes }
  if (credForm.value.password)    payload.password    = credForm.value.password
  if (credForm.value.private_key) payload.private_key = credForm.value.private_key
  if (credForm.value.token)       payload.token       = credForm.value.token
  try {
    if (credForm.value.id) {
      const { data } = await api.patch(`/devices/credentials/${credForm.value.id}/`, payload)
      const idx = credentials.value.findIndex(c => c.id === credForm.value.id)
      if (idx !== -1) credentials.value[idx] = data
    } else {
      const { data } = await api.post('/devices/credentials/', payload)
      credentials.value.push(data)
    }
    credForm.value.show = false
  } catch (e) {
    credForm.value.error = JSON.stringify(e.response?.data ?? 'Save failed.')
  }
}

async function removeCred(id) {
  if (!confirm('Delete this credential?')) return
  await api.delete(`/devices/credentials/${id}/`)
  credentials.value = credentials.value.filter(c => c.id !== id)
}

// ── devices ───────────────────────────────────────────────────────────────────
const testing   = ref(null)
const collecting = ref(null)

const DEFAULT_PORTS = { ssh: 22, telnet: 23, winrm: 5985, https: 443, push: null }
const TESTABLE_TYPES = new Set(['ssh', 'telnet', 'winrm'])
function canTestConnection(type) { return TESTABLE_TYPES.has(type) }
function defaultPort(t) { return DEFAULT_PORTS[t] ?? '' }

const deviceTypeItems = [
  { title: 'Linux',          value: 'linux' },
  { title: 'Windows',        value: 'windows' },
  { title: 'macOS',          value: 'macos' },
  { title: 'Network Device', value: 'network' },
  { title: 'Other',          value: 'other' },
]
const osTypeItems = [
  { title: 'Linux',     value: 'linux' },
  { title: 'Windows',   value: 'windows' },
  { title: 'macOS',     value: 'macos' },
  { title: 'Cisco IOS', value: 'ios' },
  { title: 'Junos',     value: 'junos' },
  { title: 'Other',     value: 'other' },
]
const connTypeItems = [
  { title: 'SSH',        value: 'ssh' },
  { title: 'Telnet',     value: 'telnet' },
  { title: 'WinRM',      value: 'winrm' },
  { title: 'HTTPS / API', value: 'https' },
  { title: 'Push',       value: 'push' },
]

function onConnectionTypeChange() {
  const def = DEFAULT_PORTS[deviceForm.value.connection_type]
  if (def) deviceForm.value.port = def
}

const deviceForm = ref(blankDevice())
function blankDevice() {
  return { show: false, id: null, name: '', hostname: '', fqdn: '', port: 22, device_type: 'linux', os_type: 'linux', connection_type: 'ssh', credential: null, username: '', password: '', host_key: '', tagsRaw: '', notes: '', is_active: true, error: '', testing: false, testResult: null }
}
function openNewDevice()  { deviceForm.value = { ...blankDevice(), show: true } }
function openEditDevice(d) {
  deviceForm.value = { ...blankDevice(), show: true, id: d.id, name: d.name, hostname: d.hostname, fqdn: d.fqdn || '', port: d.port, device_type: d.device_type, os_type: d.os_type, connection_type: d.connection_type, credential: d.credential ?? null, host_key: d.host_key || '', tagsRaw: (d.tags ?? []).join(', '), notes: d.notes || '', is_active: d.is_active }
}

async function saveDevice() {
  deviceForm.value.error = ''
  const payload = { name: deviceForm.value.name, hostname: deviceForm.value.hostname, fqdn: deviceForm.value.fqdn, port: deviceForm.value.port, device_type: deviceForm.value.device_type, os_type: deviceForm.value.os_type, connection_type: deviceForm.value.connection_type, credential: deviceForm.value.credential, host_key: deviceForm.value.host_key, tags: deviceForm.value.tagsRaw.split(',').map(t => t.trim()).filter(Boolean), notes: deviceForm.value.notes, is_active: deviceForm.value.is_active }
  if (deviceForm.value.username) payload.username = deviceForm.value.username
  if (deviceForm.value.password) payload.password = deviceForm.value.password
  try {
    if (deviceForm.value.id) await devStore.updateDevice(deviceForm.value.id, payload)
    else await devStore.createDevice(payload)
    deviceForm.value.show = false
  } catch (e) {
    deviceForm.value.error = JSON.stringify(e.response?.data ?? 'Save failed.')
  }
}

async function removeDevice(id) {
  if (confirm('Delete this device?')) await devStore.deleteDevice(id)
}

async function collect(device) {
  collecting.value = device.id
  try {
    const { data } = await api.post(`/devices/${device.id}/collect/`)
    showSnack(true, `✓ ${device.name}: ${data.detail}`)
  } catch (e) {
    showSnack(false, `✗ ${device.name}: ${e.response?.data?.detail ?? 'Failed to start collection.'}`)
  } finally {
    collecting.value = null
  }
}

async function testConn(device) {
  testing.value = device.id
  try {
    const { data } = await api.post(`/devices/${device.id}/test-connection/`)
    showSnack(true, `✓ ${device.name}: ${data.detail}`)
  } catch (e) {
    showSnack(false, `✗ ${device.name}: ${e.response?.data?.detail ?? 'Connection failed.'}`)
  } finally {
    testing.value = null
  }
}

async function testConnInModal() {
  deviceForm.value.testing = true
  deviceForm.value.testResult = null
  try {
    let data
    if (deviceForm.value.id) {
      ;({ data } = await api.post(`/devices/${deviceForm.value.id}/test-connection/`))
    } else {
      ;({ data } = await api.post('/devices/test-connection/', { connection_type: deviceForm.value.connection_type, hostname: deviceForm.value.hostname, port: deviceForm.value.port, host_key: deviceForm.value.host_key, credential: deviceForm.value.credential, username: deviceForm.value.username, password: deviceForm.value.password }))
    }
    deviceForm.value.testResult = { ok: true, detail: data.detail }
  } catch (e) {
    const resp = e.response?.data
    deviceForm.value.testResult = { ok: false, detail: resp?.detail ?? resp?.error ?? JSON.stringify(resp) ?? 'Connection failed.' }
  } finally {
    deviceForm.value.testing = false
  }
}

onMounted(() => {
  devStore.fetchDevices()
  loadCredentials()
})
</script>
