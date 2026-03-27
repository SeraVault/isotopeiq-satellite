<template>
  <div>
    <!-- ── Tab bar ─────────────────────────────────────────────────────── -->
    <h1>Devices</h1>
    <div class="tabs">
      <div
        v-for="tab in ['Devices', 'Credentials']"
        :key="tab"
        class="tab"
        :class="{ active: activeTab === tab }"
        @click="activeTab = tab"
      >{{ tab }}</div>
    </div>

    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- DEVICES TAB                                                        -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <template v-if="activeTab === 'Devices'">
      <button class="btn-primary" @click="openNewDevice" style="margin-bottom:1rem">+ Add Device</button>

      <div v-if="devStore.loading">Loading…</div>
      <table v-else>
        <thead>
          <tr>
            <th>Name</th><th>Hostname</th><th>Type</th><th>OS</th>
            <th>Connection</th><th>Credential</th><th>Active</th><th>Actions</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="d in devStore.devices" :key="d.id">
            <td>{{ d.name }}</td>
            <td>{{ d.hostname }}</td>
            <td>{{ d.device_type }}</td>
            <td>{{ d.os_type }}</td>
            <td>{{ d.connection_type }}</td>
            <td>{{ credName(d.credential) }}</td>
            <td>{{ d.is_active ? 'Yes' : 'No' }}</td>
            <td>
              <button @click="testConn(d)" :disabled="testing === d.id">
                {{ testing === d.id ? 'Testing…' : 'Test' }}
              </button>
              <button @click="openEditDevice(d)">Edit</button>
              <button class="btn-danger" @click="removeDevice(d.id)">Delete</button>
            </td>
          </tr>
          <tr v-if="!devStore.devices.length">
            <td colspan="8" style="color:#888;text-align:center">No devices yet.</td>
          </tr>
        </tbody>
      </table>

      <!-- Test-connection result toast -->
      <div v-if="testResult" :style="`margin-top:.75rem;padding:.6rem 1rem;border-radius:4px;background:${testResult.ok ? '#d4edda' : '#f8d7da'};color:${testResult.ok ? '#155724' : '#721c24'}`">
        {{ testResult.msg }}
      </div>

      <!-- Device modal -->
      <div v-if="deviceForm.show" class="modal">
        <div class="modal-box modal-md">
          <h2>{{ deviceForm.id ? 'Edit' : 'Add' }} Device</h2>
          <form @submit.prevent="saveDevice">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:.75rem">
              <label>Name <input v-model="deviceForm.name" required /></label>
              <label>Hostname / IP <input v-model="deviceForm.hostname" required /></label>
              <label>FQDN <input v-model="deviceForm.fqdn" placeholder="optional" /></label>
              <label>
                Port <small style="color:#888;font-weight:400">(override only if non-standard)</small>
                <input v-model.number="deviceForm.port" type="number" min="1" max="65535" :placeholder="defaultPort(deviceForm.connection_type)" />
              </label>
              <label>Device Type
                <select v-model="deviceForm.device_type">
                  <option value="linux">Linux</option>
                  <option value="windows">Windows</option>
                  <option value="macos">macOS</option>
                  <option value="network">Network Device</option>
                  <option value="other">Other</option>
                </select>
              </label>
              <label>OS Type
                <select v-model="deviceForm.os_type">
                  <option value="linux">Linux</option>
                  <option value="windows">Windows</option>
                  <option value="macos">macOS</option>
                  <option value="ios">Cisco IOS</option>
                  <option value="junos">Junos</option>
                  <option value="other">Other</option>
                </select>
              </label>
              <label>Connection Type
                <select v-model="deviceForm.connection_type" @change="onConnectionTypeChange">
                  <option value="ssh">SSH</option>
                  <option value="telnet">Telnet</option>
                  <option value="winrm">WinRM</option>
                  <option value="https">HTTPS / API</option>
                  <option value="push">Push</option>
                </select>
              </label>
              <label>Credential
                <select v-model="deviceForm.credential">
                  <option :value="null">— none (use inline fields) —</option>
                  <option v-for="c in credentials" :key="c.id" :value="c.id">
                    {{ c.name }} ({{ c.credential_type }})
                  </option>
                </select>
              </label>
            </div>

            <label v-if="deviceForm.connection_type === 'ssh'" style="margin-top:.75rem">
              SSH Host Key <small style="color:#888">(optional — omitting disables host verification)</small>
              <input v-model="deviceForm.host_key" placeholder="base64 public key — run: ssh-keyscan -t rsa <hostname>" style="font-family:monospace;font-size:.82rem" />
            </label>

            <details style="margin-top:.75rem">
              <summary style="cursor:pointer;color:#555;font-size:.9rem">Inline credentials (fallback if no Credential selected)</summary>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:.75rem;margin-top:.5rem">
                <label>Username <input v-model="deviceForm.username" autocomplete="off" /></label>
                <label>Password <input v-model="deviceForm.password" type="password" autocomplete="new-password" /></label>
              </div>
            </details>
            <label style="margin-top:.75rem">
              Tags (comma-separated)
              <input v-model="deviceForm.tagsRaw" placeholder="prod, linux, web" />
            </label>
            <label style="margin-top:.75rem">Notes <textarea v-model="deviceForm.notes" rows="2"></textarea></label>
            <label style="margin-top:.5rem"><input v-model="deviceForm.is_active" type="checkbox" /> Active</label>

            <p v-if="deviceForm.error" class="error" style="margin-top:.5rem">{{ deviceForm.error }}</p>

            <!-- Test connection result (inside modal) -->
            <div v-if="deviceForm.testResult" :style="`margin-top:.85rem;padding:.75rem 1rem;border-radius:6px;border:1px solid ${deviceForm.testResult.ok ? '#b7dbb7' : '#f5c6cb'};background:${deviceForm.testResult.ok ? '#f0fff0' : '#fff5f5'}`">
              <div style="display:flex;align-items:center;gap:.5rem;font-weight:600" :style="`color:${deviceForm.testResult.ok ? '#155724' : '#721c24'}`">
                <span>{{ deviceForm.testResult.ok ? '✓ Connection successful' : '✗ Connection failed' }}</span>
              </div>
              <pre v-if="deviceForm.testResult.detail" style="margin-top:.5rem;background:transparent;color:inherit;padding:0;font-size:.82rem;white-space:pre-wrap;word-break:break-word">{{ deviceForm.testResult.detail }}</pre>
            </div>

            <div style="margin-top:1rem;display:flex;align-items:center;gap:.5rem;flex-wrap:wrap">
              <button class="btn-primary" type="submit">Save</button>
              <button type="button" @click="deviceForm.show = false">Cancel</button>
              <span style="flex:1"></span>
              <button
                type="button"
                :disabled="!deviceForm.hostname || deviceForm.testing || !canTestConnection(deviceForm.connection_type)"
                :title="canTestConnection(deviceForm.connection_type) ? 'Test connection using the current form values' : `Connection testing is not supported for ${deviceForm.connection_type.toUpperCase()}`"
                @click="testConnInModal"
              >{{ deviceForm.testing ? 'Testing…' : 'Test Connection' }}</button>
            </div>
          </form>
        </div>
      </div>
    </template>

    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- CREDENTIALS TAB                                                    -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <template v-else>
      <button class="btn-primary" @click="openNewCred" style="margin-bottom:1rem">+ Add Credential</button>

      <div v-if="credLoading">Loading…</div>
      <table v-else>
        <thead>
          <tr><th>Name</th><th>Type</th><th>Username</th><th>Notes</th><th>Actions</th></tr>
        </thead>
        <tbody>
          <tr v-for="c in credentials" :key="c.id">
            <td>{{ c.name }}</td>
            <td>{{ c.credential_type }}</td>
            <td>{{ c.username }}</td>
            <td>{{ c.notes || '—' }}</td>
            <td>
              <button @click="openEditCred(c)">Edit</button>
              <button class="btn-danger" @click="removeCred(c.id)">Delete</button>
            </td>
          </tr>
          <tr v-if="!credentials.length">
            <td colspan="5" style="color:#888;text-align:center">No credentials yet.</td>
          </tr>
        </tbody>
      </table>

      <!-- Credential modal -->
      <div v-if="credForm.show" class="modal">
        <div class="modal-box modal-sm">
          <h2>{{ credForm.id ? 'Edit' : 'Add' }} Credential</h2>
          <form @submit.prevent="saveCred">
            <label>Name <input v-model="credForm.name" required /></label>
            <label style="margin-top:.75rem">Type
              <select v-model="credForm.credential_type">
                <option value="password">Username / Password</option>
                <option value="private_key">Username / Private Key</option>
                <option value="api_token">API Token</option>
              </select>
            </label>

            <template v-if="credForm.credential_type !== 'api_token'">
              <label style="margin-top:.75rem">Username <input v-model="credForm.username" /></label>
            </template>

            <template v-if="credForm.credential_type === 'password'">
              <label style="margin-top:.75rem">
                Password
                <input v-model="credForm.password" type="password" autocomplete="new-password" placeholder="leave blank to keep existing" />
              </label>
            </template>

            <template v-if="credForm.credential_type === 'private_key'">
              <label style="margin-top:.75rem">
                Private Key (PEM)
                <textarea v-model="credForm.private_key" rows="8" style="font-family:monospace;font-size:.82rem" placeholder="-----BEGIN ... PRIVATE KEY-----&#10;...&#10;-----END ... PRIVATE KEY-----"></textarea>
              </label>
            </template>

            <template v-if="credForm.credential_type === 'api_token'">
              <label style="margin-top:.75rem">
                Token
                <input v-model="credForm.token" type="password" autocomplete="new-password" placeholder="leave blank to keep existing" />
              </label>
            </template>

            <label style="margin-top:.75rem">Notes <textarea v-model="credForm.notes" rows="2"></textarea></label>

            <p v-if="credForm.error" class="error" style="margin-top:.5rem">{{ credForm.error }}</p>
            <div style="margin-top:1rem">
              <button class="btn-primary" type="submit">Save</button>
              <button type="button" @click="credForm.show = false">Cancel</button>
            </div>
          </form>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useDevicesStore } from '../stores/devices'
import api from '../api'

const devStore = useDevicesStore()

// ── tab ────────────────────────────────────────────────────────────────────
const activeTab = ref('Devices')

// ── credentials ────────────────────────────────────────────────────────────
const credentials = ref([])
const credLoading = ref(false)

async function loadCredentials() {
  credLoading.value = true
  try {
    const { data } = await api.get('/devices/credentials/')
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
function openNewCred() { credForm.value = { ...blankCred(), show: true } }
function openEditCred(c) { credForm.value = { ...blankCred(), show: true, id: c.id, name: c.name, credential_type: c.credential_type, username: c.username || '', notes: c.notes || '' } }

async function saveCred() {
  credForm.value.error = ''
  const payload = {
    name: credForm.value.name,
    credential_type: credForm.value.credential_type,
    username: credForm.value.username,
    notes: credForm.value.notes,
  }
  if (credForm.value.password) payload.password = credForm.value.password
  if (credForm.value.private_key) payload.private_key = credForm.value.private_key
  if (credForm.value.token) payload.token = credForm.value.token

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

// ── devices ────────────────────────────────────────────────────────────────
const testing = ref(null)
const testResult = ref(null)

const DEFAULT_PORTS = { ssh: 22, telnet: 23, winrm: 5985, https: 443, push: null }
const TESTABLE_TYPES = new Set(['ssh', 'telnet', 'winrm'])
function canTestConnection(type) { return TESTABLE_TYPES.has(type) }

function defaultPort(connectionType) {
  return DEFAULT_PORTS[connectionType] ?? ''
}

function onConnectionTypeChange() {
  const def = DEFAULT_PORTS[deviceForm.value.connection_type]
  if (def) deviceForm.value.port = def
}

const deviceForm = ref(blankDevice())
function blankDevice() {
  return {
    show: false, id: null,
    name: '', hostname: '', fqdn: '', port: 22,
    device_type: 'linux', os_type: 'linux',
    connection_type: 'ssh',
    credential: null,
    username: '', password: '',
    host_key: '', tagsRaw: '', notes: '',
    is_active: true, error: '',
    testing: false, testResult: null,
  }
}

function openNewDevice() { deviceForm.value = { ...blankDevice(), show: true } }
function openEditDevice(d) {
  deviceForm.value = {
    ...blankDevice(), show: true,
    id: d.id,
    name: d.name, hostname: d.hostname, fqdn: d.fqdn || '',
    port: d.port, device_type: d.device_type, os_type: d.os_type,
    connection_type: d.connection_type,
    credential: d.credential ?? null,
    host_key: d.host_key || '',
    tagsRaw: (d.tags ?? []).join(', '),
    notes: d.notes || '',
    is_active: d.is_active,
  }
}

async function saveDevice() {
  deviceForm.value.error = ''
  const payload = {
    name: deviceForm.value.name,
    hostname: deviceForm.value.hostname,
    fqdn: deviceForm.value.fqdn,
    port: deviceForm.value.port,
    device_type: deviceForm.value.device_type,
    os_type: deviceForm.value.os_type,
    connection_type: deviceForm.value.connection_type,
    credential: deviceForm.value.credential,
    host_key: deviceForm.value.host_key,
    tags: deviceForm.value.tagsRaw.split(',').map(t => t.trim()).filter(Boolean),
    notes: deviceForm.value.notes,
    is_active: deviceForm.value.is_active,
  }
  if (deviceForm.value.username) payload.username = deviceForm.value.username
  if (deviceForm.value.password) payload.password = deviceForm.value.password

  try {
    if (deviceForm.value.id) {
      await devStore.updateDevice(deviceForm.value.id, payload)
    } else {
      await devStore.createDevice(payload)
    }
    deviceForm.value.show = false
  } catch (e) {
    deviceForm.value.error = JSON.stringify(e.response?.data ?? 'Save failed.')
  }
}

async function removeDevice(id) {
  if (confirm('Delete this device?')) await devStore.deleteDevice(id)
}

async function testConn(device) {
  testing.value = device.id
  testResult.value = null
  try {
    const { data } = await api.post(`/devices/${device.id}/test-connection/`)
    testResult.value = { ok: true, msg: `✓ ${device.name}: ${data.detail}` }
  } catch (e) {
    const detail = e.response?.data?.detail ?? 'Connection failed.'
    testResult.value = { ok: false, msg: `✗ ${device.name}: ${detail}` }
  } finally {
    testing.value = null
    setTimeout(() => { testResult.value = null }, 6000)
  }
}

async function testConnInModal() {
  deviceForm.value.testing = true
  deviceForm.value.testResult = null
  try {
    let data
    if (deviceForm.value.id) {
      // Saved device — use stored credentials
      ;({ data } = await api.post(`/devices/${deviceForm.value.id}/test-connection/`))
    } else {
      // New device — send form fields inline
      ;({ data } = await api.post('/devices/test-connection/', {
        connection_type: deviceForm.value.connection_type,
        hostname:        deviceForm.value.hostname,
        port:            deviceForm.value.port,
        host_key:        deviceForm.value.host_key,
        credential:      deviceForm.value.credential,
        username:        deviceForm.value.username,
        password:        deviceForm.value.password,
      }))
    }
    deviceForm.value.testResult = { ok: true, detail: data.detail }
  } catch (e) {
    const resp = e.response?.data
    const detail = resp?.detail ?? resp?.error ?? JSON.stringify(resp) ?? 'Connection failed — no detail returned.'
    deviceForm.value.testResult = { ok: false, detail }
  } finally {
    deviceForm.value.testing = false
  }
}

// ── init ───────────────────────────────────────────────────────────────────
onMounted(() => {
  devStore.fetchDevices()
  loadCredentials()
})
</script>
