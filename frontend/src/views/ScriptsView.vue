<template>
  <div>
    <h1>Scripts</h1>
    <div class="tabs">
      <div
        v-for="tab in ['Packages', 'Scripts']"
        :key="tab"
        class="tab"
        :class="{ active: activeTab === tab }"
        @click="activeTab = tab"
      >{{ tab }}</div>
    </div>

    <!-- ── PACKAGES TAB ───────────────────────────────────────────────────── -->
    <template v-if="activeTab === 'Packages'">
      <button class="btn-primary" @click="openNewPackage" style="margin-bottom:1rem">+ New Package</button>
      <div v-if="pkgLoading" class="text-muted">Loading…</div>
      <table v-else-if="packages.length">
        <thead>
          <tr><th>Name</th><th>Target OS</th><th>Version</th><th>Collection Script</th><th>Parser Script</th><th>Active</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="p in packages" :key="p.id">
            <td>{{ p.name }}</td>
            <td>{{ p.target_os }}</td>
            <td>{{ p.version }}</td>
            <td class="text-muted">{{ p.collection_script_detail?.name ?? '—' }}</td>
            <td class="text-muted">{{ p.parser_script_detail?.name ?? '—' }}</td>
            <td>{{ p.is_active ? 'Yes' : 'No' }}</td>
            <td>
              <button @click="openEditor(p)">Edit / Test</button>
              <button class="btn-danger" @click="removePkg(p.id)">Delete</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="text-muted">No packages yet.</p>
    </template>

    <!-- ── SCRIPTS TAB ────────────────────────────────────────────────────── -->
    <template v-else>
      <button class="btn-primary" @click="openNewScript" style="margin-bottom:1rem">+ New Script</button>
      <div v-if="scrLoading" class="text-muted">Loading…</div>
      <table v-else-if="scripts.length">
        <thead>
          <tr><th>Name</th><th>Type</th><th>Target OS</th><th>Version</th><th>Active</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="s in scripts" :key="s.id">
            <td>{{ s.name }}</td>
            <td>{{ s.script_type }}</td>
            <td>{{ s.target_os }}</td>
            <td>{{ s.version }}</td>
            <td>{{ s.is_active ? 'Yes' : 'No' }}</td>
            <td>
              <button @click="openEditScript(s)">Edit</button>
              <button class="btn-danger" @click="removeScript(s.id)">Delete</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else class="text-muted">No scripts yet.</p>

      <!-- Script modal -->
      <div v-if="scriptForm.show" class="modal">
        <div class="modal-box modal-lg">
          <h2>{{ scriptForm.id ? 'Edit' : 'New' }} Script</h2>
          <form @submit.prevent="saveScript">
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:.75rem">
              <label>Name <input v-model="scriptForm.name" required /></label>
              <label>Type
                <select v-model="scriptForm.script_type">
                  <option value="collection">Collection</option>
                  <option value="parser">Parser</option>
                  <option value="deployment">Deployment</option>
                </select>
              </label>
              <label>Target OS
                <select v-model="scriptForm.target_os">
                  <option value="linux">Linux</option>
                  <option value="windows">Windows</option>
                  <option value="macos">macOS</option>
                  <option value="any">Any</option>
                </select>
              </label>
            </div>
            <div style="display:grid;grid-template-columns:140px 1fr;gap:.75rem;margin-top:.75rem">
              <label>Version <input v-model="scriptForm.version" /></label>
              <label>Description <input v-model="scriptForm.description" /></label>
            </div>
            <label style="margin-top:.75rem;display:flex;flex-direction:column;flex:1;min-height:0">
              Content
              <div style="flex:1;min-height:400px;margin-top:.25rem">
                <CodeEditor v-model="scriptForm.content" :language="scriptForm.script_type === 'parser' ? 'python' : 'shell'" />
              </div>
            </label>
            <div style="display:flex;align-items:center;gap:1rem;margin-top:.75rem">
              <label style="margin:0"><input v-model="scriptForm.is_active" type="checkbox" /> Active</label>
              <span v-if="scriptForm.error" class="error">{{ scriptForm.error }}</span>
              <div style="margin-left:auto">
                <button class="btn-primary" type="submit">Save</button>
                <button type="button" @click="scriptForm.show = false">Cancel</button>
              </div>
            </div>
          </form>
        </div>
      </div>
    </template>

    <!-- ── PACKAGE EDITOR (full-screen overlay) ───────────────────────────── -->
    <div v-if="editor.show" class="pkg-overlay">

      <!-- Top bar -->
      <div class="pkg-topbar">
        <div class="pkg-topbar-left">
          <span class="pkg-title">{{ editor.id ? 'Edit Package' : 'New Package' }}</span>
          <span v-if="editor.saveError" class="error" style="font-size:.85rem">{{ editor.saveError }}</span>
        </div>
        <div class="pkg-topbar-right">
          <button @click="editor.show = false">✕ Close</button>
          <button class="btn-primary" @click="savePackage" :disabled="editor.saving">
            {{ editor.saving ? 'Saving…' : 'Save' }}
          </button>
        </div>
      </div>

      <!-- Metadata row -->
      <div class="pkg-meta">
        <label>
          Package Name
          <input v-model="editor.name" placeholder="e.g. Linux Baseline" required />
        </label>
        <label>
          Target OS
          <select v-model="editor.target_os">
            <option value="linux">Linux</option>
            <option value="windows">Windows</option>
            <option value="macos">macOS</option>
            <option value="any">Any</option>
          </select>
        </label>
        <label>
          Version
          <input v-model="editor.version" style="width:100px" />
        </label>
        <label>
          Test Device
          <select v-model="editor.deviceId">
            <option :value="null">— select device —</option>
            <option v-for="d in testDevices" :key="d.id" :value="d.id">
              {{ d.name }} ({{ d.hostname }})
            </option>
          </select>
        </label>
        <label>
          Description
          <input v-model="editor.description" placeholder="optional" />
        </label>
        <label style="align-self:flex-end;padding-bottom:.3rem">
          <input v-model="editor.is_active" type="checkbox" /> Active
        </label>
      </div>

      <!-- Editor + results area (fills remaining space) -->
      <div class="pkg-workspace" ref="workspaceEl">

        <!-- Top: side-by-side editors -->
        <div class="pkg-editors" :style="{ height: editorHeight + 'px', flex: 'none' }">

          <!-- Collection script pane -->
          <div class="pkg-editor-pane">
            <div class="pkg-editor-header">
              <div>
                <span class="pkg-editor-label">Collection Script</span>
                <span class="pkg-editor-context">runs on the target device</span>
              </div>
              <select v-model="editor.collectionLang" class="lang-select">
                <option value="shell">Shell / Bash</option>
                <option value="powershell">PowerShell</option>
                <option value="batch">Batch (.bat / .com)</option>
                <option value="vbscript">VBScript</option>
                <option value="python">Python</option>
                <option value="javascript">JavaScript</option>
                <option value="sql">SQL</option>
              </select>
              <button
                class="btn-primary pane-run-btn"
                @click="runCollector"
                :disabled="editor.collecting || !editor.deviceId || !editor.collectionContent.trim()"
                :title="!editor.deviceId ? 'Select a test device first' : ''"
              >{{ editor.collecting ? 'Running…' : '▶ Run Collector' }}</button>
            </div>
            <CodeEditor v-model="editor.collectionContent" :language="editor.collectionLang" />
          </div>

          <!-- Parser script pane -->
          <div class="pkg-editor-pane">
            <div class="pkg-editor-header">
              <div>
                <span class="pkg-editor-label">Parser Script</span>
                <span class="pkg-editor-context">runs on the server — <code style="font-size:.75rem">result</code> = collector output, populate <code style="font-size:.75rem">output</code></span>
              </div>
              <button
                class="btn-primary pane-run-btn"
                @click="runParser"
                :disabled="editor.parsing || !editor.rawOutput || !editor.parserContent.trim()"
                :title="!editor.rawOutput ? 'Run the collector first to capture raw output' : ''"
              >{{ editor.parsing ? 'Parsing…' : '▶ Run Parser' }}</button>
            </div>
            <CodeEditor v-model="editor.parserContent" language="python" />
          </div>
        </div>

        <!-- Draggable splitter -->
        <div
          v-if="editor.rawOutput !== null || editor.collectError"
          class="pkg-splitter"
          @mousedown="startResize"
        >
          <div class="pkg-splitter-handle"></div>
        </div>

        <!-- Bottom: results panel (always visible once collector has run) -->
        <div v-if="editor.rawOutput !== null || editor.collectError" class="pkg-results">
          <div class="pkg-results-header">
            <span class="pkg-results-title">Results</span>
            <span v-if="editor.parseResult" :class="['result-badge', editor.parseResult.success ? 'result-pass' : 'result-fail']">
              {{ editor.parseResult.success ? '✓ PASS' : '✗ FAIL' }}
            </span>
            <button style="margin-left:auto;color:#a0aec0" @click="clearResults">✕ Clear</button>
          </div>

          <!-- Collection or parse errors -->
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
            <div class="result-pane">
              <div class="result-pane-label">
                Raw Output
                <span v-if="editor.rawOutput" class="result-pane-hint">(captured — edit parser and click Run Parser)</span>
              </div>
              <pre class="result-pre">{{ editor.rawOutput || '(empty)' }}</pre>
            </div>
            <div class="result-pane">
              <div class="result-pane-label">Parsed Output <span class="text-muted" style="font-weight:400">(Canonical JSON)</span></div>
              <pre class="result-pre">{{ editor.parseResult?.parsed_output ? JSON.stringify(editor.parseResult.parsed_output, null, 2) : '(run parser)' }}</pre>
            </div>
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

const activeTab = ref('Packages')

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
  if (!confirm('Delete this package? The underlying scripts will not be deleted.')) return
  await api.delete(`/scripts/packages/${id}/`)
  packages.value = packages.value.filter(p => p.id !== id)
}

// ── package editor ────────────────────────────────────────────────────────────
const editor = ref(blankEditor())

function blankEditor() {
  return {
    show: false, id: null,
    name: '', description: '', target_os: 'any', version: '1.0.0', is_active: true,
    collectionScriptId: null, collectionContent: '', collectionLang: 'shell',
    parserScriptId: null,     parserContent: '',
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
  if (!editor.value.name.trim()) {
    editor.value.saveError = 'Package name is required.'
    return
  }
  if (!editor.value.collectionContent.trim()) {
    editor.value.saveError = 'Collection script content is required.'
    return
  }
  if (requireParser && !editor.value.parserContent.trim()) {
    editor.value.saveError = 'Parser script content is required.'
    return
  }
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
      success: false,
      parsed_output: null,
      validation_errors: null,
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
  const col = await _upsertScript(
    editor.value.collectionScriptId,
    `${editor.value.name} — Collector`,
    'collection',
    editor.value.collectionContent,
  )
  editor.value.collectionScriptId = col

  let par = editor.value.parserScriptId
  if (editor.value.parserContent.trim()) {
    par = await _upsertScript(
      editor.value.parserScriptId,
      `${editor.value.name} — Parser`,
      'parser',
      editor.value.parserContent,
    )
    editor.value.parserScriptId = par
  }

  return { collection: col, parser: par }
}

async function _upsertScript(id, name, type, content) {
  const payload = {
    name,
    script_type: type,
    content,
    target_os: editor.value.target_os,
    version: editor.value.version,
    is_active: editor.value.is_active,
  }
  if (id) {
    const { data } = await api.patch(`/scripts/${id}/`, payload)
    return data.id
  } else {
    // If name conflicts, append a timestamp to make it unique
    try {
      const { data } = await api.post('/scripts/', payload)
      scripts.value.push(data)
      return data.id
    } catch (e) {
      if (e.response?.data?.name) {
        const { data } = await api.post('/scripts/', {
          ...payload,
          name: `${name} (${Date.now()})`,
        })
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
const scriptForm = ref(blankScript())

function blankScript() {
  return { show: false, id: null, name: '', description: '', script_type: 'collection', target_os: 'any', version: '1.0.0', content: '', is_active: true, error: '' }
}

async function loadScripts() {
  scrLoading.value = true
  try {
    const { data } = await api.get('/scripts/')
    scripts.value = data.results ?? data
  } finally {
    scrLoading.value = false
  }
}

function openNewScript() { scriptForm.value = { ...blankScript(), show: true } }
function openEditScript(s) { scriptForm.value = { ...blankScript(), ...s, show: true, error: '' } }

async function saveScript() {
  scriptForm.value.error = ''
  const { id, show, error, ...payload } = scriptForm.value
  try {
    if (id) {
      const { data } = await api.patch(`/scripts/${id}/`, payload)
      const idx = scripts.value.findIndex(s => s.id === id)
      if (idx !== -1) scripts.value[idx] = data
    } else {
      const { data } = await api.post('/scripts/', payload)
      scripts.value.push(data)
    }
    scriptForm.value.show = false
  } catch (e) {
    scriptForm.value.error = JSON.stringify(e.response?.data ?? 'Save failed.')
  }
}

async function removeScript(id) {
  if (!confirm('Delete this script?')) return
  await api.delete(`/scripts/${id}/`)
  scripts.value = scripts.value.filter(s => s.id !== id)
}

// ── init ─────────────────────────────────────────────────────────────────────
onMounted(async () => {
  // Set initial editor height to ~60% of viewport
  editorHeight.value = Math.floor(window.innerHeight * 0.6)

  const [, , devRes] = await Promise.all([
    loadPackages(),
    loadScripts(),
    api.get('/devices/', { params: { is_active: true } }),
  ])
  testDevices.value = devRes.data.results ?? devRes.data
})
</script>

<style scoped>
/* ── Language selector ────────────────────────────────────────────────────── */
.lang-select {
  margin-left: auto;
  padding: .2rem .45rem;
  font-size: .78rem;
  border: 1px solid #313244;
  border-radius: 4px;
  background: #1e1e2e;
  color: #cdd6f4;
  cursor: pointer;
}

/* ── Package editor overlay ───────────────────────────────────────────────── */
.pkg-overlay {
  position: fixed;
  inset: 0;
  background: #f0f2f5;
  z-index: 300;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

/* Top bar */
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

/* Metadata row */
.pkg-meta {
  display: flex;
  gap: 1rem;
  align-items: flex-end;
  padding: .75rem 1.25rem;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  flex-shrink: 0;
  flex-wrap: wrap;
}
.pkg-meta label {
  display: flex;
  flex-direction: column;
  font-size: .82rem;
  font-weight: 600;
  color: #555;
  gap: .25rem;
  margin: 0;
}
.pkg-meta input, .pkg-meta select {
  margin: 0;
  padding: .35rem .55rem;
  border: 1px solid #d0d0d0;
  border-radius: 4px;
  font-size: .88rem;
  min-width: 120px;
}
.pkg-meta label:nth-child(1) input { min-width: 220px; }
.pkg-meta label:nth-child(5) input { min-width: 260px; }

/* Workspace: editors on top, results on bottom */
.pkg-workspace {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

/* Draggable splitter */
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

/* Side-by-side editors */
.pkg-editors {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0;
  flex: 1;
  overflow: hidden;
  min-height: 0;
}
.pkg-editor-pane {
  display: flex;
  flex-direction: column;
  padding: .75rem 1rem;
  border-right: 1px solid #e0e0e0;
  min-height: 0;
  overflow: hidden;
}
.pkg-editor-pane:last-child { border-right: none; }
.pkg-editor-header {
  display: flex;
  align-items: center;
  gap: .75rem;
  margin-bottom: .5rem;
  flex-shrink: 0;
}
.pkg-editor-label {
  font-size: .8rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .06em;
  color: #4fc3f7;
  white-space: nowrap;
}
.pkg-editor-context {
  display: block;
  font-size: .75rem;
  font-weight: 400;
  color: #7a8a9a;
  text-transform: none;
  letter-spacing: 0;
  margin-top: .1rem;
}
/* Test results panel */
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
.pkg-results-title {
  font-weight: 700;
  font-size: .9rem;
}
.result-badge {
  padding: .2rem .6rem;
  border-radius: 999px;
  font-size: .8rem;
  font-weight: 700;
}
.result-pass { background: #d4edda; color: #155724; }
.result-fail { background: #f8d7da; color: #721c24; }
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
.result-pane {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.pane-run-btn {
  font-size: .78rem;
  padding: .22rem .6rem;
}
.result-pane-hint {
  font-size: .72rem;
  font-weight: 400;
  color: #7a8a9a;
  text-transform: none;
  letter-spacing: 0;
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
