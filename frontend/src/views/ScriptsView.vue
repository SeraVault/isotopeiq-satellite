<template>
  <div>
    <div class="d-flex align-center mb-5">
      <div class="text-h5 font-weight-bold">Scripts</div>
      <v-spacer />
      <v-btn variant="tonal" prepend-icon="mdi-help-circle-outline" @click="showHelp = true">How it works</v-btn>
    </div>

    <!-- ── Help dialog ───────────────────────────────────────────────────── -->
    <v-dialog v-model="showHelp" max-width="720" scrollable>
      <v-card rounded="lg">
        <v-card-title class="d-flex align-center pt-4 pb-2">
          <v-icon icon="mdi-script-text-outline" class="mr-2" color="primary" />
          Scripts &amp; Collection Profiles
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" @click="showHelp = false" />
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-5" style="font-size:0.92rem;line-height:1.7">

          <p class="mb-3">
            Scripts are the executable units that Satellite uses to <strong>collect</strong>,
            <strong>parse</strong>, and optionally <strong>deploy</strong> configuration data.
            Collection Profiles bundle a collection script and a parser script together so they
            can be versioned and distributed as a single artefact. Deployment scripts are kept
            separate and assigned directly to Policies.
          </p>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">Script types</div>
          <v-table density="compact" class="mb-3 rounded-lg" style="border:1px solid rgba(0,0,0,.12)">
            <tbody>
              <tr>
                <td class="font-weight-medium" style="width:28%">Collection</td>
                <td>Runs <em>on the remote device</em> via SSH or WinRM. Its job is to gather raw configuration data and write it to stdout. Keep these scripts minimal and side-effect-free.</td>
              </tr>
              <tr>
                <td class="font-weight-medium">Parser</td>
                <td>Runs <em>on the Satellite server</em>. Receives the raw collection output via stdin and must emit a single canonical JSON document to stdout. One parser per OS family is the recommended pattern.</td>
              </tr>
              <tr>
                <td class="font-weight-medium">Deployment</td>
                <td>Optional. Pushed to the device to apply a remediation, hardening change, or golden configuration. Referenced by a Policy but only executed when explicitly triggered or when auto-remediation is enabled.</td>
              </tr>
            </tbody>
          </v-table>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">Script fields</div>
          <v-table density="compact" class="mb-3 rounded-lg" style="border:1px solid rgba(0,0,0,.12)">
            <tbody>
              <tr><td class="font-weight-medium" style="width:28%">Name</td><td>Unique identifier used when selecting scripts in a Policy.</td></tr>
              <tr><td class="font-weight-medium">Type</td><td>Collection, Parser, or Deployment — determines when and where the script is executed.</td></tr>
              <tr><td class="font-weight-medium">OS Family</td><td>Linux, Windows, macOS, or Network. Informational — used to filter the right script into a policy targeting a given OS type.</td></tr>
              <tr><td class="font-weight-medium">Language</td><td>Shell, PowerShell, Python, etc. Satellite uses this to invoke the correct interpreter on the remote host.</td></tr>
              <tr><td class="font-weight-medium">Content</td><td>The full script body. Stored encrypted at rest. Substitution placeholders like <code>{{SATELLITE_URL}}</code> are replaced at deployment time.</td></tr>
              <tr><td class="font-weight-medium">Version</td><td>Free-form version string. Displayed in job records so you know exactly which script version produced a given result.</td></tr>
              <tr><td class="font-weight-medium">Active</td><td>Inactive scripts cannot be selected in new policies but remain visible for reference and historical jobs.</td></tr>
            </tbody>
          </v-table>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">Collection Profiles</div>
          <p class="mb-3">
            A Collection Profile groups a collection script and a parser script into a named,
            versioned bundle. Collection Profiles are what Windows pull agents download from
            <code>GET /api/agents/&lt;filename&gt;</code> — the server serves the profile artefact
            and exposes its SHA-256 via <code>/api/agents/&lt;filename&gt;/info</code> so agents
            can self-update without polling unnecessarily. Deployment scripts are assigned
            separately at the Policy level.
          </p>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">Canonical JSON output</div>
          <p class="mb-3">
            Parser scripts must produce a document that conforms to the IsotopeIQ canonical schema.
            The schema covers 28 top-level sections including <code>hardware</code>, <code>os</code>,
            <code>network</code>, <code>installed_software</code>, <code>firewall_rules</code>,
            <code>services</code>, and network-device sections such as <code>vlans</code>,
            <code>acls</code>, and <code>routing_protocols</code>. All sections must be present —
            populate inapplicable ones with empty arrays or objects.
          </p>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">Recommended workflow</div>
          <ol class="pl-4" style="line-height:2">
            <li>Write and test your <strong>Collection Script</strong> manually on a target device.</li>
            <li>Pipe its output into your <strong>Parser Script</strong> locally to validate the JSON structure.</li>
            <li>Upload both scripts here, set the correct OS family and language.</li>
            <li>Create a <strong>Policy</strong> that references both scripts and assign target devices.</li>
            <li>Run the policy once manually to confirm end-to-end operation before enabling the schedule.</li>
          </ol>

        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-3">
          <v-spacer />
          <v-btn color="primary" variant="tonal" @click="showHelp = false">Got it</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-tabs v-model="activeTab" class="mb-5">
      <v-tab value="CollectionProfiles">Collection Profiles</v-tab>
      <v-tab value="Scripts">Scripts</v-tab>
    </v-tabs>

    <!-- ── PACKAGES TAB ───────────────────────────────────────────────────── -->
    <v-window v-model="activeTab">
      <v-window-item value="CollectionProfiles">
        <div class="d-flex justify-space-between align-center mb-4">
          <span class="text-body-2 text-medium-emphasis">{{ packages.length }} collection profile(s)</span>
          <v-btn color="primary" prepend-icon="mdi-plus" @click="openNewPackage">New Collection Profile</v-btn>
        </div>

        <div v-if="pkgLoading" class="text-medium-emphasis pa-4">Loading…</div>
        <v-card v-else-if="packages.length" rounded="lg" elevation="1">
          <v-table density="compact">
            <thead>
              <tr>
                <th>Name</th><th>Target OS</th><th>Version</th>
                <th>Collection Script</th><th>Parser Script</th><th>Active</th><th></th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="p in packages" :key="p.id">
                <td class="font-weight-medium">{{ p.name }}</td>
                <td>{{ p.target_os }}</td>
                <td>{{ p.version }}</td>
                <td class="text-medium-emphasis">{{ p.collection_script_detail?.name ?? '—' }}</td>
                <td class="text-medium-emphasis">{{ p.parser_script_detail?.name ?? '—' }}</td>
                <td>
                  <v-chip :color="p.is_active ? 'success' : 'default'" size="x-small" label>
                    {{ p.is_active ? 'Yes' : 'No' }}
                  </v-chip>
                </td>
                <td>
                  <v-btn size="x-small" variant="tonal" class="mr-1" @click="openEditor(p)">Edit / Test</v-btn>
                  <v-btn size="x-small" color="error" variant="tonal" @click="removePkg(p.id)">Delete</v-btn>
                </td>
              </tr>
            </tbody>
          </v-table>
        </v-card>
        <div v-else class="pa-6 text-center text-medium-emphasis">No collection profiles yet.</div>
      </v-window-item>

      <!-- ── SCRIPTS TAB ────────────────────────────────────────────────────── -->
      <v-window-item value="Scripts">
        <div class="d-flex justify-space-between align-center mb-4">
          <span class="text-body-2 text-medium-emphasis">{{ scripts.length }} script(s)</span>
          <v-btn color="primary" prepend-icon="mdi-plus" @click="openNewScriptInEditor">New Script</v-btn>
        </div>

        <div v-if="scrLoading" class="text-medium-emphasis pa-4">Loading…</div>
        <v-card v-else-if="scripts.length" rounded="lg" elevation="1">
          <v-table density="compact">
            <thead>
              <tr><th>Name</th><th>Type</th><th>Target OS</th><th>Version</th><th>Active</th><th></th></tr>
            </thead>
            <tbody>
              <tr v-for="s in scripts" :key="s.id">
                <td class="font-weight-medium">{{ s.name }}</td>
                <td>{{ s.script_type }}</td>
                <td>{{ s.target_os }}</td>
                <td>{{ s.version }}</td>
                <td>
                  <v-chip :color="s.is_active ? 'success' : 'default'" size="x-small" label>
                    {{ s.is_active ? 'Yes' : 'No' }}
                  </v-chip>
                </td>
                <td>
                  <v-btn size="x-small" variant="tonal" class="mr-1" @click="openScriptInEditor(s)">Edit</v-btn>
                  <v-btn size="x-small" color="error" variant="tonal" @click="removeScript(s.id)">Delete</v-btn>
                </td>
              </tr>
            </tbody>
          </v-table>
        </v-card>
        <div v-else class="pa-6 text-center text-medium-emphasis">No scripts yet.</div>
      </v-window-item>
    </v-window>



    <!-- ── PACKAGE EDITOR (full-screen overlay) ───────────────────────────── -->
    <div v-if="editor.show" class="pkg-overlay">

      <!-- Top bar -->
      <div class="pkg-topbar">
        <div class="pkg-topbar-left">
          <span class="pkg-title">{{ editor.scriptMode ? (editor.id ? 'Edit Script' : 'New Script') : (editor.id ? 'Edit Collection Profile' : 'New Collection Profile') }}</span>
          <span v-if="editor.saveError" class="text-error text-caption">{{ editor.saveError }}</span>
        </div>
        <div class="pkg-topbar-right">
          <v-btn variant="text" color="white" size="small" @click="editor.show = false">✕ Close</v-btn>
          <v-btn color="primary" size="small" :loading="editor.saving" @click="editor.scriptMode ? saveStandaloneScript() : savePackage()">Save</v-btn>
        </div>
      </div>

      <!-- Metadata row (package mode) -->
      <div v-if="!editor.scriptMode" class="pkg-meta">
        <v-text-field v-model="editor.name" label="Package Name" placeholder="e.g. Linux Baseline" required density="compact" variant="outlined" hide-details style="min-width:220px" />
        <v-select v-model="editor.target_os" label="Target OS" :items="['linux','windows','macos','any']" density="compact" variant="outlined" hide-details style="min-width:130px" />
        <v-text-field v-model="editor.version" label="Version" density="compact" variant="outlined" hide-details style="width:100px" />
        <v-autocomplete
          v-model="editor.deviceId"
          label="Test Device"
          :items="testDevices"
          item-title="name"
          item-value="id"
          density="compact"
          variant="outlined"
          hide-details
          style="min-width:220px"
          clearable
          no-filter
          :loading="deviceSearchLoading"
          placeholder="Search devices…"
          @update:search="onDeviceSearch"
        />
        <v-text-field v-model="editor.description" label="Description" placeholder="optional" density="compact" variant="outlined" hide-details style="min-width:220px" />
        <v-checkbox v-model="editor.is_active" label="Active" density="compact" hide-details style="align-self:center" />
      </div>

      <!-- Metadata row (script mode) -->
      <div v-if="editor.scriptMode" class="pkg-meta">
        <v-text-field v-model="editor.name" label="Script Name" required density="compact" variant="outlined" hide-details style="min-width:220px" />
        <v-select v-model="editor.target_os" label="Target OS" :items="['linux','windows','macos','any']" density="compact" variant="outlined" hide-details style="min-width:130px" />
        <v-text-field v-model="editor.version" label="Version" density="compact" variant="outlined" hide-details style="width:100px" />
        <v-autocomplete
          v-model="editor.deviceId"
          label="Test Device"
          :items="testDevices"
          item-title="name"
          item-value="id"
          density="compact"
          variant="outlined"
          hide-details
          style="min-width:220px"
          clearable
          no-filter
          :loading="deviceSearchLoading"
          placeholder="Search devices…"
          @update:search="onDeviceSearch"
        />
        <v-text-field v-model="editor.description" label="Description" placeholder="optional" density="compact" variant="outlined" hide-details style="min-width:220px" />
        <v-checkbox v-model="editor.is_active" label="Active" density="compact" hide-details style="align-self:center" />
      </div>

      <!-- Editor + results area (fills remaining space) -->
      <div class="pkg-workspace" ref="workspaceEl">

        <!-- Tabbed script editor -->
        <div class="pkg-editor-tabs">
          <button v-if="!editor.scriptMode || !editor.id || editor.scriptTab === 'collection'" :class="['pkg-tab', { 'pkg-tab--active': editor.scriptTab === 'collection' }]" @click="editor.scriptTab = 'collection'">
            Collection<span class="pkg-tab-sub">runs on device</span>
          </button>
          <button v-if="!editor.scriptMode || !editor.id || editor.scriptTab === 'parser'" :class="['pkg-tab', { 'pkg-tab--active': editor.scriptTab === 'parser' }]" @click="editor.scriptTab = 'parser'">
            Parser<span class="pkg-tab-sub">runs on server</span>
          </button>
          <button v-if="editor.scriptMode && (!editor.id || editor.scriptTab === 'deployment')" :class="['pkg-tab', { 'pkg-tab--active': editor.scriptTab === 'deployment' }]" @click="editor.scriptTab = 'deployment'">
            Deployment<span class="pkg-tab-sub">optional · runs on device</span>
          </button>
          <div class="pkg-tab-actions">
            <template v-if="editor.scriptTab === 'collection'">
              <v-select v-model="editor.collectionLang" :items="langItems" item-title="title" item-value="value" density="compact" variant="outlined" hide-details style="max-width:160px" />
              <v-btn v-if="!editor.scriptMode" color="primary" size="x-small" :loading="editor.collecting" :disabled="!editor.deviceId || !editor.collectionContent.trim()" :title="!editor.deviceId ? 'Select a test device first' : ''" @click="runCollector">▶ Run Collector</v-btn>
            </template>
            <template v-else-if="editor.scriptTab === 'parser'">
              <v-btn v-if="!editor.scriptMode" color="primary" size="x-small" :loading="editor.parsing" :disabled="!editor.rawOutput || !editor.parserContent.trim()" :title="!editor.rawOutput ? 'Run the collector first' : ''" @click="runParser">▶ Run Parser</v-btn>
            </template>
            <template v-else>
              <v-select v-model="editor.deploymentLang" :items="langItems" item-title="title" item-value="value" density="compact" variant="outlined" hide-details style="max-width:160px" />
            </template>
          </div>
        </div>
        <div class="pkg-editor-single" :style="{ height: editorHeight + 'px', flex: 'none' }">
          <CodeEditor v-if="editor.scriptTab === 'collection'" v-model="editor.collectionContent" :language="editor.collectionLang" />
          <CodeEditor v-else-if="editor.scriptTab === 'parser'" v-model="editor.parserContent" language="python" />
          <CodeEditor v-else v-model="editor.deploymentContent" :language="editor.deploymentLang" />
        </div>

        <!-- Draggable splitter -->
        <div
          v-if="editor.rawOutput !== null || editor.collectError"
          class="pkg-splitter"
          @mousedown="startResize"
        >
          <div class="pkg-splitter-handle"></div>
        </div>

        <!-- Bottom: results panel -->
        <div v-if="editor.rawOutput !== null || editor.collectError" class="pkg-results">
          <div class="pkg-results-header">
            <span class="pkg-results-title">Results</span>
            <v-chip v-if="editor.parseResult" :color="editor.parseResult.success ? 'success' : 'error'" size="x-small" label>
              {{ editor.parseResult.success ? '✓ PASS' : '✗ FAIL' }}
            </v-chip>
            <v-btn style="margin-left:auto" variant="text" size="x-small" color="grey" @click="clearResults">✕ Clear</v-btn>
          </div>

          <!-- Errors -->
          <div v-if="editor.collectError" class="result-error-banner">
            <strong>Collection error:</strong> {{ editor.collectError }}
          </div>
          <div v-if="editor.parseResult?.error" class="result-error-banner">
            <strong>Parser error:</strong> {{ editor.parseResult.error }}
          </div>
          <div v-if="editor.parseResult?.validation_errors" class="result-error-banner">
            <strong>Schema validation errors:</strong>
            <pre style="margin-top:.35rem;background:transparent;color:inherit;padding:0;font-size:.82rem">{{ editor.parseResult.validation_errors }}</pre>
          </div>
          <div class="pkg-results-body">
            <template v-if="editor.rawOutput !== null || editor.collectError">
              <div class="result-pane">
                <div class="result-pane-label">
                  Raw Output
                  <span v-if="editor.rawOutput" class="result-pane-hint">(captured — edit parser and click Run Parser)</span>
                </div>
                <pre class="result-pre">{{ editor.rawOutput || '(empty)' }}</pre>
              </div>
              <div class="result-pane">
                <div class="result-pane-label">Parsed Output <span style="font-weight:400;color:#7a8a9a">(Canonical JSON)</span></div>
                <pre class="result-pre">{{ editor.parseResult?.parsed_output ? JSON.stringify(editor.parseResult.parsed_output, null, 2) : '(run parser)' }}</pre>
              </div>
            </template>
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import api from '../api'
import CodeEditor from '../components/CodeEditor.vue'

const activeTab  = ref('CollectionProfiles')
const showHelp   = ref(false)

const langItems = [
  { title: 'Shell / Bash', value: 'shell' },
  { title: 'PowerShell', value: 'powershell' },
  { title: 'Batch (.bat)', value: 'batch' },
  { title: 'VBScript', value: 'vbscript' },
  { title: 'Python', value: 'python' },
  { title: 'JavaScript', value: 'javascript' },
  { title: 'SQL', value: 'sql' },
]

// ── workspace splitter ────────────────────────────────────────────────────────
const workspaceEl = ref(null)
const editorHeight = ref(400)
let dragging = false
let dragStartY = 0
let dragStartH = 0

function startResize(e) {
  dragging = true
  dragStartY = e.clientY
  dragStartH = editorHeight.value
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', stopResize)
}

function onMouseMove(e) {
  if (!dragging) return
  const delta = e.clientY - dragStartY
  const workspace = workspaceEl.value
  const min = 120
  const max = workspace ? workspace.clientHeight - 80 : window.innerHeight - 80
  editorHeight.value = Math.min(max, Math.max(min, dragStartH + delta))
}

function stopResize() {
  dragging = false
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseup', stopResize)
}

onBeforeUnmount(() => {
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseup', stopResize)
})

// ── packages ─────────────────────────────────────────────────────────────────
const packages = ref([])
const pkgLoading = ref(false)
const testDevices = ref([])
const deviceSearchLoading = ref(false)
let deviceSearchTimer = null

function onDeviceSearch(q) {
  clearTimeout(deviceSearchTimer)
  // Preserve the currently selected device in the list while searching
  deviceSearchTimer = setTimeout(() => searchTestDevices(q), 300)
}

async function searchTestDevices(q) {
  deviceSearchLoading.value = true
  try {
    const { data } = await api.get('/devices/', { params: { search: q || '', is_active: true, page: 1 } })
    const results = data.results ?? data
    // Keep the currently selected device in the list so the label stays visible
    if (editor.value.deviceId) {
      const alreadyIn = results.some(d => d.id === editor.value.deviceId)
      if (!alreadyIn) {
        const existing = testDevices.value.find(d => d.id === editor.value.deviceId)
        if (existing) results.unshift(existing)
      }
    }
    testDevices.value = results
  } finally {
    deviceSearchLoading.value = false
  }
}

async function loadPackages() {
  pkgLoading.value = true
  try {
    const { data } = await api.get('/scripts/packages/')
    packages.value = data.results ?? data
  } finally {
    pkgLoading.value = false
  }
}

async function removePkg(id) {
  if (!confirm('Delete this collection profile? The underlying scripts will not be deleted.')) return
  await api.delete(`/scripts/packages/${id}/`)
  packages.value = packages.value.filter(p => p.id !== id)
}

// ── package editor ────────────────────────────────────────────────────────────
const editor = ref(blankEditor())

function blankEditor() {
  return {
    show: false, id: null, scriptMode: false, scriptTab: 'collection',
    name: '', description: '', target_os: 'any', version: '1.0.0', is_active: true,
    collectionScriptId: null, collectionContent: '', collectionLang: 'shell',
    parserScriptId: null,     parserContent: '',
    deploymentScriptId: null, deploymentContent: '', deploymentLang: 'shell',
    deviceId: null,
    saving: false, saveError: '',
    collecting: false, collectError: null,
    rawOutput: null,
    parsing: false, parseResult: null,
  }
}

function openNewPackage() {
  editor.value = { ...blankEditor(), show: true }
}

function openEditor(pkg) {
  editor.value = {
    ...blankEditor(),
    show: true,
    id: pkg.id,
    name: pkg.name,
    description: pkg.description ?? '',
    target_os: pkg.target_os,
    version: pkg.version,
    is_active: pkg.is_active,
    collectionScriptId: pkg.collection_script ?? null,
    collectionContent: pkg.collection_script_detail?.content ?? '',
    parserScriptId: pkg.parser_script ?? null,
    parserContent: pkg.parser_script_detail?.content ?? '',
  }
}

async function savePackage({ requireParser = true } = {}) {
  editor.value.saveError = ''
  if (!editor.value.name.trim()) { editor.value.saveError = 'Collection profile name is required.'; return }
  if (!editor.value.collectionContent.trim()) { editor.value.saveError = 'Collection script content is required.'; return }
  if (requireParser && !editor.value.parserContent.trim()) { editor.value.saveError = 'Parser script content is required.'; return }
  editor.value.saving = true
  try {
    const ids = await _ensureScripts()
    const payload = {
      name: editor.value.name,
      description: editor.value.description,
      target_os: editor.value.target_os,
      version: editor.value.version,
      is_active: editor.value.is_active,
      collection_script: ids.collection,
      parser_script: ids.parser,
    }
    if (editor.value.id) {
      const { data } = await api.patch(`/scripts/packages/${editor.value.id}/`, payload)
      const idx = packages.value.findIndex(p => p.id === editor.value.id)
      if (idx !== -1) packages.value[idx] = data
      editor.value.id = data.id
    } else {
      const { data } = await api.post('/scripts/packages/', payload)
      packages.value.push(data)
      editor.value.id = data.id
    }
  } catch (e) {
    editor.value.saveError = JSON.stringify(e.response?.data ?? 'Save failed.')
  } finally {
    editor.value.saving = false
  }
}

async function runCollector() {
  await savePackage({ requireParser: false })
  if (editor.value.saveError) return
  editor.value.collecting = true
  editor.value.collectError = null
  editor.value.rawOutput = null
  editor.value.parseResult = null
  try {
    const { data } = await api.post(`/scripts/packages/${editor.value.id}/collect/`, {
      device_id: editor.value.deviceId,
      collection_content: editor.value.collectionContent,
    })
    if (data.success) {
      editor.value.rawOutput = data.raw_output
    } else {
      editor.value.collectError = data.error
    }
  } catch (e) {
    editor.value.collectError = e.response?.data?.error ?? e.response?.data?.detail ?? 'Request failed.'
  } finally {
    editor.value.collecting = false
  }
}

async function runParser() {
  editor.value.parsing = true
  editor.value.parseResult = null
  try {
    const { data } = await api.post(`/scripts/packages/${editor.value.id}/parse/`, {
      raw_output: editor.value.rawOutput,
      parser_content: editor.value.parserContent,
    })
    editor.value.parseResult = data
  } catch (e) {
    editor.value.parseResult = {
      success: false, parsed_output: null, validation_errors: null,
      error: e.response?.data?.error ?? e.response?.data?.detail ?? 'Request failed.',
    }
  } finally {
    editor.value.parsing = false
  }
}

function clearResults() {
  editor.value.rawOutput = null
  editor.value.collectError = null
  editor.value.parseResult = null
}

async function _ensureScripts() {
  const col = await _upsertScript(editor.value.collectionScriptId, `${editor.value.name} — Collector`, 'collection', editor.value.collectionContent)
  editor.value.collectionScriptId = col

  let par = editor.value.parserScriptId
  if (editor.value.parserContent.trim()) {
    par = await _upsertScript(editor.value.parserScriptId, `${editor.value.name} — Parser`, 'parser', editor.value.parserContent)
    editor.value.parserScriptId = par
  }

  return { collection: col, parser: par }
}

async function _upsertScript(id, name, type, content) {
  const payload = { name, script_type: type, content, target_os: editor.value.target_os, version: editor.value.version, is_active: editor.value.is_active }
  if (id) {
    const { data } = await api.patch(`/scripts/${id}/`, payload)
    return data.id
  } else {
    try {
      const { data } = await api.post('/scripts/', payload)
      scripts.value.push(data)
      return data.id
    } catch (e) {
      if (e.response?.data?.name) {
        const { data } = await api.post('/scripts/', { ...payload, name: `${name} (${Date.now()})` })
        scripts.value.push(data)
        return data.id
      }
      throw e
    }
  }
}

// ── individual scripts ────────────────────────────────────────────────────────
const scripts = ref([])
const scrLoading = ref(false)

async function loadScripts() {
  scrLoading.value = true
  try {
    const { data } = await api.get('/scripts/')
    scripts.value = data.results ?? data
  } finally {
    scrLoading.value = false
  }
}

async function removeScript(id) {
  if (!confirm('Delete this script?')) return
  await api.delete(`/scripts/${id}/`)
  scripts.value = scripts.value.filter(s => s.id !== id)
}

function openNewScriptInEditor() {
  editor.value = { ...blankEditor(), show: true, scriptMode: true }
}

function openScriptInEditor(s) {
  const tab = s.script_type === 'parser' ? 'parser' : s.script_type === 'deployment' ? 'deployment' : 'collection'
  editor.value = {
    ...blankEditor(),
    show: true,
    scriptMode: true,
    scriptTab: tab,
    collectionScriptId: s.script_type === 'collection' ? s.id : null,
    parserScriptId:     s.script_type === 'parser'     ? s.id : null,
    deploymentScriptId: s.script_type === 'deployment' ? s.id : null,
    collectionContent:  s.script_type === 'collection' ? s.content : '',
    parserContent:      s.script_type === 'parser'     ? s.content : '',
    deploymentContent:  s.script_type === 'deployment' ? s.content : '',
    name:        s.name,
    description: s.description ?? '',
    version:     s.version,
    target_os:   s.target_os,
    is_active:   s.is_active,
  }
}

async function saveStandaloneScript() {
  editor.value.saveError = ''
  if (!editor.value.name.trim()) { editor.value.saveError = 'Name is required.'; return }
  editor.value.saving = true
  const tab = editor.value.scriptTab
  const contentMap = { collection: editor.value.collectionContent, parser: editor.value.parserContent, deployment: editor.value.deploymentContent }
  const idMap = { collection: editor.value.collectionScriptId, parser: editor.value.parserScriptId, deployment: editor.value.deploymentScriptId }
  const payload = {
    name: editor.value.name,
    description: editor.value.description,
    script_type: tab,
    target_os: editor.value.target_os,
    version: editor.value.version,
    is_active: editor.value.is_active,
    content: contentMap[tab],
  }
  try {
    const id = idMap[tab]
    if (id) {
      const { data } = await api.patch(`/scripts/${id}/`, payload)
      const idx = scripts.value.findIndex(s => s.id === id)
      if (idx !== -1) scripts.value[idx] = data
    } else {
      const { data } = await api.post('/scripts/', payload)
      scripts.value.push(data)
    }
    editor.value.show = false
  } catch (e) {
    editor.value.saveError = JSON.stringify(e.response?.data ?? 'Save failed.')
  } finally {
    editor.value.saving = false
  }
}

// ── init ─────────────────────────────────────────────────────────────────────
onMounted(async () => {
  editorHeight.value = Math.floor(window.innerHeight * 0.6)
  await Promise.all([loadPackages(), loadScripts()])
  // Pre-populate with first page so the picker isn't empty on first open
  searchTestDevices('')
})
</script>

<style scoped>
/* ── Package editor overlay ───────────────────────────────────────────────── */
.pkg-overlay {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  left: 220px;
  background: #f0f2f5;
  z-index: 300;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.pkg-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: .75rem 1.25rem;
  background: #16213e;
  color: #fff;
  flex-shrink: 0;
}
.pkg-topbar-left { display: flex; align-items: center; gap: 1rem; }
.pkg-topbar-right { display: flex; align-items: center; gap: .5rem; }
.pkg-title { font-size: 1rem; font-weight: 600; }

.pkg-meta {
  display: flex;
  gap: 1rem;
  align-items: flex-start;
  padding: .75rem 1.25rem;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  flex-shrink: 0;
  flex-wrap: wrap;
}

.pkg-workspace {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.pkg-splitter {
  flex-shrink: 0;
  height: 6px;
  cursor: ns-resize;
  background: #e0e0e0;
  display: flex;
  align-items: center;
  justify-content: center;
  user-select: none;
}
.pkg-splitter:hover, .pkg-splitter:active { background: #4fc3f7; }
.pkg-splitter-handle {
  width: 32px;
  height: 3px;
  border-radius: 2px;
  background: #a0aec0;
  pointer-events: none;
}
.pkg-splitter:hover .pkg-splitter-handle,
.pkg-splitter:active .pkg-splitter-handle { background: #fff; }

.pkg-editor-tabs {
  display: flex;
  align-items: center;
  background: #eef0f3;
  border-bottom: 1px solid #d0d5de;
  flex-shrink: 0;
}
.pkg-tab {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: .6rem 1.25rem;
  font-size: .82rem;
  font-weight: 600;
  color: #5a6280;
  border: none;
  background: transparent;
  cursor: pointer;
  border-bottom: 3px solid transparent;
  transition: color .15s, border-color .15s;
  white-space: nowrap;
}
.pkg-tab:hover { color: #1a1a2e; }
.pkg-tab--active { color: #4fc3f7; border-bottom-color: #4fc3f7; }
.pkg-tab-sub {
  font-size: .7rem;
  font-weight: 400;
  color: #7a8a9a;
  margin-top: .1rem;
  letter-spacing: .02em;
}
.pkg-tab--active .pkg-tab-sub { color: #a8d8ea; }
.pkg-tab-actions {
  display: flex;
  align-items: center;
  gap: .75rem;
  margin-left: auto;
  padding: 0 1rem;
}
.pkg-editor-single {
  flex: none;
  overflow: hidden;
}

.pkg-results {
  flex: 1;
  min-height: 0;
  background: #1a1a2e;
  color: #e2e8f0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
}
.pkg-results-header {
  display: flex;
  align-items: center;
  gap: .75rem;
  padding: .6rem 1.25rem;
  background: #16213e;
  flex-shrink: 0;
  position: sticky;
  top: 0;
}
.pkg-results-title { font-weight: 700; font-size: .9rem; }
.result-error-banner {
  margin: .75rem 1.25rem 0;
  padding: .65rem .85rem;
  background: rgba(248,215,218,.15);
  border: 1px solid rgba(252,129,129,.3);
  border-radius: 6px;
  color: #fc8181;
  font-size: .85rem;
}
.pkg-results-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1rem;
  padding: .75rem 1.25rem 1rem;
  flex: 1;
  min-height: 0;
}
.result-pane { display: flex; flex-direction: column; min-height: 0; }
.result-pane-hint {
  font-size: .72rem;
  font-weight: 400;
  color: #7a8a9a;
  margin-left: .4rem;
}
.result-pane-label {
  font-size: .78rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .05em;
  color: #4fc3f7;
  margin-bottom: .4rem;
}
.result-pre {
  flex: 1;
  min-height: 0;
  background: #13131f;
  color: #cdd6f4;
  border: 1px solid #313244;
  border-radius: 4px;
  padding: .65rem .75rem;
  font-size: .8rem;
  line-height: 1.5;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
