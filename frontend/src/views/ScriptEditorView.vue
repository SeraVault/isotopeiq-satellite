<template>
  <!-- fill-height makes this take the full v-main height; d-flex flex-column stacks toolbar → meta → workspace -->
  <v-sheet class="d-flex flex-column fill-height" color="background">

    <!-- ── Toolbar ───────────────────────────────────────────────────────── -->
    <v-toolbar color="secondary" density="compact" flat>
      <v-btn icon="mdi-arrow-left" variant="text" @click="goBack" />
      <v-toolbar-title>{{ isNew ? 'New Script' : 'Edit Script' }}</v-toolbar-title>
      <template #append>
        <span v-if="saveError" class="text-error text-caption mr-3">{{ saveError }}</span>
        <v-btn icon="mdi-help-circle-outline" variant="text" size="small" class="mr-1" @click="showHelp = true" />
        <v-btn variant="text" size="small" class="mr-1" @click="goBack">Cancel</v-btn>
        <v-btn color="primary" size="small" variant="tonal" :loading="saving" class="mr-2" @click="save">Save</v-btn>
      </template>
    </v-toolbar>

    <!-- ── Placeholders help dialog ──────────────────────────────────────── -->
    <v-dialog v-model="showHelp" max-width="600" scrollable>
      <v-card rounded="lg">
        <v-card-title class="d-flex align-center pt-4 pb-2">
          <v-icon icon="mdi-code-braces" class="mr-2" color="primary" />
          Script Placeholders
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" @click="showHelp = false" />
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-5" style="font-size:0.92rem;line-height:1.7">
          <p v-pre class="mb-4">
            Use <code>{{VARIABLE}}</code> syntax anywhere in your script. Satellite substitutes
            the values at runtime from the device's credential record — secrets are never stored
            in the script itself.
          </p>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">Credential / Auth</div>
          <v-table density="compact" class="mb-4 rounded-lg" style="border:1px solid rgba(0,0,0,.12)">
            <tbody v-pre>
              <tr><td style="width:170px"><code>{{USERNAME}}</code></td><td>Login username</td></tr>
              <tr><td><code>{{PASSWORD}}</code></td><td>Login password</td></tr>
              <tr><td><code>{{PRIVATE_KEY}}</code></td><td>PEM private key</td></tr>
              <tr><td><code>{{TOKEN}}</code></td><td>API token</td></tr>
            </tbody>
          </v-table>

          <div class="text-subtitle-2 font-weight-bold mb-2">Elevation</div>
          <v-table density="compact" class="mb-4 rounded-lg" style="border:1px solid rgba(0,0,0,.12)">
            <tbody v-pre>
              <tr><td style="width:170px"><code>{{ELEVATE}}</code></td><td>Elevation method derived from credential type: <code>sudo_pass</code> (password cred), <code>sudo</code> (private key), <code>none</code> (token or no cred). Use this to branch your script's privilege logic.</td></tr>
              <tr><td><code>{{ELEVATE_PASS}}</code></td><td>The credential password — alias for <code>{{PASSWORD}}</code>, named for clarity in sudo contexts. Example: <code>echo "{{ELEVATE_PASS}}" | sudo -S whoami</code></td></tr>
              <tr><td><code>{{ENABLE_PASS}}</code></td><td>Enable / privileged-exec password for network devices such as Cisco IOS. Same value as <code>{{PASSWORD}}</code>, named for clarity. Example: send <code>enable</code> then <code>{{ENABLE_PASS}}</code> to enter privileged mode.</td></tr>
            </tbody>
          </v-table>

          <div class="text-subtitle-2 font-weight-bold mb-2">Device Identity</div>
          <v-table density="compact" class="mb-4 rounded-lg" style="border:1px solid rgba(0,0,0,.12)">
            <tbody v-pre>
              <tr><td style="width:170px"><code>{{HOSTNAME}}</code></td><td>Device hostname or IP address</td></tr>
              <tr><td><code>{{FQDN}}</code></td><td>Fully qualified domain name</td></tr>
              <tr><td><code>{{PORT}}</code></td><td>Connection port</td></tr>
              <tr><td><code>{{DEVICE_TYPE}}</code></td><td>Device type — <code>linux</code>, <code>windows</code>, <code>network</code>, etc.</td></tr>
              <tr><td><code>{{OS_TYPE}}</code></td><td>OS type — <code>linux</code>, <code>windows</code>, <code>ios</code>, <code>junos</code>, etc.</td></tr>
              <tr><td><code>{{CONNECTION_TYPE}}</code></td><td>Transport in use — <code>ssh</code>, <code>telnet</code>, <code>winrm</code>, <code>agent</code></td></tr>
            </tbody>
          </v-table>

          <div class="text-subtitle-2 font-weight-bold mb-2">Satellite</div>
          <v-table density="compact" class="rounded-lg" style="border:1px solid rgba(0,0,0,.12)">
            <tbody v-pre>
              <tr><td style="width:170px"><code>{{SATELLITE_URL}}</code></td><td>Base URL of this Satellite server — useful in deployment scripts that need to call back home</td></tr>
            </tbody>
          </v-table>
        </v-card-text>
      </v-card>
    </v-dialog>

    <!-- ── Metadata bar ───────────────────────────────────────────────────── -->
    <v-sheet
      color="surface-variant"
      class="d-flex flex-wrap align-center ga-2 pa-2 flex-shrink-0 border-b"
    >
      <v-text-field v-model="form.name" label="Name *" density="compact" variant="outlined"
        hide-details style="min-width:180px;max-width:240px" />
      <v-select v-model="form.script_type" label="Type" density="compact" variant="outlined"
        hide-details style="min-width:140px;max-width:170px"
        :items="[
          { title: 'Collection',  value: 'collection' },
          { title: 'Parser',      value: 'parser' },
          { title: 'Deployment',  value: 'deployment' },
          { title: 'Utility',     value: 'utility' },
        ]" item-title="title" item-value="value" />
      <v-select v-model="form.run_on" label="Execution" density="compact" variant="outlined"
        hide-details style="min-width:160px;max-width:200px"
        :items="[
          { title: 'Push to device',    value: 'client' },
          { title: 'Run on Satellite',  value: 'server' },
          { title: 'Both',              value: 'both' },
        ]" item-title="title" item-value="value" />
      <v-select v-model="form.language" label="Language" density="compact" variant="outlined"
        hide-details style="min-width:120px;max-width:155px"
        :items="form.run_on === 'server' ? [{ title: 'Python', value: 'python' }] : langItems"
        item-title="title" item-value="value" />
      <v-select v-model="form.target_os" label="Target OS" density="compact" variant="outlined"
        hide-details style="min-width:120px;max-width:145px"
        :items="[
          { title: 'Any',     value: 'any' },
          { title: 'Linux',   value: 'linux' },
          { title: 'Windows', value: 'windows' },
          { title: 'macOS',   value: 'macos' },
        ]" item-title="title" item-value="value" />
      <v-text-field v-model="form.version" label="Version" density="compact" variant="outlined"
        hide-details style="max-width:85px" />
      <v-text-field v-model="form.description" label="Description" density="compact" variant="outlined"
        hide-details style="min-width:160px;flex:1" />
      <v-checkbox v-model="form.is_active" label="Active" density="compact" hide-details class="flex-shrink-0 align-self-center" />
    </v-sheet>

    <!-- ── Workspace (fills remaining height) ────────────────────────────── -->
    <div class="d-flex flex-row flex-grow-1" style="min-height:0;overflow:hidden">

      <!-- Code editor pane -->
      <div class="d-flex flex-column" :style="{ width: editorWidthPct + '%' }" style="min-width:0;overflow:hidden;padding:6px">
        <CodeEditor v-model="form.content" :language="form.language" style="height:100%" />
      </div>

      <!-- Drag-to-resize handle -->
      <div class="sev-resizer" @mousedown="startResize" />

      <!-- Output / test pane -->
      <div class="d-flex flex-column flex-grow-1" style="min-width:0;overflow:hidden">

        <!-- Run bar -->
        <v-sheet color="surface-variant" class="d-flex flex-wrap align-center ga-2 pa-2 flex-shrink-0 border-b">
          <!-- Device picker — required for push-to-device scripts, optional for satellite scripts that connect to a device -->
          <v-autocomplete
            v-model="test.deviceId"
            :items="test.devices"
            item-title="name"
            item-value="id"
            :label="form.run_on === 'server' ? 'Device (optional)' : 'Device *'"
            density="compact"
            variant="outlined"
            hide-details
            clearable
            :loading="test.devicesLoading"
            style="min-width:200px;max-width:260px"
            no-filter
          />
          <!-- Input — for server-side scripts that consume previous step output -->
          <v-textarea
            v-if="form.run_on === 'server'"
            v-model="test.stdin"
            label="Input (previous step output — leave blank if not needed)"
            density="compact"
            variant="outlined"
            hide-details
            rows="1"
            auto-grow
            clearable
            style="min-width:260px;flex:1"
          />
          <v-btn
            color="primary"
            size="small"
            variant="tonal"
            prepend-icon="mdi-play"
            :loading="test.running"
            :disabled="form.run_on !== 'server' && !test.deviceId"
            @click="runTest"
          >Run</v-btn>
          <v-spacer />
          <span v-if="test.result !== null" class="text-caption text-medium-emphasis mr-1">{{ test.durationMs }}ms</span>
          <v-btn
            v-if="test.result !== null || test.error || test.printOutput"
            size="small"
            variant="text"
            prepend-icon="mdi-content-copy"
            :color="test.copied ? 'success' : undefined"
            @click="copyOutput"
          >{{ test.copied ? 'Copied' : 'Copy' }}</v-btn>
          <v-btn
            v-if="test.result"
            size="small"
            variant="text"
            prepend-icon="mdi-arrow-left-bold"
            title="Use this output as input for the next test run"
            @click="test.stdin = test.result"
          >Use as input</v-btn>
        </v-sheet>

        <!-- Output body -->
        <div class="flex-grow-1 overflow-y-auto pa-3" style="min-height:0">
          <div v-if="test.result === null && !test.error && !test.running" class="text-center text-medium-emphasis text-body-2 pt-8">
            Run the script to see output here.
          </div>
          <div v-if="test.running" class="d-flex align-center justify-center pt-8">
            <v-progress-circular indeterminate size="24" class="mr-2" />Running…
          </div>
          <v-alert v-if="test.error && !test.running" type="error" variant="tonal" class="mb-3">
            <pre style="white-space:pre-wrap;word-break:break-word;font-size:.82rem;margin:0">{{ test.error }}</pre>
          </v-alert>
          <template v-if="test.printOutput && !test.running">
            <div class="text-caption font-weight-bold text-medium-emphasis text-uppercase mb-1">stdout (print output)</div>
            <pre class="mb-3" style="white-space:pre-wrap;word-break:break-word;font-size:.82rem;line-height:1.55;margin:0;opacity:.8">{{ test.printOutput }}</pre>
            <v-divider class="mb-3" />
          </template>
          <pre v-if="test.result" style="white-space:pre-wrap;word-break:break-word;font-size:.82rem;line-height:1.55;margin:0">{{ test.result }}</pre>
        </div>

      </div>
    </div>

  </v-sheet>
</template>

<script setup>
import { ref, reactive, watch, onMounted, onBeforeUnmount } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '../api'
import CodeEditor from '../components/CodeEditor.vue'

const route  = useRoute()
const router = useRouter()

const isNew     = !route.params.id
const saving    = ref(false)
const saveError = ref('')
const showHelp  = ref(false)

const langItems = [
  { title: 'Shell / Bash', value: 'shell' },
  { title: 'PowerShell',   value: 'powershell' },
  { title: 'Batch (.bat)', value: 'batch' },
  { title: 'VBScript',     value: 'vbscript' },
  { title: 'Python',       value: 'python' },
  { title: 'JavaScript',   value: 'javascript' },
  { title: 'SQL',          value: 'sql' },
]

const form = reactive({
  name: '', description: '', script_type: 'collection', run_on: 'client',
  target_os: 'any', language: 'shell', version: '1.0.0', is_active: true,
  content: '',
})

// When creating a new script, auto-switch language default to match execution context.
watch(() => form.run_on, run_on => {
  if (!isNew) return
  form.language = run_on === 'server' ? 'python' : 'shell'
})

const test = reactive({
  deviceId: null, devices: [], devicesLoading: false,
  stdin: '', running: false,
  result: null, printOutput: null, error: null, durationMs: 0, copied: false,
})

onMounted(async () => {
  loadDevices()
  if (!isNew) {
    try {
      const { data } = await api.get(`/scripts/${route.params.id}/`)
      Object.assign(form, {
        name:        data.name,
        description: data.description ?? '',
        script_type: data.script_type,
        run_on:      data.run_on ?? 'client',
        target_os:   data.target_os,
        language:    data.language || 'shell',
        version:     data.version,
        is_active:   data.is_active,
        content:     data.content,
      })
    } catch {
      saveError.value = 'Failed to load script.'
    }
  }
})

async function loadDevices() {
  test.devicesLoading = true
  try {
    const res = await api.get('/devices/', { params: { page_size: 500 } })
    test.devices = res.data?.results ?? res.data ?? []
  } finally {
    test.devicesLoading = false
  }
}

async function save() {
  saveError.value = ''
  if (!form.name.trim()) { saveError.value = 'Name is required.'; return }
  saving.value = true
  const payload = {
    name: form.name, description: form.description,
    script_type: form.script_type, run_on: form.run_on,
    target_os: form.target_os, language: form.language,
    version: form.version, is_active: form.is_active,
    content: form.content,
  }
  try {
    if (isNew) {
      await api.post('/scripts/', payload)
    } else {
      await api.patch(`/scripts/${route.params.id}/`, payload)
    }
    router.push('/scripts')
  } catch (e) {
    saveError.value = JSON.stringify(e.response?.data ?? 'Save failed.')
  } finally {
    saving.value = false
  }
}

function goBack() { router.push('/scripts') }

async function runTest() {
  test.running = true
  test.result  = null
  test.printOutput = null
  test.error   = null
  test.copied  = false
  try {
    const body = {
      content:  form.content,
      run_on:   form.run_on === 'both' ? 'client' : form.run_on,
      language: form.language,
    }
    if (test.deviceId) body.device_id = test.deviceId
    if (test.stdin)    body.stdin      = test.stdin
    const res = await api.post('/scripts/test/', body)
    test.result      = res.data.output    || ''
    test.printOutput = res.data.print_output || null
    test.error       = res.data.error     || null
    test.durationMs  = res.data.duration_ms ?? 0
  } catch (e) {
    test.error = e.response?.data?.error ?? JSON.stringify(e.response?.data) ?? 'Request failed.'
  } finally {
    test.running = false
  }
}

async function copyOutput() {
  const parts = []
  if (test.printOutput) parts.push(test.printOutput)
  if (test.result || test.error) parts.push(test.result || test.error || '')
  await navigator.clipboard.writeText(parts.join('\n'))
  test.copied = true
  setTimeout(() => { test.copied = false }, 2000)
}

// Resizer
const editorWidthPct = ref(58)
let resizing = false, resizeStartX = 0, resizeStartPct = 58

function startResize(e) {
  resizing = true
  resizeStartX = e.clientX
  resizeStartPct = editorWidthPct.value
  document.addEventListener('mousemove', onResizeMove)
  document.addEventListener('mouseup', stopResize)
}
function onResizeMove(e) {
  if (!resizing) return
  editorWidthPct.value = Math.min(80, Math.max(20, resizeStartPct + ((e.clientX - resizeStartX) / window.innerWidth) * 100))
}
function stopResize() {
  resizing = false
  document.removeEventListener('mousemove', onResizeMove)
  document.removeEventListener('mouseup', stopResize)
}
onBeforeUnmount(() => {
  document.removeEventListener('mousemove', onResizeMove)
  document.removeEventListener('mouseup', stopResize)
})
</script>

<style scoped>
.sev-resizer {
  width: 5px;
  flex-shrink: 0;
  cursor: col-resize;
}
</style>
