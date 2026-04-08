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
          Scripts
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" @click="showHelp = false" />
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-5" style="font-size:0.92rem;line-height:1.7">

          <p class="mb-3">
            Scripts are the executable units that Satellite uses to <strong>collect</strong>,
            <strong>parse</strong>, and optionally <strong>deploy</strong> configuration data.
            Assign scripts directly to Policies (for scheduled baseline runs) or wire them
            together in Script Jobs (for ad-hoc and utility workflows).
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
      <v-tab value="Scripts">Scripts</v-tab>
      <v-tab value="ScriptJobs">Script Jobs</v-tab>
    </v-tabs>

    <!-- ── WINDOW ─────────────────────────────────────────────────────────── -->
    <v-window v-model="activeTab">

      <!-- ── SCRIPTS TAB ────────────────────────────────────────────────────── -->
      <v-window-item value="Scripts">
        <div class="d-flex justify-space-between align-center mb-4">
          <span class="text-body-2 text-medium-emphasis">{{ totalScripts }} script(s)</span>
          <v-btn color="primary" prepend-icon="mdi-plus" @click="openNewScriptInEditor">New Script</v-btn>
        </div>

        <v-data-table-server
          v-model:options="scrTableOptions"
          :headers="scrHeaders"
          :items="scripts"
          :items-length="totalScripts"
          :loading="scrLoading"
          :items-per-page-options="[25, 50, 100]"
          density="compact"
          rounded="lg"
          elevation="1"
          hover
          @update:options="onScrTableOptions"
        >
          <template #item.run_on="{ item }">
            <v-chip
              size="x-small" label
              :color="item.run_on === 'client' ? 'blue-darken-1' : item.run_on === 'server' ? 'purple-darken-1' : 'teal-darken-1'"
            >{{ item.run_on }}</v-chip>
          </template>
          <template #item.language="{ item }">
            <span class="text-caption text-medium-emphasis">{{ item.language || '—' }}</span>
          </template>
          <template #item.is_active="{ item }">
            <v-chip :color="item.is_active ? 'success' : 'default'" size="x-small" label>
              {{ item.is_active ? 'Yes' : 'No' }}
            </v-chip>
          </template>
          <template #item.actions="{ item }">
            <div class="d-flex ga-1">
              <v-btn size="x-small" variant="tonal" @click="openScriptInEditor(item)">Edit</v-btn>
              <v-btn size="x-small" color="error" variant="tonal" @click="removeScript(item.id)">Delete</v-btn>
            </div>
          </template>
        </v-data-table-server>
      </v-window-item>

      <!-- ── SCRIPT JOBS TAB ───────────────────────────────────────────────── -->
      <v-window-item value="ScriptJobs">
        <!-- What is a Script Job? -->
        <v-alert type="info" variant="tonal" density="compact" rounded="lg" class="mb-4 text-body-2" icon="mdi-information-outline">
          A <strong>Script Job</strong> is an ordered pipeline of steps. Each step runs a script on the remote
          device (<em>client</em>) or the satellite (<em>server</em>), optionally piping its output to the next
          step, saving results, and enabling baseline storage or drift detection.
        </v-alert>

        <div class="d-flex justify-space-between align-center mb-4">
          <span class="text-body-2 text-medium-emphasis">{{ totalScriptJobs }} job definition(s)</span>
          <v-btn color="primary" prepend-icon="mdi-plus" @click="openNewScriptJob">New Script Job</v-btn>
        </div>

        <v-data-table
          :headers="sjHeaders"
          :items="scriptJobs"
          :loading="sjLoading"
          density="compact"
          rounded="lg"
          elevation="1"
          hover
        >
          <template #item.steps="{ item }">
            <div class="d-flex ga-1 flex-wrap">
              <template v-if="item.steps?.length">
                <v-chip
                  v-for="(s, i) in item.steps"
                  :key="i"
                  size="x-small"
                  label
                  :color="s.run_on === 'client' ? 'blue-darken-1' : 'purple-darken-1'"
                >
                  {{ s.run_on === 'client' ? 'Client' : 'Server' }}
                  <span class="ml-1 opacity-70">{{ s.script_name }}</span>
                  <v-icon v-if="s.enable_baseline" size="12" class="ml-1">mdi-database</v-icon>
                  <v-icon v-if="s.enable_drift" size="12" class="ml-1">mdi-chart-timeline-variant</v-icon>
                </v-chip>
              </template>
              <span v-else class="text-caption text-medium-emphasis">No steps</span>
            </div>
          </template>
          <template #item.is_active="{ item }">
            <v-chip :color="item.is_active ? 'success' : 'default'" size="x-small" label>
              {{ item.is_active ? 'Yes' : 'No' }}
            </v-chip>
          </template>
          <template #item.actions="{ item }">
            <div class="d-flex ga-1">
              <v-btn size="x-small" variant="tonal" @click="openRunNow(item)">Run Now</v-btn>
              <v-btn size="x-small" variant="tonal" @click="openScriptJobResults(item)">Results</v-btn>
              <v-btn size="x-small" variant="tonal" @click="openEditScriptJob(item)">Edit</v-btn>
              <v-btn size="x-small" color="error" variant="tonal" @click="removeScriptJob(item.id)">Delete</v-btn>
            </div>
          </template>
        </v-data-table>
      </v-window-item>
    </v-window>

    <!-- ── SCRIPT JOB FORM ────────────────────────────────────────────────── -->
    <v-dialog v-model="sjForm.show" max-width="860" scrollable>
      <v-card rounded="lg">
        <v-card-title class="pt-4">{{ sjForm.id ? 'Edit' : 'New' }} Script Job</v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <v-row dense>
            <v-col cols="12" sm="6">
              <v-text-field v-model="sjForm.name" label="Name *" density="compact" />
            </v-col>
            <v-col cols="12" sm="6">
              <v-text-field v-model="sjForm.description" label="Description" density="compact" />
            </v-col>

            <!-- ── Steps ────────────────────────────────────────────────── -->
            <v-col cols="12">
              <div class="d-flex align-center mb-2 mt-2">
                <div class="text-body-2 font-weight-bold text-medium-emphasis text-uppercase">Steps</div>
                <div class="text-caption text-medium-emphasis ml-2">(execute in order — at least one required)</div>
                <v-spacer />
                <v-btn size="small" variant="tonal" prepend-icon="mdi-plus" @click="sjAddStep">Add Step</v-btn>
              </div>
              <div v-if="!sjForm.steps.length" class="text-caption text-medium-emphasis pa-3 text-center">
                No steps yet. Click <strong>Add Step</strong> to define what this job does.
              </div>
              <v-card
                v-for="(step, idx) in sjForm.steps"
                :key="idx"
                variant="outlined"
                rounded="lg"
                class="mb-3 pa-3"
              >
                <div class="d-flex align-center mb-3">
                  <span class="text-caption font-weight-bold text-medium-emphasis text-uppercase">
                    Step {{ idx + 1 }}
                  </span>
                  <v-spacer />
                  <v-btn icon="mdi-arrow-up" size="x-small" variant="text" :disabled="idx === 0" @click="sjMoveStep(idx, -1)" />
                  <v-btn icon="mdi-arrow-down" size="x-small" variant="text" :disabled="idx === sjForm.steps.length - 1" @click="sjMoveStep(idx, 1)" />
                  <v-btn icon="mdi-delete-outline" size="x-small" variant="text" color="error" @click="sjRemoveStep(idx)" />
                </div>
                <v-row dense>
                  <v-col cols="12" sm="7">
                    <v-select
                      v-model="step.script"
                      label="Script *"
                      :items="allScripts"
                      item-title="displayName"
                      item-value="id"
                      density="compact"
                      clearable
                    />
                  </v-col>
                  <v-col cols="12" sm="5" class="d-flex align-center">
                    <v-btn-toggle v-model="step.run_on" mandatory density="compact" rounded="lg" style="width:100%">
                      <v-btn value="client" size="small" style="flex:1">
                        <v-icon start size="14">mdi-laptop</v-icon>Client
                      </v-btn>
                      <v-btn value="server" size="small" style="flex:1">
                        <v-icon start size="14">mdi-server</v-icon>Server
                      </v-btn>
                    </v-btn-toggle>
                  </v-col>
                  <v-col cols="12">
                    <div class="d-flex flex-wrap align-center" style="gap:4px 20px">
                      <v-checkbox v-model="step.pipe_to_next" label="Pipe output to next step" density="compact" hide-details />
                      <v-checkbox v-model="step.save_output" label="Save output" density="compact" hide-details />
                      <v-checkbox v-model="step.enable_baseline" label="Save as baseline" density="compact" hide-details />
                      <v-checkbox v-model="step.enable_drift" label="Check drift" density="compact" hide-details />
                    </div>
                    <div v-if="step.enable_baseline || step.enable_drift" class="text-caption text-medium-emphasis ml-1 mt-1">
                      Output must be canonical JSON (use a server-side parser step to transform raw output first).
                    </div>
                  </v-col>
                </v-row>
              </v-card>
            </v-col>

            <v-col cols="12" class="mt-2">
              <v-checkbox v-model="sjForm.is_active" label="Active" density="compact" hide-details />
            </v-col>
          </v-row>
        </v-card-text>
        <v-card-actions class="pa-4 pt-0">
          <v-spacer />
          <v-btn @click="sjForm.show = false">Cancel</v-btn>
          <v-btn color="primary" variant="tonal" :loading="sjForm.saving" @click="saveScriptJob">Save</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- ── RUN NOW DIALOG ─────────────────────────────────────────────────── -->
    <v-dialog v-model="runNowDialog.show" max-width="480">
      <v-card rounded="lg">
        <v-card-title class="pt-4">Run Now — {{ runNowDialog.job?.name }}</v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <v-autocomplete
            v-model="runNowDialog.device_id"
            :label="runNowDialog.needsDevice ? 'Device *' : 'Device (optional — leave blank for server-only)'"
            :items="runNowDialog.devices"
            item-title="name"
            item-value="id"
            :loading="runNowDialog.deviceLoading"
            clearable
            density="compact"
            :hint="runNowDialog.needsDevice ? 'Required — this job has client steps.' : 'Leave blank to run server steps only.'"
            persistent-hint
          />
          <v-alert
            v-if="runNowDialog.needsDevice && !runNowDialog.device_id"
            type="warning"
            density="compact"
            class="mt-3"
            text="This job has at least one client step. Please select a device."
          />
        </v-card-text>
        <v-card-actions class="pa-4 pt-0">
          <v-spacer />
          <v-btn @click="runNowDialog.show = false">Cancel</v-btn>
          <v-btn
            color="primary"
            variant="tonal"
            :loading="runNowDialog.running"
            :disabled="runNowDialog.needsDevice && !runNowDialog.device_id"
            @click="confirmRunNow"
          >Run</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-snackbar v-model="snackbar.show" :color="snackbar.color" timeout="3000" location="bottom right">
      {{ snackbar.text }}
    </v-snackbar>

    <!-- ── SCRIPT JOB RESULTS ────────────────────────────────────────────── -->
    <v-dialog v-model="sjResultsDialog.show" max-width="960" scrollable>
      <v-card rounded="lg">
        <v-card-title class="pt-4 d-flex align-center">
          Results — {{ sjResultsDialog.job?.name }}
          <v-spacer />
          <v-btn icon="mdi-refresh" variant="text" size="small" :loading="sjResultsDialog.loading" @click="loadScriptJobResults" />
          <v-btn icon="mdi-close" variant="text" size="small" @click="sjResultsDialog.show = false" />
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-0">
          <v-data-table
            :headers="sjResultHeaders"
            :items="sjResultsDialog.results"
            :loading="sjResultsDialog.loading"
            density="compact"
            :items-per-page="25"
            hover
          >
            <template #item.device="{ item }">{{ item.device_name || '(server)' }}</template>
            <template #item.status="{ item }">
              <v-chip
                :color="{ success: 'success', failed: 'error', running: 'info', pending: 'default' }[item.status]"
                size="x-small" label
              >{{ item.status }}</v-chip>
            </template>
            <template #item.started_at="{ item }">{{ item.started_at ? new Date(item.started_at).toLocaleString() : '—' }}</template>
            <template #item.finished_at="{ item }">{{ item.finished_at ? new Date(item.finished_at).toLocaleString() : '—' }}</template>
            <template #item.actions="{ item }">
              <v-btn size="x-small" variant="tonal" @click="viewScriptJobOutput(item)">Output</v-btn>
            </template>
          </v-data-table>
        </v-card-text>
      </v-card>
    </v-dialog>

    <!-- ── SCRIPT JOB OUTPUT VIEWER ─────────────────────────────────────── -->
    <v-dialog v-model="sjOutputDialog.show" max-width="900" scrollable>
      <v-card rounded="lg">
        <v-card-title class="pt-4 d-flex align-center">
          Output
          <v-chip :color="{ success: 'success', failed: 'error' }[sjOutputDialog.result?.status]" size="x-small" label class="ml-2">
            {{ sjOutputDialog.result?.status }}
          </v-chip>
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" size="small" @click="sjOutputDialog.show = false" />
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-4">
          <!-- Per-step outputs (new format) -->
          <template v-if="sjOutputDialog.result?.step_outputs?.length">
            <div
              v-for="step in sjOutputDialog.result.step_outputs"
              :key="step.order"
              class="mb-4"
            >
              <div class="text-caption font-weight-bold text-medium-emphasis text-uppercase mb-1">
                Step {{ step.order + 1 }} — {{ step.script }}
                <v-chip size="x-small" label :color="step.run_on === 'client' ? 'blue-darken-1' : 'purple-darken-1'" class="ml-1">
                  {{ step.run_on }}
                </v-chip>
              </div>
              <v-sheet rounded="lg" color="grey-darken-4" class="pa-3" style="font-family:monospace;font-size:0.8rem;white-space:pre-wrap;max-height:280px;overflow-y:auto">{{ step.output }}</v-sheet>
            </div>
          </template>
          <!-- Legacy fields for older results -->
          <template v-else>
            <template v-if="sjOutputDialog.result?.client_output">
              <div class="text-caption font-weight-bold text-medium-emphasis text-uppercase mb-1">Client Output</div>
              <v-sheet rounded="lg" color="grey-darken-4" class="pa-3 mb-4" style="font-family:monospace;font-size:0.8rem;white-space:pre-wrap;max-height:280px;overflow-y:auto">{{ sjOutputDialog.result.client_output }}</v-sheet>
            </template>
            <template v-if="sjOutputDialog.result?.server_output">
              <div class="text-caption font-weight-bold text-medium-emphasis text-uppercase mb-1">Server Output</div>
              <v-sheet rounded="lg" color="grey-darken-4" class="pa-3 mb-4" style="font-family:monospace;font-size:0.8rem;white-space:pre-wrap;max-height:280px;overflow-y:auto">{{ sjOutputDialog.result.server_output }}</v-sheet>
            </template>
          </template>
          <template v-if="sjOutputDialog.result?.parsed_output">
            <div class="text-caption font-weight-bold text-medium-emphasis text-uppercase mb-1">Parsed / Baseline Output</div>
            <v-sheet rounded="lg" color="grey-darken-4" class="pa-3 mb-4" style="font-family:monospace;font-size:0.8rem;white-space:pre-wrap;max-height:280px;overflow-y:auto">{{ JSON.stringify(sjOutputDialog.result.parsed_output, null, 2) }}</v-sheet>
          </template>
          <template v-if="sjOutputDialog.result?.error_message">
            <div class="text-caption font-weight-bold text-error text-uppercase mb-1">Error</div>
            <v-sheet rounded="lg" color="red-darken-4" class="pa-3" style="font-family:monospace;font-size:0.8rem;white-space:pre-wrap">{{ sjOutputDialog.result.error_message }}</v-sheet>
          </template>
        </v-card-text>
      </v-card>
    </v-dialog>



    <!-- Script editor is now a separate page at /scripts/:id/edit and /scripts/new -->

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
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'

const confirmDialog = ref({ open: false, message: '', resolve: () => {} })
function askConfirm(message) {
  return new Promise(resolve => {
    confirmDialog.value = { open: true, message, resolve: (val) => { confirmDialog.value.open = false; resolve(val) } }
  })
}
import api from '../api'

const router = useRouter()

const activeTab  = ref('Scripts')
const showHelp   = ref(false)

// ── individual scripts ────────────────────────────────────────────────────────
const scripts = ref([])
const scrLoading = ref(false)
const totalScripts = ref(0)
const scrTableOptions = ref({ page: 1, itemsPerPage: 25, sortBy: [] })
const scrHeaders = [
  { title: 'Name',      key: 'name' },
  { title: 'Type',      key: 'script_type' },
  { title: 'Runs On',   key: 'run_on',     sortable: false },
  { title: 'Language',  key: 'language',   sortable: false },
  { title: 'Target OS', key: 'target_os' },
  { title: 'Version',   key: 'version' },
  { title: 'Active',    key: 'is_active',  sortable: false },
  { title: '',          key: 'actions',    sortable: false, align: 'end' },
]

function onScrTableOptions(options) {
  scrTableOptions.value = options
  loadScripts(options)
}

async function loadScripts(options = scrTableOptions.value) {
  scrLoading.value = true
  try {
    const { data } = await api.get('/scripts/', {
      params: { page: options.page, page_size: options.itemsPerPage },
    })
    scripts.value      = data.results ?? data
    totalScripts.value = data.count   ?? scripts.value.length
  } finally {
    scrLoading.value = false
  }
}

async function removeScript(id) {
  if (!await askConfirm('Delete this script?')) return
  await api.delete(`/scripts/${id}/`)
  loadScripts()
}

function openNewScriptInEditor() {
  router.push('/scripts/new')
}

function openScriptInEditor(s) {
  router.push(`/scripts/${s.id}/edit`)
}

// ── script jobs ───────────────────────────────────────────────────────────────
const scriptJobs = ref([])
const sjLoading = ref(false)
const totalScriptJobs = ref(0)
const allScripts = ref([])

const sjHeaders = [
  { title: 'Name',   key: 'name',      sortable: true },
  { title: 'Steps',  key: 'steps',     sortable: false },
  { title: 'Active', key: 'is_active', sortable: false },
  { title: '',       key: 'actions',   sortable: false, align: 'end' },
]
const sjResultHeaders = [
  { title: 'Device',       key: 'device',       sortable: false },
  { title: 'Status',       key: 'status',       sortable: false },
  { title: 'Triggered By', key: 'triggered_by', sortable: false },
  { title: 'Started',      key: 'started_at',   sortable: false },
  { title: 'Finished',     key: 'finished_at',  sortable: false },
  { title: '',             key: 'actions',      sortable: false, align: 'end' },
]

async function loadScriptJobs() {
  sjLoading.value = true
  try {
    const res = await api.get('/scripts/script-jobs/')
    scriptJobs.value = res.data?.results ?? res.data ?? []
    totalScriptJobs.value = scriptJobs.value.length
  } finally {
    sjLoading.value = false
  }
}

async function loadAllScripts() {
  const res = await api.get('/scripts/', { params: { page_size: 1000 } })
  allScripts.value = (res.data?.results ?? res.data ?? []).map(s => ({
    ...s,
    displayName: `${s.name} (${s.script_type})`,
  }))
}

// ── Script Job form ──────────────────────────────────────────────────────────
const BLANK_STEP = () => ({
  script: null,
  run_on: 'client',
  pipe_to_next: true,
  save_output: false,
  enable_baseline: false,
  enable_drift: false,
})
const BLANK_SJ_FORM = () => ({
  show: false, id: null, saving: false,
  name: '', description: '',
  steps: [],
  is_active: true,
})
const sjForm = ref(BLANK_SJ_FORM())

function sjAddStep() {
  sjForm.value.steps.push(BLANK_STEP())
}
function sjRemoveStep(idx) {
  sjForm.value.steps.splice(idx, 1)
}
function sjMoveStep(idx, dir) {
  const steps = sjForm.value.steps
  const newIdx = idx + dir
  if (newIdx < 0 || newIdx >= steps.length) return
  const [item] = steps.splice(idx, 1)
  steps.splice(newIdx, 0, item)
}

// Run Now dialog
const runNowDialog = ref({ show: false, job: null, device_id: null, devices: [], deviceLoading: false, running: false, needsDevice: false })
const snackbar = ref({ show: false, text: '', color: 'success' })

function showSnack(text, color = 'success') {
  snackbar.value = { show: true, text, color }
}

async function openRunNow(item) {
  const needsDevice = (item.steps ?? []).some(s => s.run_on === 'client')
  runNowDialog.value = { show: true, job: item, device_id: null, devices: [], deviceLoading: true, running: false, needsDevice }
  try {
    const res = await api.get('/devices/', { params: { page_size: 1000 } })
    runNowDialog.value.devices = res.data?.results ?? res.data ?? []
  } finally {
    runNowDialog.value.deviceLoading = false
  }
}

async function confirmRunNow() {
  runNowDialog.value.running = true
  try {
    const body = runNowDialog.value.device_id ? { device_id: runNowDialog.value.device_id } : {}
    await api.post(`/scripts/script-jobs/${runNowDialog.value.job.id}/run/`, body)
    runNowDialog.value.show = false
    showSnack('Job queued successfully.')
  } catch (e) {
    showSnack(e.response?.data?.detail ?? 'Failed to queue job.', 'error')
  } finally {
    runNowDialog.value.running = false
  }
}

async function openNewScriptJob() {
  await loadAllScripts()
  sjForm.value = BLANK_SJ_FORM()
  sjForm.value.show = true
}

async function openEditScriptJob(item) {
  await loadAllScripts()
  sjForm.value = {
    ...BLANK_SJ_FORM(),
    id: item.id, name: item.name, description: item.description,
    steps: (item.steps ?? []).map(s => ({
      script: s.script,
      run_on: s.run_on,
      pipe_to_next: s.pipe_to_next,
      save_output: s.save_output,
      enable_baseline: s.enable_baseline,
      enable_drift: s.enable_drift,
    })),
    is_active: item.is_active,
    show: true,
  }
}

async function saveScriptJob() {
  if (!sjForm.value.name) { alert('Name is required.'); return }
  if (!sjForm.value.steps.length) {
    alert('At least one step is required.')
    return
  }
  if (sjForm.value.steps.some(s => !s.script)) {
    alert('Each step must have a script selected.')
    return
  }
  sjForm.value.saving = true
  try {
    const payload = {
      name: sjForm.value.name,
      description: sjForm.value.description,
      steps: sjForm.value.steps.map((s, i) => ({
        order: i * 10,
        script: s.script,
        run_on: s.run_on,
        pipe_to_next: s.pipe_to_next,
        save_output: s.save_output,
        enable_baseline: s.enable_baseline,
        enable_drift: s.enable_drift,
      })),
      is_active: sjForm.value.is_active,
    }
    if (sjForm.value.id) await api.put(`/scripts/script-jobs/${sjForm.value.id}/`, payload)
    else await api.post('/scripts/script-jobs/', payload)
    sjForm.value.show = false
    await loadScriptJobs()
  } finally {
    sjForm.value.saving = false
  }
}

async function removeScriptJob(id) {
  if (!await askConfirm('Delete this Script Job?')) return
  await api.delete(`/scripts/script-jobs/${id}/`)
  await loadScriptJobs()
}



// Results + output
const sjResultsDialog = ref({ show: false, job: null, loading: false, results: [] })
const sjOutputDialog  = ref({ show: false, result: null })

async function openScriptJobResults(item) {
  sjResultsDialog.value = { show: true, job: item, loading: false, results: [] }
  await loadScriptJobResults()
}
async function loadScriptJobResults() {
  if (!sjResultsDialog.value.job) return
  sjResultsDialog.value.loading = true
  try {
    const res = await api.get(`/scripts/script-jobs/${sjResultsDialog.value.job.id}/results/`)
    sjResultsDialog.value.results = res.data?.results ?? res.data ?? []
  } finally {
    sjResultsDialog.value.loading = false
  }
}
function viewScriptJobOutput(item) { sjOutputDialog.value = { show: true, result: item } }

// ── init ─────────────────────────────────────────────────────────────────────
onMounted(() => {
  loadScriptJobs()
  loadAllScripts()
})
</script>

<style scoped>
</style>
