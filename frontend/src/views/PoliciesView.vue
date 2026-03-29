<template>
  <div>
    <div class="d-flex align-center mb-5">
      <div class="text-h5 font-weight-bold">Policies</div>
      <v-spacer />
      <v-btn variant="tonal" prepend-icon="mdi-help-circle-outline" class="mr-3" @click="showHelp = true">How it works</v-btn>
      <v-btn color="primary" prepend-icon="mdi-plus" @click="openNew">New Policy</v-btn>
    </div>

    <!-- ── Help dialog ─────────────────────────────────────────────────────── -->
    <v-dialog v-model="showHelp" max-width="720" scrollable>
      <v-card rounded="lg">
        <v-card-title class="d-flex align-center pt-4 pb-2">
          <v-icon icon="mdi-calendar-clock" class="mr-2" color="primary" />
          Policies &amp; Scheduling
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" @click="showHelp = false" />
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-5" style="font-size:0.92rem;line-height:1.7">

          <p class="mb-3">
            A <strong>Policy</strong> ties devices, scripts, and a schedule together into an automated
            collection workflow. Policies are the primary way to keep configuration data current and
            trigger drift detection on a recurring basis.
          </p>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">What a Policy contains</div>
          <v-table density="compact" class="mb-3 rounded-lg" style="border:1px solid rgba(0,0,0,.12)">
            <tbody>
              <tr>
                <td class="font-weight-medium" style="width:30%">Name</td>
                <td>Human-readable identifier shown in the job monitor and notifications.</td>
              </tr>
              <tr>
                <td class="font-weight-medium">Collection Script</td>
                <td>Runs on the remote device (SSH/WinRM) or is expected from a push agent. Outputs raw configuration data.</td>
              </tr>
              <tr>
                <td class="font-weight-medium">Parser Script</td>
                <td>Runs on the Satellite server. Receives the raw output and produces a normalised canonical JSON document.</td>
              </tr>
              <tr>
                <td class="font-weight-medium">Deployment Script</td>
                <td>Optional. Used to push a remediation or hardening script to the device after collection, for example to apply a golden baseline.</td>
              </tr>
              <tr>
                <td class="font-weight-medium">Devices</td>
                <td>The set of devices this policy targets. Collection runs independently against each device in the list.</td>
              </tr>
              <tr>
                <td class="font-weight-medium">Schedule</td>
                <td>A cron expression that controls when the policy fires. See scheduling options below.</td>
              </tr>
              <tr>
                <td class="font-weight-medium">Active</td>
                <td>Inactive policies are never triggered automatically but can still be run manually.</td>
              </tr>
            </tbody>
          </v-table>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">Scheduling</div>
          <p class="mb-3">
            Policies use standard 5-field cron expressions. The visual scheduler converts your
            selections into a cron string automatically.
          </p>
          <v-table density="compact" class="mb-3 rounded-lg" style="border:1px solid rgba(0,0,0,.12)">
            <tbody>
              <tr><td class="font-weight-medium" style="width:22%">Hourly</td><td>Runs once per hour at a chosen minute offset. Useful for frequently changing or high-risk devices.</td></tr>
              <tr><td class="font-weight-medium">Daily</td><td>Runs once per day at a specific time. The most common choice for production infrastructure.</td></tr>
              <tr><td class="font-weight-medium">Weekly</td><td>Runs on one or more selected days of the week at a specific time.</td></tr>
              <tr><td class="font-weight-medium">Monthly</td><td>Runs on a specific day-of-month and time. Suitable for low-change, compliance-driven baselines.</td></tr>
              <tr><td class="font-weight-medium">Custom</td><td>Enter a raw cron expression for full control, e.g. <code>*/15 6-18 * * 1-5</code>.</td></tr>
            </tbody>
          </v-table>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">Execution flow</div>
          <ol class="pl-4" style="line-height:2">
            <li>At the scheduled time, CeleryBeat enqueues a job for every device in the policy.</li>
            <li>A Celery worker picks up each job and connects to the device via its configured transport (SSH, WinRM, or waits for push).</li>
            <li>The <strong>Collection Script</strong> is executed and its stdout captured.</li>
            <li>The <strong>Parser Script</strong> receives that output and returns canonical JSON.</li>
            <li>The JSON is validated against the canonical schema. Validation failures are recorded and surfaced as warnings — they do not suppress storage of the result.</li>
            <li>The result is stored as a <strong>Job</strong>. If a baseline already exists for the device, a <strong>Drift</strong> comparison is performed automatically.</li>
            <li>Any configured <strong>Notification</strong> rules are evaluated and alerts sent if thresholds are met.</li>
          </ol>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">Tips</div>
          <ul class="pl-4" style="line-height:2">
            <li>Assign one policy per <em>purpose</em> rather than one policy per device — a policy can target hundreds of devices simultaneously.</li>
            <li>Use separate collection + parser scripts per OS family (Linux, Windows, network) and assign the right combination per policy.</li>
            <li>Tag your devices and use tags to keep policy device lists manageable and queryable.</li>
            <li>Set a policy inactive instead of deleting it — inactive policies retain all historical job data.</li>
          </ul>

        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-3">
          <v-spacer />
          <v-btn color="primary" variant="tonal" @click="showHelp = false">Got it</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-data-table-server
      v-model:options="tableOptions"
      :headers="policyHeaders"
      :items="policies"
      :items-length="totalPolicies"
      :loading="loading"
      :items-per-page-options="[25, 50, 100]"
      density="compact"
      rounded="lg"
      elevation="1"
      hover
      @update:options="onTableOptions"
    >
      <template #item.cron_schedule="{ item }">
        <code>{{ item.cron_schedule }}</code>
      </template>
      <template #item.devices="{ item }">
        {{ item.devices?.length ?? 0 }}
      </template>
      <template #item.is_active="{ item }">
        <v-chip :color="item.is_active ? 'success' : 'default'" size="x-small" label>
          {{ item.is_active ? 'Yes' : 'No' }}
        </v-chip>
      </template>
      <template #item.actions="{ item }">
        <div class="d-flex ga-1">
          <v-btn size="x-small" variant="tonal" :loading="running === item.id" @click="runNow(item.id)">Run Now</v-btn>
          <v-btn size="x-small" variant="tonal" :disabled="!item.deployment_script" :loading="deploying === item.id" @click="deployNow(item)">Deploy</v-btn>
          <v-btn size="x-small" variant="tonal" @click="openEdit(item)">Edit</v-btn>
          <v-btn size="x-small" color="error" variant="tonal" @click="remove(item.id)">Delete</v-btn>
        </div>
      </template>
    </v-data-table-server>

    <!-- Confirm dialog -->
    <v-dialog v-model="confirmDialog.open" max-width="400" persistent>
      <v-card rounded="lg">
        <v-card-title class="pt-4">Confirm</v-card-title>
        <v-card-text>{{ confirmDialog.message }}</v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="confirmDialog.resolve(false)">Cancel</v-btn>
          <v-btn color="error" variant="tonal" @click="confirmDialog.resolve(true)">Confirm</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- ── Policy form dialog ─────────────────────────────────────────────── -->
    <v-dialog v-model="showForm" max-width="920" scrollable>
      <v-card rounded="lg">
        <v-card-title class="pt-4">{{ form.id ? 'Edit' : 'New' }} Policy</v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <v-row dense>

            <!-- Name / Description -->
            <v-col cols="12" sm="6">
              <v-text-field v-model="form.name" label="Name" required density="compact" />
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field v-model="form.description" label="Description" density="compact" />
            </v-col>

            <!-- ── Schedule ────────────────────────────────────────────── -->
            <v-col cols="12">
              <div class="text-body-2 font-weight-bold text-medium-emphasis text-uppercase mb-2 mt-1">Schedule</div>
            </v-col>

            <v-col cols="12" sm="3">
              <v-select
                v-model="schedFreq"
                label="Frequency"
                :items="FREQ_OPTIONS"
                density="compact"
                @update:modelValue="onFreqChange"
              />
            </v-col>

            <!-- Hourly -->
            <template v-if="schedFreq === 'Hourly'">
              <v-col cols="6" sm="2">
                <v-text-field v-model.number="schedMinute" label="At minute" type="number" min="0" max="59" density="compact" @update:modelValue="syncCron" />
              </v-col>
            </template>

            <!-- Daily -->
            <template v-if="schedFreq === 'Daily'">
              <v-col cols="6" sm="2">
                <v-text-field v-model.number="schedHour" label="Hour (UTC)" type="number" min="0" max="23" density="compact" @update:modelValue="syncCron" />
              </v-col>
              <v-col cols="6" sm="2">
                <v-text-field v-model.number="schedMinute" label="Minute" type="number" min="0" max="59" density="compact" @update:modelValue="syncCron" />
              </v-col>
            </template>

            <!-- Weekly -->
            <template v-if="schedFreq === 'Weekly'">
              <v-col cols="12" sm="6">
                <div class="text-caption mb-1 text-medium-emphasis">Days of week</div>
                <v-btn-toggle v-model="schedDays" multiple density="compact" rounded="lg" @update:modelValue="syncCron">
                  <v-btn v-for="(d, i) in DAY_NAMES" :key="i" :value="String(i)" size="small">{{ d }}</v-btn>
                </v-btn-toggle>
              </v-col>
              <v-col cols="6" sm="2">
                <v-text-field v-model.number="schedHour" label="Hour (UTC)" type="number" min="0" max="23" density="compact" @update:modelValue="syncCron" />
              </v-col>
              <v-col cols="6" sm="2">
                <v-text-field v-model.number="schedMinute" label="Minute" type="number" min="0" max="59" density="compact" @update:modelValue="syncCron" />
              </v-col>
            </template>

            <!-- Monthly -->
            <template v-if="schedFreq === 'Monthly'">
              <v-col cols="6" sm="2">
                <v-text-field v-model.number="schedDom" label="Day of month" type="number" min="1" max="28" density="compact" @update:modelValue="syncCron" />
              </v-col>
              <v-col cols="6" sm="2">
                <v-text-field v-model.number="schedHour" label="Hour (UTC)" type="number" min="0" max="23" density="compact" @update:modelValue="syncCron" />
              </v-col>
              <v-col cols="6" sm="2">
                <v-text-field v-model.number="schedMinute" label="Minute" type="number" min="0" max="59" density="compact" @update:modelValue="syncCron" />
              </v-col>
            </template>

            <!-- Custom -->
            <template v-if="schedFreq === 'Custom'">
              <v-col cols="12" sm="5">
                <v-text-field
                  v-model="form.cron_schedule"
                  label="Cron expression"
                  placeholder="0 2 * * *"
                  hint="minute hour dom month dow (UTC)"
                  persistent-hint
                  density="compact"
                />
              </v-col>
            </template>

            <!-- Human-readable summary -->
            <v-col cols="12">
              <v-alert density="compact" variant="tonal" color="info" rounded="lg" class="text-body-2">
                <span class="font-weight-medium">{{ cronSummary }}</span>
                <span v-if="schedFreq !== 'Custom'" class="text-medium-emphasis ml-2">({{ form.cron_schedule }})</span>
              </v-alert>
            </v-col>

            <!-- ── Scripts ───────────────────────────────────────────────── -->
            <v-col cols="12">
              <div class="text-body-2 font-weight-bold text-medium-emphasis text-uppercase mb-2 mt-2">Scripts</div>
            </v-col>
            <v-col cols="12" sm="4">
              <v-select v-model="form.collection_script" label="Collection Script" :items="collectionScripts" item-title="name" item-value="id" clearable density="compact" />
            </v-col>
            <v-col cols="12" sm="4">
              <v-select v-model="form.parser_script" label="Parser Script" :items="parserScripts" item-title="name" item-value="id" clearable density="compact" />
            </v-col>
            <v-col cols="12" sm="4">
              <v-select v-model="form.deployment_script" label="Deployment Script" :items="deploymentScripts" item-title="name" item-value="id" clearable density="compact" />
            </v-col>

            <!-- ── Device picker ─────────────────────────────────────────── -->
            <v-col cols="12">
              <div class="d-flex align-center mb-2 mt-2">
                <div class="text-body-2 font-weight-bold text-medium-emphasis text-uppercase">Devices</div>
                <v-spacer />
                <span class="text-caption text-medium-emphasis">{{ selectedDevices.length }} selected</span>
              </div>
              <v-row dense>
                <!-- Search + paginated list -->
                <v-col cols="12" sm="7">
                  <v-text-field
                    v-model="deviceSearch"
                    placeholder="Search by name, hostname or FQDN…"
                    prepend-inner-icon="mdi-magnify"
                    clearable
                    density="compact"
                    hide-details
                    class="mb-2"
                    @update:modelValue="onDeviceSearch"
                    @click:clear="onClearSearch"
                  />
                  <v-card variant="outlined" rounded="lg" style="max-height:240px;overflow-y:auto">
                    <v-list density="compact" :lines="false">
                      <v-list-item
                        v-for="d in devicePage"
                        :key="d.id"
                        :title="d.name"
                        :subtitle="`${d.hostname} · ${d.os_type ?? ''}`"
                        :active="isSelected(d.id)"
                        active-color="primary"
                        rounded="0"
                        @click="toggleDevice(d)"
                      >
                        <template #prepend>
                          <v-checkbox-btn :model-value="isSelected(d.id)" density="compact" readonly tabindex="-1" />
                        </template>
                      </v-list-item>
                      <v-list-item v-if="deviceLoading" class="justify-center">
                        <v-progress-circular indeterminate size="20" />
                      </v-list-item>
                      <v-list-item v-if="!deviceLoading && !devicePage.length" class="text-center text-caption text-medium-emphasis">
                        No devices found.
                      </v-list-item>
                    </v-list>
                    <div v-if="hasMore" class="text-center pa-1">
                      <v-btn variant="text" size="x-small" :loading="deviceLoadingMore" @click="loadMoreDevices">
                        Load more ({{ deviceTotal - devicePage.length }} remaining)
                      </v-btn>
                    </div>
                  </v-card>
                  <div class="text-caption text-medium-emphasis mt-1">
                    Showing {{ devicePage.length }} of {{ deviceTotal }} device{{ deviceTotal !== 1 ? 's' : '' }}
                  </div>
                </v-col>

                <!-- Selected chips -->
                <v-col cols="12" sm="5">
                  <div class="text-caption font-weight-medium mb-1">Selected</div>
                  <v-card variant="tonal" rounded="lg" style="min-height:60px;max-height:276px;overflow-y:auto" class="pa-2">
                    <v-chip
                      v-for="d in selectedDevices"
                      :key="d.id"
                      closable
                      size="small"
                      class="ma-1"
                      @click:close="removeSelected(d.id)"
                    >{{ d.name }}</v-chip>
                    <div v-if="!selectedDevices.length" class="text-caption text-medium-emphasis pa-1">None selected.</div>
                  </v-card>
                </v-col>
              </v-row>
            </v-col>

            <!-- ── Options ───────────────────────────────────────────────── -->
            <v-col cols="12" sm="4">
              <v-text-field
                v-model.number="form.delay_between_devices"
                label="Delay between devices (s)"
                type="number" min="0"
                density="compact"
                class="mt-2"
              />
            </v-col>
            <v-col cols="12" sm="8" class="d-flex align-center mt-2">
              <v-checkbox v-model="form.is_active" label="Active" density="compact" hide-details />
            </v-col>

          </v-row>
        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-3">
          <v-spacer />
          <v-btn @click="cancel">Cancel</v-btn>
          <v-btn color="primary" variant="tonal" @click="save">Save</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api'

const confirmDialog = ref({ open: false, message: '', resolve: () => {} })
function askConfirm(message) {
  return new Promise(resolve => {
    confirmDialog.value = { open: true, message, resolve: (val) => { confirmDialog.value.open = false; resolve(val) } }
  })
}

// ── Scheduler state ───────────────────────────────────────────────────────────

const FREQ_OPTIONS = ['Hourly', 'Daily', 'Weekly', 'Monthly', 'Custom']
const DAY_NAMES    = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']

const schedFreq   = ref('Daily')
const schedMinute = ref(0)
const schedHour   = ref(2)
const schedDays   = ref([])   // string[] for v-btn-toggle: ['1','3','5']
const schedDom    = ref(1)

const cronSummary = computed(() => {
  const mm = String(schedMinute.value ?? 0).padStart(2, '0')
  const hh = String(schedHour.value ?? 0).padStart(2, '0')
  switch (schedFreq.value) {
    case 'Hourly':
      return `Every hour at minute :${mm}`
    case 'Daily':
      return `Daily at ${hh}:${mm} UTC`
    case 'Weekly': {
      const names = schedDays.value.length
        ? schedDays.value.map(d => DAY_NAMES[parseInt(d)]).join(', ')
        : '(no days selected)'
      return `Weekly on ${names} at ${hh}:${mm} UTC`
    }
    case 'Monthly':
      return `Monthly on day ${schedDom.value} at ${hh}:${mm} UTC`
    default:
      return form.value.cron_schedule || '—'
  }
})

function syncCron() {
  const min = schedMinute.value ?? 0
  const hr  = schedHour.value  ?? 0
  switch (schedFreq.value) {
    case 'Hourly':
      form.value.cron_schedule = `${min} * * * *`
      break
    case 'Daily':
      form.value.cron_schedule = `${min} ${hr} * * *`
      break
    case 'Weekly': {
      const days = schedDays.value.length ? [...schedDays.value].sort().join(',') : '*'
      form.value.cron_schedule = `${min} ${hr} * * ${days}`
      break
    }
    case 'Monthly':
      form.value.cron_schedule = `${min} ${hr} ${schedDom.value ?? 1} * *`
      break
    // Custom: user edits form.cron_schedule directly
  }
}

function onFreqChange() {
  if (schedFreq.value !== 'Custom') syncCron()
}

/** Attempt to infer a friendly frequency from an existing cron string. */
function parseCron(cron) {
  schedFreq.value   = 'Daily'
  schedMinute.value = 0
  schedHour.value   = 2
  schedDays.value   = []
  schedDom.value    = 1
  if (!cron) return
  const parts = cron.trim().split(/\s+/)
  if (parts.length !== 5) { schedFreq.value = 'Custom'; return }
  const [min, hr, dom, month, dow] = parts
  schedMinute.value = parseInt(min, 10) || 0
  if (month !== '*')             { schedFreq.value = 'Custom'; return }
  if (!/^[\d*]/.test(dom))       { schedFreq.value = 'Custom'; return }
  if (dom !== '*') {
    schedFreq.value = 'Monthly'
    schedDom.value  = parseInt(dom, 10) || 1
    schedHour.value = hr === '*' ? 0 : parseInt(hr, 10)
    return
  }
  if (dow !== '*') {
    schedFreq.value = 'Weekly'
    schedDays.value = dow.split(',')
    schedHour.value = hr === '*' ? 0 : parseInt(hr, 10)
    return
  }
  if (hr === '*') { schedFreq.value = 'Hourly'; return }
  schedFreq.value = 'Daily'
  schedHour.value = parseInt(hr, 10) || 0
}

// ── Device picker state ───────────────────────────────────────────────────────

const deviceSearch      = ref('')
const devicePage        = ref([])
const devicePageNum     = ref(1)
const deviceTotal       = ref(0)
const deviceLoading     = ref(false)
const deviceLoadingMore = ref(false)
const selectedDevices   = ref([])

const hasMore = computed(() => devicePage.value.length < deviceTotal.value)

function isSelected(id) {
  return selectedDevices.value.some(d => d.id === id)
}

function toggleDevice(device) {
  if (isSelected(device.id)) {
    selectedDevices.value = selectedDevices.value.filter(d => d.id !== device.id)
  } else {
    selectedDevices.value = [...selectedDevices.value, device]
  }
}

function removeSelected(id) {
  selectedDevices.value = selectedDevices.value.filter(d => d.id !== id)
}

let _searchTimer = null
function onDeviceSearch() {
  clearTimeout(_searchTimer)
  _searchTimer = setTimeout(fetchDevices, 350)
}
function onClearSearch() {
  deviceSearch.value = ''
  fetchDevices()
}

async function fetchDevices() {
  deviceLoading.value  = true
  devicePageNum.value  = 1
  try {
    const { data } = await api.get('/devices/', {
      params: { search: deviceSearch.value || undefined, page: 1 },
    })
    devicePage.value  = data.results ?? data
    deviceTotal.value = data.count   ?? devicePage.value.length
  } finally {
    deviceLoading.value = false
  }
}

async function loadMoreDevices() {
  if (deviceLoadingMore.value) return
  deviceLoadingMore.value = true
  try {
    const { data } = await api.get('/devices/', {
      params: { search: deviceSearch.value || undefined, page: devicePageNum.value + 1 },
    })
    devicePageNum.value++
    const incoming    = data.results ?? data
    const existingIds = new Set(devicePage.value.map(d => d.id))
    devicePage.value  = [...devicePage.value, ...incoming.filter(d => !existingIds.has(d.id))]
  } finally {
    deviceLoadingMore.value = false
  }
}

// ── Policy form ───────────────────────────────────────────────────────────────

const policies          = ref([])
const totalPolicies     = ref(0)
const collectionScripts = ref([])
const parserScripts     = ref([])
const deploymentScripts = ref([])
const loading   = ref(false)
const showHelp  = ref(false)
const showForm  = ref(false)
const running   = ref(null)
const deploying = ref(null)
const form      = ref(blank())

const tableOptions = ref({ page: 1, itemsPerPage: 25, sortBy: [] })

const policyHeaders = [
  { title: 'Name',     key: 'name' },
  { title: 'Schedule', key: 'cron_schedule', sortable: false },
  { title: 'Devices',  key: 'devices',       sortable: false },
  { title: 'Active',   key: 'is_active',     sortable: false },
  { title: '',         key: 'actions',       sortable: false, align: 'end' },
]

function onTableOptions(options) {
  tableOptions.value = options
  fetchPolicies(options)
}

async function fetchPolicies(options = tableOptions.value) {
  loading.value = true
  try {
    const { data } = await api.get('/policies/', {
      params: { page: options.page, page_size: options.itemsPerPage },
    })
    policies.value     = data.results ?? data
    totalPolicies.value = data.count   ?? policies.value.length
  } finally {
    loading.value = false
  }
}

function blank() {
  return {
    name: '', description: '', cron_schedule: '0 2 * * *',
    delay_between_devices: 0,
    devices: [], collection_script: null, parser_script: null,
    deployment_script: null, is_active: true,
  }
}

onMounted(async () => {
  try {
    await Promise.all([
      api.get('/scripts/').then(r => {
        const scripts = r.data.results ?? r.data
        collectionScripts.value  = scripts.filter(s => s.script_type === 'collection'  && s.is_active)
        parserScripts.value      = scripts.filter(s => s.script_type === 'parser'      && s.is_active)
        deploymentScripts.value  = scripts.filter(s => s.script_type === 'deployment'  && s.is_active)
      }),
      fetchDevices(),
    ])
  } finally {}
})

function openNew() {
  form.value          = blank()
  selectedDevices.value = []
  deviceSearch.value  = ''
  parseCron('0 2 * * *')
  showForm.value      = true
}

function openEdit(p) {
  form.value = {
    ...p,
    collection_script:  p.collection_script?.id  ?? p.collection_script  ?? null,
    parser_script:      p.parser_script?.id      ?? p.parser_script      ?? null,
    deployment_script:  p.deployment_script?.id  ?? p.deployment_script  ?? null,
  }
  // Preserve full device objects so chips show names (policy API returns nested objects)
  selectedDevices.value = (p.devices ?? []).map(d =>
    typeof d === 'object' ? d : { id: d, name: `#${d}`, hostname: '' }
  )
  deviceSearch.value = ''
  parseCron(p.cron_schedule)
  showForm.value = true
}

function cancel() { showForm.value = false }

async function save() {
  const payload = { ...form.value, devices: selectedDevices.value.map(d => d.id) }
  if (form.value.id) {
    await api.patch(`/policies/${form.value.id}/`, payload)
  } else {
    await api.post('/policies/', payload)
  }
  cancel()
  fetchPolicies()
}

async function remove(id) {
  if (!await askConfirm('Delete this policy?')) return
  await api.delete(`/policies/${id}/`)
  fetchPolicies()
}

async function runNow(id) {
  running.value = id
  try { await api.post(`/policies/${id}/run/`) }
  finally { setTimeout(() => { running.value = null }, 2000) }
}

async function deployNow(p) {
  if (!await askConfirm(`Run deployment script on all devices in "${p.name}"?`)) return
  deploying.value = p.id
  try { await api.post(`/policies/${p.id}/deploy/`) }
  finally { setTimeout(() => { deploying.value = null }, 2000) }
}
</script>
