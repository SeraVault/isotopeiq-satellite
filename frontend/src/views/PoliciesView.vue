<template>
  <div>
    <h1>Policies</h1>
    <button class="btn-primary" @click="openNew" style="margin-bottom:1rem">+ New Policy</button>

    <div v-if="loading">Loading…</div>
    <table v-else-if="policies.length">
      <thead>
        <tr><th>Name</th><th>Schedule</th><th>Devices</th><th>Active</th><th>Actions</th></tr>
      </thead>
      <tbody>
        <tr v-for="p in policies" :key="p.id">
          <td>{{ p.name }}</td>
          <td><code>{{ p.cron_schedule }}</code></td>
          <td>{{ p.devices?.length ?? 0 }}</td>
          <td>{{ p.is_active ? 'Yes' : 'No' }}</td>
          <td>
            <button @click="runNow(p.id)" :disabled="running === p.id">
              {{ running === p.id ? 'Queued…' : 'Run Now' }}
            </button>
            <button @click="deployNow(p)" :disabled="!p.deployment_script || deploying === p.id">Deploy</button>
            <button @click="openEdit(p)">Edit</button>
            <button class="btn-danger" @click="remove(p.id)">Delete</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else>No policies yet.</p>

    <!-- Policy form modal -->
    <div v-if="showForm" class="modal">
      <div class="modal-box modal-md">
        <h2>{{ form.id ? 'Edit' : 'New' }} Policy</h2>
        <form @submit.prevent="save">
          <label>Name <input v-model="form.name" required /></label>
          <label>Description <textarea v-model="form.description" rows="2"></textarea></label>
          <label>
            Cron Schedule
            <input v-model="form.cron_schedule" placeholder="0 2 * * *" />
            <small>minute hour dom month dow (UTC)</small>
          </label>
          <label>
            Delay Between Devices (seconds)
            <input v-model.number="form.delay_between_devices" type="number" min="0" />
          </label>

          <label>
            Collection Script
            <select v-model="form.collection_script">
              <option :value="null">— none —</option>
              <option v-for="s in collectionScripts" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </label>
          <label>
            Parser Script
            <select v-model="form.parser_script">
              <option :value="null">— none —</option>
              <option v-for="s in parserScripts" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </label>
          <label>
            Deployment Script
            <select v-model="form.deployment_script">
              <option :value="null">— none —</option>
              <option v-for="s in deploymentScripts" :key="s.id" :value="s.id">{{ s.name }}</option>
            </select>
          </label>

          <fieldset style="margin-top:.75rem;padding:.75rem;border:1px solid #ccc;border-radius:4px">
            <legend style="padding:0 .4rem">Devices</legend>
            <div v-for="d in allDevices" :key="d.id" style="margin-bottom:.3rem">
              <label style="display:flex;align-items:center;gap:.5rem;margin:0">
                <input type="checkbox" :value="d.id" v-model="form.devices" />
                {{ d.name }} ({{ d.hostname }})
              </label>
            </div>
            <p v-if="!allDevices.length" style="color:#888;font-size:.85rem">No devices defined.</p>
          </fieldset>

          <label style="margin-top:.75rem"><input v-model="form.is_active" type="checkbox" /> Active</label>
          <div style="margin-top:1rem">
            <button class="btn-primary" type="submit">Save</button>
            <button type="button" @click="cancel">Cancel</button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const policies = ref([])
const allDevices = ref([])
const collectionScripts = ref([])
const parserScripts = ref([])
const deploymentScripts = ref([])
const loading = ref(false)
const showForm = ref(false)
const running = ref(null)
const deploying = ref(null)
const form = ref(blank())

function blank() {
  return {
    name: '', description: '', cron_schedule: '0 2 * * *',
    delay_between_devices: 0,
    devices: [], collection_script: null, parser_script: null, deployment_script: null,
    is_active: true,
  }
}

onMounted(async () => {
  loading.value = true
  try {
    const [polRes, devRes, scrRes] = await Promise.all([
      api.get('/policies/'),
      api.get('/devices/'),
      api.get('/scripts/'),
    ])
    policies.value = polRes.data.results ?? polRes.data
    allDevices.value = devRes.data.results ?? devRes.data
    const scripts = scrRes.data.results ?? scrRes.data
    collectionScripts.value = scripts.filter(s => s.script_type === 'collection' && s.is_active)
    parserScripts.value = scripts.filter(s => s.script_type === 'parser' && s.is_active)
    deploymentScripts.value = scripts.filter(s => s.script_type === 'deployment' && s.is_active)
  } finally {
    loading.value = false
  }
})

function openNew() { form.value = blank(); showForm.value = true }
function openEdit(p) {
  form.value = {
    ...p,
    devices: p.devices?.map(d => (typeof d === 'object' ? d.id : d)) ?? [],
    collection_script: p.collection_script?.id ?? p.collection_script ?? null,
    parser_script: p.parser_script?.id ?? p.parser_script ?? null,
    deployment_script: p.deployment_script?.id ?? p.deployment_script ?? null,
  }
  showForm.value = true
}
function cancel() { showForm.value = false }

async function save() {
  const payload = { ...form.value }
  if (form.value.id) {
    const { data } = await api.patch(`/policies/${form.value.id}/`, payload)
    const idx = policies.value.findIndex(p => p.id === form.value.id)
    policies.value[idx] = data
  } else {
    const { data } = await api.post('/policies/', payload)
    policies.value.push(data)
  }
  cancel()
}

async function remove(id) {
  if (!confirm('Delete this policy?')) return
  await api.delete(`/policies/${id}/`)
  policies.value = policies.value.filter(p => p.id !== id)
}

async function runNow(id) {
  running.value = id
  try {
    await api.post(`/policies/${id}/run/`)
  } finally {
    setTimeout(() => { running.value = null }, 2000)
  }
}

async function deployNow(p) {
  if (!confirm(`Run deployment script on all devices in "${p.name}"?`)) return
  deploying.value = p.id
  try {
    await api.post(`/policies/${p.id}/deploy/`)
  } finally {
    setTimeout(() => { deploying.value = null }, 2000)
  }
}
</script>
