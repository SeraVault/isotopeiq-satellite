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
                <td>Runs on the remote device (SSH/WinRM). Outputs raw configuration data. Not used for Agent Pull devices — those run their own embedded collector.</td>
              </tr>
              <tr>
                <td class="font-weight-medium">Parser Script</td>
                <td>Runs on the Satellite server. Receives the raw output and produces a normalised canonical JSON document.</td>
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
            <li>A Celery worker picks up each job and connects to the device via its configured transport (SSH, WinRM). For <strong>Agent Pull</strong> devices, the satellite calls <code>GET /collect</code> on the agent directly — no script execution needed.</li>
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

            <!-- ── Collection Method ─────────────────────────────────────── -->
            <v-col cols="12">
              <div class="text-body-2 font-weight-bold text-medium-emphasis text-uppercase mb-2 mt-2">Collection Method</div>
              <v-btn-toggle v-model="form.collection_method" mandatory density="compact" rounded="lg" color="primary">
                <v-btn value="agent" prepend-icon="mdi-lan-connect">Query Agent Endpoint</v-btn>
                <v-btn value="script" prepend-icon="mdi-console">Run Collection Script</v-btn>
              </v-btn-toggle>
              <div v-if="form.collection_method === 'agent'" class="text-caption text-medium-emphasis mt-2">
                The satellite calls <code>GET /collect</code> on each agent's HTTP port on schedule. No collection script needed.
              </div>
              <div v-else class="text-caption text-medium-emphasis mt-2">
                The satellite connects to each device via SSH, WinRM, or Telnet and executes the selected script.
              </div>
            </v-col>

            <!-- Script Job (script mode only) -->
            <v-col v-if="form.collection_method === 'script'" cols="12" sm="6">
              <v-select
                v-model="form.script_job"
                label="Script Job *"
                hint="Defines the collection and parser scripts to run."
                persistent-hint
                :items="scriptJobs"
                item-title="name"
                item-value="id"
                clearable
                density="compact"
              >
                <template #item="{ item, props }">
                  <v-list-item v-bind="props">
                    <template #subtitle>
                      <span v-if="item.raw.steps?.length" class="text-caption text-medium-emphasis">
                        {{ item.raw.steps.length }} step{{ item.raw.steps.length !== 1 ? 's' : '' }}:
                        {{ item.raw.steps.map(s => `${s.script_run_on === 'client' ? '➡ device' : '⚙ Satellite'}: ${s.script_name}`).join(' → ') }}
                      </span>
                    </template>
                  </v-list-item>
                </template>
              </v-select>
            </v-col>


            <!-- ── Device picker ─────────────────────────────────────────── -->
            <v-col cols="12">
              <div class="d-flex align-center mb-2 mt-2">
                <div class="text-body-2 font-weight-bold text-medium-emphasis text-uppercase">Devices</div>
                <v-spacer />
                <span class="text-caption text-medium-emphasis">{{ selectedDevices.length }} selected</span>
              </div>

              <!-- Contextual banner: warn when device type mismatches collection method -->
              <v-alert
                v-if="form.collection_method === 'agent' && selectedNonAgentCount > 0"
                type="warning" variant="tonal" density="compact" rounded="lg" class="mb-3 text-body-2"
                icon="mdi-alert-outline"
              >
                {{ selectedNonAgentCount }} selected device{{ selectedNonAgentCount !== 1 ? 's are' : ' is' }} not agent-type and will be skipped during execution.
              </v-alert>
              <v-alert
                v-else-if="form.collection_method === 'script' && selectedAgentCount > 0"
                type="warning" variant="tonal" density="compact" rounded="lg" class="mb-3 text-body-2"
                icon="mdi-alert-outline"
              >
                {{ selectedAgentCount }} selected device{{ selectedAgentCount !== 1 ? 's are' : ' is' }} agent-type and will be skipped — switch to <strong>Query Agent Endpoint</strong> to include them.
              </v-alert>
              <v-alert
                v-else-if="selectedAgentCount > 0 && selectedNonAgentCount === 0"
                type="success" variant="tonal" density="compact" rounded="lg" class="mb-3 text-body-2"
                icon="mdi-lan-connect"
              >
                All selected devices are <span class="font-weight-medium">Agent Pull</span>.
                The satellite calls each agent’s HTTP endpoint on schedule — only a <span class="font-weight-medium">Parser Script</span> is needed.
              </v-alert>

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
                        :subtitle="d.hostname"
                        :active="isSelected(d.id)"
                        color="primary"
                        rounded="0"
                        @click="toggleDevice(d)"
                      >
                        <template #prepend>
                          <v-checkbox-btn :model-value="isSelected(d.id)" density="compact" readonly tabindex="-1" />
                        </template>
                        <template #append>
                          <v-chip
                            :color="d.connection_type === 'agent' ? 'success' : 'default'"
                            size="x-small" label class="ml-1" style="font-size:10px"
                          >{{ d.connection_type }}</v-chip>
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
                      :color="d.connection_type === 'agent' ? 'success' : undefined"
                      @click:close="removeSelected(d.id)"
                    >
                      <v-icon v-if="d.connection_type === 'agent'" size="12" start>mdi-lan-connect</v-icon>
                      {{ d.name }}
                    </v-chip>
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

            <!-- ── Post-Collection Actions ───────────────────────────────── -->
            <v-col cols="12">
              <div class="d-flex align-center mb-2 mt-2">
                <div class="text-body-2 font-weight-bold text-medium-emphasis text-uppercase">Post-Collection Actions</div>
                <v-tooltip location="end" max-width="340">
                  <template #activator="{ props }">
                    <v-icon v-bind="props" size="16" class="ml-1 text-medium-emphasis">mdi-help-circle-outline</v-icon>
                  </template>
                  Automatically send a notification or export the baseline when a specific event occurs for this policy. Destinations are configured in System Settings.
                </v-tooltip>
              </div>

              <!-- Existing actions list -->
              <div v-if="policyActions.length" class="mb-2">
                <v-chip
                  v-for="act in policyActions"
                  :key="act.id"
                  closable
                  size="small"
                  :color="actionDestColor(act.destination)"
                  class="ma-1"
                  :prepend-icon="actionDestIcon(act.destination)"
                  @click:close="removeAction(act)"
                >
                  {{ act.trigger_label }} → {{ act.destination_label }}
                </v-chip>
              </div>
              <div v-else class="text-caption text-medium-emphasis mb-2">No actions configured.</div>

              <!-- New policy: save first before adding actions -->
              <v-alert
                v-if="!form.id"
                type="info"
                variant="tonal"
                density="compact"
                class="mb-2 text-body-2"
                icon="mdi-information-outline"
              >Save the policy first, then re-open it to configure post-collection actions.</v-alert>

              <!-- Add action row (edit mode only) -->
              <template v-else>
              <v-row dense align="center">
                <v-col cols="12" sm="4">
                  <v-select
                    v-model="newAction.trigger"
                    :items="triggerOptions"
                    item-title="label"
                    item-value="value"
                    label="When…"
                    density="compact"
                    hide-details
                  />
                </v-col>
                <v-col cols="12" sm="4">
                  <v-select
                    v-model="newAction.destination"
                    :items="destinationOptions"
                    item-title="label"
                    item-value="value"
                    label="Send to…"
                    density="compact"
                    hide-details
                  />
                </v-col>
                <v-col cols="12" sm="auto">
                  <v-btn
                    variant="tonal"
                    prepend-icon="mdi-plus"
                    size="small"
                    :disabled="!newAction.trigger || !newAction.destination"
                    @click="addAction"
                  >Add</v-btn>
                </v-col>
              </v-row>
              <v-alert
                v-if="actionError"
                type="error"
                variant="tonal"
                density="compact"
                class="mt-2 text-body-2"
              >{{ actionError }}</v-alert>
              </template>
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

const selectedAgentCount    = computed(() => selectedDevices.value.filter(d => d.connection_type === 'agent').length)
const selectedNonAgentCount = computed(() => selectedDevices.value.filter(d => d.connection_type !== 'agent').length)

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
      params: {
        search: deviceSearch.value || undefined,
        page: 1,
      },
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
      params: {
        search: deviceSearch.value || undefined,
        page: devicePageNum.value + 1,
      },
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
const scriptJobs        = ref([])
const loading   = ref(false)
const showHelp  = ref(false)
const showForm  = ref(false)
const running   = ref(null)
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
    collection_method: 'script',
    delay_between_devices: 0,
    devices: [], script_job: null, is_active: true,
  }
}

onMounted(async () => {
  try {
    await Promise.all([
      api.get('/scripts/script-jobs/', { params: { page_size: 1000 } }).then(r => {
        scriptJobs.value = r.data.results ?? r.data ?? []
      }),
      fetchDevices(),
    ])
  } finally {}
})

function openNew() {
  form.value             = blank()
  selectedDevices.value  = []
  deviceSearch.value     = ''
  policyActions.value    = []
  newAction.value        = { trigger: null, destination: null }
  actionError.value      = ''
  parseCron('0 2 * * *')
  showForm.value         = true
}

function openEdit(p) {
  form.value = {
    ...p,
    script_job: p.script_job_detail?.id ?? p.script_job ?? null,
  }
  // Preserve full device objects so chips show names (policy API returns nested objects)
  selectedDevices.value = (p.devices ?? []).map(d =>
    typeof d === 'object' ? d : { id: d, name: `#${d}`, hostname: '' }
  )
  deviceSearch.value     = ''
  newAction.value        = { trigger: null, destination: null }
  actionError.value      = ''
  policyActions.value    = []
  parseCron(p.cron_schedule)
  loadActions(p.id)
  showForm.value = true
}

function cancel() { showForm.value = false }

async function save() {
  // Auto-commit any pending action selection before closing the form
  if (form.value.id && newAction.value.trigger && newAction.value.destination) {
    await addAction()
    if (actionError.value) return  // Don't close if the auto-add failed
  }
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

// ── Post-collection actions ───────────────────────────────────────────────────

const triggerOptions = [
  { value: 'new_baseline',   label: 'New Baseline Established' },
  { value: 'drift_detected', label: 'Drift Detected'           },
  { value: 'always',         label: 'Always (every success)'   },
]
const destinationOptions = [
  { value: 'syslog', label: 'Syslog'    },
  { value: 'email',  label: 'Email'     },
  { value: 'ftp',    label: 'FTP/SFTP'  },
]

const policyActions = ref([])
const newAction     = ref({ trigger: null, destination: null })
const actionError   = ref('')

function actionDestColor(dest) {
  return { syslog: 'default', email: 'blue', ftp: 'teal' }[dest] ?? 'default'
}
function actionDestIcon(dest) {
  return { syslog: 'mdi-server', email: 'mdi-email-outline', ftp: 'mdi-server-network' }[dest] ?? 'mdi-bell-outline'
}

async function loadActions(policyId) {
  if (!policyId) { policyActions.value = []; return }
  try {
    const { data } = await api.get('/settings/actions/', { params: { policy: policyId } })
    policyActions.value = data.results ?? data
  } catch (e) {
    console.error('[loadActions] failed:', e)
    policyActions.value = []
  }
}

async function addAction() {
  actionError.value = ''
  const dup = policyActions.value.find(
    a => a.trigger === newAction.value.trigger && a.destination === newAction.value.destination
  )
  if (dup) { actionError.value = 'That trigger/destination combination already exists.'; return }
  try {
    const { data } = await api.post('/settings/actions/', {
      policy:      form.value.id,
      trigger:     newAction.value.trigger,
      destination: newAction.value.destination,
    })
    policyActions.value = [...policyActions.value, data]
    newAction.value = { trigger: null, destination: null }
  } catch (e) {
    actionError.value = e.response?.data?.non_field_errors?.[0]
      ?? e.response?.data?.detail
      ?? 'Could not add action.'
  }
}

async function removeAction(act) {
  await api.delete(`/settings/actions/${act.id}/`)
  policyActions.value = policyActions.value.filter(a => a.id !== act.id)
}

</script>
