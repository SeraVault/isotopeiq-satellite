<template>
  <div>
    <!-- ── Tab bar ─────────────────────────────────────────────────────── -->
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

    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- PACKAGES TAB                                                       -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <template v-if="activeTab === 'Packages'">
      <button class="btn-primary" @click="openNewPackage" style="margin-bottom:1rem">+ New Package</button>

      <div v-if="pkgLoading">Loading…</div>
      <table v-else-if="packages.length">
        <thead>
          <tr><th>Name</th><th>Target OS</th><th>Version</th><th>Collection Script</th><th>Parser Script</th><th>Active</th><th>Actions</th></tr>
        </thead>
        <tbody>
          <tr v-for="p in packages" :key="p.id">
            <td>{{ p.name }}</td>
            <td>{{ p.target_os }}</td>
            <td>{{ p.version }}</td>
            <td>{{ p.collection_script_detail?.name ?? '—' }}</td>
            <td>{{ p.parser_script_detail?.name ?? '—' }}</td>
            <td>{{ p.is_active ? 'Yes' : 'No' }}</td>
            <td>
              <button @click="openEditor(p)">Edit / Test</button>
              <button class="btn-danger" @click="removePkg(p.id)">Delete</button>
            </td>
          </tr>
        </tbody>
      </table>
      <p v-else>No packages yet. Create one to pair a collection and parser script together.</p>
    </template>

    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- SCRIPTS TAB                                                        -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <template v-else>
      <button class="btn-primary" @click="openNewScript" style="margin-bottom:1rem">+ New Script</button>

      <div v-if="scrLoading">Loading…</div>
      <table v-else-if="scripts.length">
        <thead>
          <tr><th>Name</th><th>Type</th><th>Target OS</th><th>Version</th><th>Active</th><th>Actions</th></tr>
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
      <p v-else>No scripts yet.</p>

      <!-- Individual script modal -->
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
            <label style="margin-top:.75rem">Version <input v-model="scriptForm.version" style="width:140px" /></label>
            <label style="margin-top:.75rem">Description <textarea v-model="scriptForm.description" rows="2"></textarea></label>
            <label style="margin-top:.75rem">
              Content
              <textarea
                v-model="scriptForm.content"
                rows="22"
                style="font-family:monospace;font-size:.85rem;width:100%;resize:vertical"
                required
                spellcheck="false"
              ></textarea>
            </label>
            <label style="margin-top:.5rem"><input v-model="scriptForm.is_active" type="checkbox" /> Active</label>
            <p v-if="scriptForm.error" class="error" style="margin-top:.5rem">{{ scriptForm.error }}</p>
            <div style="margin-top:1rem">
              <button class="btn-primary" type="submit">Save</button>
              <button type="button" @click="scriptForm.show = false">Cancel</button>
            </div>
          </form>
        </div>
      </div>
    </template>

    <!-- ══════════════════════════════════════════════════════════════════ -->
    <!-- PACKAGE EDITOR MODAL                                               -->
    <!-- ══════════════════════════════════════════════════════════════════ -->
    <div v-if="editor.show" class="modal" style="align-items:flex-start;padding:1rem">
      <div class="modal-box modal-xl">

        <!-- Header row -->
        <div style="display:flex;align-items:center;gap:1rem;margin-bottom:1rem">
          <h2 style="margin:0">{{ editor.id ? 'Edit Package' : 'New Package' }}</h2>
          <div style="display:flex;gap:.5rem;margin-left:auto">
            <button class="btn-primary" @click="savePackage" :disabled="editor.saving">
              {{ editor.saving ? 'Saving…' : 'Save' }}
            </button>
            <button class="btn-primary" @click="saveAndTest" :disabled="editor.testing || !editor.deviceId">
              {{ editor.testing ? 'Testing…' : 'Save & Test' }}
            </button>
            <button @click="editor.show = false">Close</button>
          </div>
        </div>

        <!-- Package metadata -->
        <div style="display:grid;grid-template-columns:2fr 1fr 1fr 1fr auto;gap:.75rem;margin-bottom:1rem;align-items:end">
          <label style="margin:0">Name <input v-model="editor.name" required /></label>
          <label style="margin:0">Target OS
            <select v-model="editor.target_os">
              <option value="linux">Linux</option>
              <option value="windows">Windows</option>
              <option value="macos">macOS</option>
              <option value="any">Any</option>
            </select>
          </label>
          <label style="margin:0">Version <input v-model="editor.version" /></label>
          <label style="margin:0">Test Device
            <select v-model="editor.deviceId">
              <option :value="null">— pick a device —</option>
              <option v-for="d in testDevices" :key="d.id" :value="d.id">
                {{ d.name }} ({{ d.hostname }})
              </option>
            </select>
          </label>
          <label style="margin:0;white-space:nowrap"><input v-model="editor.is_active" type="checkbox" /> Active</label>
        </div>
        <label style="display:block;margin-bottom:1rem">
          Description
          <input v-model="editor.description" />
        </label>

        <!-- Side-by-side editors -->
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
          <!-- Collection script -->
          <div>
            <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.4rem">
              <strong>Collection Script</strong>
              <input v-model="editor.collectionName" placeholder="Script name" style="flex:1;margin:0" />
            </div>
            <textarea
              v-model="editor.collectionContent"
              rows="28"
              style="width:100%;font-family:monospace;font-size:.82rem;resize:vertical;border:1px solid #ccc;border-radius:4px;padding:.5rem"
              placeholder="#!/usr/bin/env bash&#10;# Collect raw data from the device&#10;..."
              spellcheck="false"
            ></textarea>
          </div>

          <!-- Parser script -->
          <div>
            <div style="display:flex;align-items:center;gap:.5rem;margin-bottom:.4rem">
              <strong>Parser Script</strong>
              <input v-model="editor.parserName" placeholder="Script name" style="flex:1;margin:0" />
            </div>
            <textarea
              v-model="editor.parserContent"
              rows="28"
              style="width:100%;font-family:monospace;font-size:.82rem;resize:vertical;border:1px solid #ccc;border-radius:4px;padding:.5rem"
              placeholder="#!/usr/bin/env python3&#10;import sys, json&#10;# Read stdin, write canonical JSON to stdout&#10;..."
              spellcheck="false"
            ></textarea>
          </div>
        </div>

        <!-- Error / save feedback -->
        <p v-if="editor.saveError" class="error" style="margin-top:.5rem">{{ editor.saveError }}</p>

        <!-- Test results panel -->
        <div v-if="editor.testDone" style="margin-top:1.25rem;border-top:2px solid #eee;padding-top:1rem">
          <div style="display:flex;align-items:center;gap:.75rem;margin-bottom:.75rem">
            <h3 style="margin:0">Test Results</h3>
            <span :style="`display:inline-block;padding:.2rem .6rem;border-radius:999px;font-size:.85rem;font-weight:600;background:${editor.testResult.success ? '#d4edda' : '#f8d7da'};color:${editor.testResult.success ? '#155724' : '#721c24'}`">
              {{ editor.testResult.success ? 'PASS' : 'FAIL' }}
            </span>
          </div>

          <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem">
            <div>
              <p style="font-weight:600;margin-bottom:.35rem">Raw Output</p>
              <pre style="max-height:320px;overflow:auto">{{ editor.testResult.raw_output ?? '(none)' }}</pre>
            </div>
            <div>
              <p style="font-weight:600;margin-bottom:.35rem">Parsed Output (Canonical JSON)</p>
              <pre style="max-height:320px;overflow:auto">{{ editor.testResult.parsed_output ? JSON.stringify(editor.testResult.parsed_output, null, 2) : '(none)' }}</pre>
            </div>
          </div>

          <div v-if="editor.testResult.validation_errors" style="margin-top:.75rem;padding:.75rem;background:#f8d7da;border-radius:4px;color:#721c24">
            <strong>Schema validation errors:</strong>
            <pre style="margin-top:.35rem;background:transparent;color:inherit;padding:0">{{ editor.testResult.validation_errors }}</pre>
          </div>

          <div v-if="editor.testResult.error" style="margin-top:.75rem;padding:.75rem;background:#f8d7da;border-radius:4px;color:#721c24">
            <strong>Error:</strong> {{ editor.testResult.error }}
          </div>
        </div>

      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const activeTab = ref('Packages')

// ── packages ────────────────────────────────────────────────────────────────
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

// ── package editor ───────────────────────────────────────────────────────────
const editor = ref(blankEditor())

function blankEditor() {
  return {
    show: false, id: null,
    name: '', description: '', target_os: 'any', version: '1.0.0', is_active: true,
    collectionScriptId: null, collectionName: '', collectionContent: '',
    parserScriptId: null, parserName: '', parserContent: '',
    deviceId: null,
    saving: false, saveError: '',
    testing: false, testDone: false, testResult: null,
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
    description: pkg.description,
    target_os: pkg.target_os,
    version: pkg.version,
    is_active: pkg.is_active,
    collectionScriptId: pkg.collection_script ?? null,
    collectionName: pkg.collection_script_detail?.name ?? '',
    collectionContent: pkg.collection_script_detail?.content ?? '',
    parserScriptId: pkg.parser_script ?? null,
    parserName: pkg.parser_script_detail?.name ?? '',
    parserContent: pkg.parser_script_detail?.content ?? '',
  }
}

async function savePackage() {
  editor.value.saveError = ''
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

async function saveAndTest() {
  await savePackage()
  if (editor.value.saveError) return
  editor.value.testing = true
  editor.value.testDone = false
  try {
    const { data } = await api.post(
      `/scripts/packages/${editor.value.id}/test/`,
      { device_id: editor.value.deviceId },
    )
    editor.value.testResult = data
    editor.value.testDone = true
  } catch (e) {
    editor.value.testResult = {
      success: false,
      raw_output: null,
      parsed_output: null,
      validation_errors: null,
      error: e.response?.data?.error ?? 'Request failed.',
    }
    editor.value.testDone = true
  } finally {
    editor.value.testing = false
  }
}

// Create or update the underlying Script records, return their IDs.
async function _ensureScripts() {
  const col = await _upsertScript(
    editor.value.collectionScriptId,
    editor.value.collectionName || `${editor.value.name} — Collector`,
    'collection',
    editor.value.collectionContent,
    editor.value.target_os,
  )
  const par = await _upsertScript(
    editor.value.parserScriptId,
    editor.value.parserName || `${editor.value.name} — Parser`,
    'parser',
    editor.value.parserContent,
    editor.value.target_os,
  )
  editor.value.collectionScriptId = col
  editor.value.parserScriptId = par
  return { collection: col, parser: par }
}

async function _upsertScript(id, name, type, content, targetOs) {
  const payload = { name, script_type: type, content, target_os: targetOs, version: editor.value.version, is_active: editor.value.is_active }
  if (id) {
    const { data } = await api.patch(`/scripts/${id}/`, payload)
    const idx = scripts.value.findIndex(s => s.id === id)
    if (idx !== -1) scripts.value[idx] = data
    return data.id
  } else {
    const { data } = await api.post('/scripts/', payload)
    scripts.value.push(data)
    return data.id
  }
}

// ── individual scripts ───────────────────────────────────────────────────────
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

// ── init ────────────────────────────────────────────────────────────────────
onMounted(async () => {
  const [, , devRes] = await Promise.all([
    loadPackages(),
    loadScripts(),
    api.get('/devices/?connection_type__in=ssh,telnet&is_active=true'),
  ])
  testDevices.value = devRes.data.results ?? devRes.data
})
</script>
