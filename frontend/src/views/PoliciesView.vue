<template>
  <div>
    <div class="d-flex justify-space-between align-center mb-5">
      <div class="text-h5 font-weight-bold">Policies</div>
      <v-btn color="primary" prepend-icon="mdi-plus" @click="openNew">New Policy</v-btn>
    </div>

    <div v-if="loading" class="text-medium-emphasis pa-4">Loading…</div>
    <v-card v-else-if="policies.length" rounded="lg" elevation="1">
      <v-table density="compact">
        <thead>
          <tr><th>Name</th><th>Schedule</th><th>Devices</th><th>Active</th><th>Actions</th></tr>
        </thead>
        <tbody>
          <tr v-for="p in policies" :key="p.id">
            <td class="font-weight-medium">{{ p.name }}</td>
            <td><code>{{ p.cron_schedule }}</code></td>
            <td>{{ p.devices?.length ?? 0 }}</td>
            <td>
              <v-chip :color="p.is_active ? 'success' : 'default'" size="x-small" label>
                {{ p.is_active ? 'Yes' : 'No' }}
              </v-chip>
            </td>
            <td>
              <v-btn size="x-small" variant="tonal" class="mr-1" :loading="running === p.id" @click="runNow(p.id)">Run Now</v-btn>
              <v-btn size="x-small" variant="tonal" class="mr-1" :disabled="!p.deployment_script" :loading="deploying === p.id" @click="deployNow(p)">Deploy</v-btn>
              <v-btn size="x-small" variant="tonal" class="mr-1" @click="openEdit(p)">Edit</v-btn>
              <v-btn size="x-small" color="error" variant="tonal" @click="remove(p.id)">Delete</v-btn>
            </td>
          </tr>
        </tbody>
      </v-table>
    </v-card>
    <div v-else class="pa-6 text-center text-medium-emphasis">No policies yet.</div>

    <!-- Policy form dialog -->
    <v-dialog v-model="showForm" max-width="600" scrollable>
      <v-card rounded="lg">
        <v-card-title>{{ form.id ? 'Edit' : 'New' }} Policy</v-card-title>
        <v-card-text>
          <v-row dense>
            <v-col cols="12">
              <v-text-field v-model="form.name" label="Name" required />
            </v-col>
            <v-col cols="12">
              <v-textarea v-model="form.description" label="Description" rows="2" />
            </v-col>
            <v-col cols="12" sm="8">
              <v-text-field v-model="form.cron_schedule" label="Cron Schedule" placeholder="0 2 * * *" hint="minute hour dom month dow (UTC)" persistent-hint />
            </v-col>
            <v-col cols="12" sm="4">
              <v-text-field v-model.number="form.delay_between_devices" label="Delay Between Devices (s)" type="number" min="0" />
            </v-col>
            <v-col cols="12" sm="4">
              <v-select v-model="form.collection_script" label="Collection Script" :items="collectionScripts" item-title="name" item-value="id" clearable />
            </v-col>
            <v-col cols="12" sm="4">
              <v-select v-model="form.parser_script" label="Parser Script" :items="parserScripts" item-title="name" item-value="id" clearable />
            </v-col>
            <v-col cols="12" sm="4">
              <v-select v-model="form.deployment_script" label="Deployment Script" :items="deploymentScripts" item-title="name" item-value="id" clearable />
            </v-col>
            <v-col cols="12">
              <div class="text-body-2 font-weight-bold mb-2">Devices</div>
              <v-card variant="outlined" rounded="lg" class="pa-2" style="max-height:200px;overflow-y:auto">
                <v-checkbox
                  v-for="d in allDevices"
                  :key="d.id"
                  v-model="form.devices"
                  :value="d.id"
                  :label="`${d.name} (${d.hostname})`"
                  density="compact"
                  hide-details
                />
                <div v-if="!allDevices.length" class="text-medium-emphasis text-caption pa-2">No devices defined.</div>
              </v-card>
            </v-col>
            <v-col cols="12">
              <v-checkbox v-model="form.is_active" label="Active" density="compact" hide-details />
            </v-col>
          </v-row>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="cancel">Cancel</v-btn>
          <v-btn color="primary" @click="save">Save</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
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
