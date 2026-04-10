<template>
  <div>
    <div class="d-flex align-center mb-4">
      <div class="text-h5 font-weight-bold">Devices</div>
      <v-spacer />
      <v-btn variant="tonal" prepend-icon="mdi-help-circle-outline" @click="showHelp = true">How it works</v-btn>
    </div>

    <!-- ── Help dialog ───────────────────────────────────────────────────── -->
    <v-dialog v-model="showHelp" max-width="720" scrollable>
      <v-card rounded="lg">
        <v-card-title class="d-flex align-center pt-4 pb-2">
          <v-icon icon="mdi-server-network" class="mr-2" color="primary" />
          Devices &amp; Credentials
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" @click="showHelp = false" />
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-5" style="font-size:0.92rem;line-height:1.7">

          <p class="mb-3">
            A <strong>Device</strong> is any host, appliance, or network node that IsotopeIQ Satellite will
            collect configuration data from. Devices are the foundational inventory — everything else
            (Policies, Jobs, Baselines, Drift) is anchored to one or more devices.
          </p>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">How collection works</div>
          <p class="mb-3">
            When a Policy runs, Satellite connects to each assigned device, executes the Script Job's
            steps in order, then stores the parsed canonical JSON result. The result is compared
            against the device's baseline to detect drift.
          </p>
          <p class="mb-3">
            Five connection types are supported:
          </p>
          <v-table density="compact" class="mb-3 rounded-lg" style="border:1px solid rgba(0,0,0,.12)">
            <tbody>
              <tr>
                <td class="font-weight-medium" style="width:30%">SSH</td>
                <td>Satellite opens an SSH session and runs scripts remotely. Requires a username/password or private key credential.</td>
              </tr>
              <tr>
                <td class="font-weight-medium">Telnet</td>
                <td>For legacy devices that only support Telnet. Supports interactive command sequences defined in the collection script.</td>
              </tr>
              <tr>
                <td class="font-weight-medium">WinRM</td>
                <td>Windows Remote Management — remote script execution on Windows devices. Requires a username/password credential.</td>
              </tr>
              <tr>
                <td class="font-weight-medium">HTTPS / API</td>
                <td>Satellite sends HTTP requests to a REST API. Useful for network devices, hypervisors, or cloud endpoints. Typically uses an API token credential.</td>
              </tr>
              <tr>
                <td class="font-weight-medium">Agent Pull</td>
                <td>An IsotopeIQ agent runs persistently on the device and listens on TCP port 9322.
                  Satellite calls <code>GET /collect</code> on demand — no credentials or scripts needed.
                  Download the agent installer from <router-link to="/agent-download">Download Agent</router-link>.</td>
              </tr>
            </tbody>
          </v-table>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">Credentials</div>
          <p class="mb-3">
            Credentials are stored separately from devices and encrypted at rest. A single credential record
            can be shared across many devices (e.g. a domain service account). Supported types:
          </p>
          <v-table density="compact" class="mb-3 rounded-lg" style="border:1px solid rgba(0,0,0,.12)">
            <tbody>
              <tr><td class="font-weight-medium" style="width:30%">Username / Password</td><td>Used for SSH (password auth), Telnet, and WinRM.</td></tr>
              <tr><td class="font-weight-medium">Username / Private Key</td><td>PEM private key for SSH key-based authentication. Recommended for Linux/Unix.</td></tr>
              <tr><td class="font-weight-medium">API Token</td><td>Bearer token for HTTPS-based collection (network devices, REST APIs).</td></tr>
            </tbody>
          </v-table>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">Device fields</div>
          <v-table density="compact" class="mb-3 rounded-lg" style="border:1px solid rgba(0,0,0,.12)">
            <tbody>
              <tr><td class="font-weight-medium" style="width:30%">Name</td><td>Human-readable label used throughout the UI.</td></tr>
              <tr><td class="font-weight-medium">Hostname / FQDN</td><td>Used as the connection target. FQDN is preferred where DNS is available.</td></tr>
              <tr><td class="font-weight-medium">Connection Type</td><td>SSH, Telnet, WinRM, HTTPS/API, or Agent Pull. Determines which transport Satellite uses.</td></tr>
              <tr><td class="font-weight-medium">Port</td><td>Connection port. Defaults to the standard port for each connection type (22 for SSH, 5985 for WinRM, 9322 for Agent).</td></tr>
              <tr><td class="font-weight-medium">Credential</td><td>Link to a Credential record. Leave blank for Agent Pull devices.</td></tr>
              <tr><td class="font-weight-medium">Agent Port</td><td>TCP port the IsotopeIQ agent is listening on (default: 9322). Only applies to Agent Pull devices.</td></tr>
              <tr><td class="font-weight-medium">Tags</td><td>Comma-separated labels for grouping and filtering devices (e.g. <code>prod, linux, db</code>). Used to filter the device list and narrow selections in the policy editor.</td></tr>
              <tr><td class="font-weight-medium">Notes</td><td>Free-text notes visible in the device detail panel.</td></tr>
              <tr><td class="font-weight-medium">Active</td><td>Inactive devices are excluded from scheduled policy runs but can still be targeted manually.</td></tr>
            </tbody>
          </v-table>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">Typical setup flow</div>
          <ol class="pl-4" style="line-height:2">
            <li>Create a <strong>Credential</strong> (Credentials tab) for the account Satellite will use.</li>
            <li>Add one or more <strong>Devices</strong>, selecting the connection type and credential.</li>
            <li>Use <strong>Test Connection</strong> to verify reachability and cache the SSH host key.</li>
            <li>Create a <strong>Script Job</strong> (Scripts page) with the collection and parser steps for your target OS.</li>
            <li>Create a <strong>Policy</strong> that assigns the Script Job and target devices to a schedule.</li>
            <li>Run the policy — results appear in <strong>Job Monitor</strong> and baselines are captured on first run.</li>
            <li>Subsequent runs produce <strong>Drift</strong> reports comparing against the baseline.</li>
          </ol>

        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-3">
          <v-spacer />
          <v-btn color="primary" variant="tonal" @click="showHelp = false">Got it</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <v-tabs v-model="activeTab" color="primary" class="mb-4">
      <v-tab value="devices">Devices</v-tab>
      <v-tab value="credentials">Credentials</v-tab>
    </v-tabs>

    <!-- ── DEVICES TAB ──────────────────────────────────────────────────── -->
    <v-window v-model="activeTab">
      <v-window-item value="devices">

        <!-- Filter bar -->
        <v-card elevation="1" rounded="lg" class="mb-4 pa-4">
          <v-row dense align="center">
            <v-col cols="12" sm="4">
              <v-text-field v-model="deviceSearch" label="Search" placeholder="name, hostname, FQDN…" prepend-inner-icon="mdi-magnify" clearable @keyup.enter="applyDeviceFilters" @click:clear="clearDeviceFilters" />
            </v-col>
            <v-col cols="6" sm="2">
              <v-select v-model="deviceConnType" label="Connection" :items="connItems" @update:modelValue="applyDeviceFilters" />
            </v-col>
            <v-col cols="6" sm="2">
              <v-select v-model="deviceActive" label="Active" :items="activeItems" @update:modelValue="applyDeviceFilters" />
            </v-col>
            <v-col cols="6" sm="2">
              <v-select v-model="deviceTag" label="Tag" :items="[{ title: 'All', value: '' }, ...allTags.map(t => ({ title: t, value: t }))]" @update:modelValue="applyDeviceFilters" />
            </v-col>
            <v-col cols="6" sm="2" class="d-flex ga-2 justify-end align-center">
              <v-btn @click="clearDeviceFilters" variant="outlined">Clear</v-btn>
              <v-btn color="primary" prepend-icon="mdi-plus" @click="openNewDevice">Add Device</v-btn>
            </v-col>
          </v-row>
        </v-card>

        <!-- Snackbar for test/collect result -->
        <v-snackbar v-model="snackbar.show" :color="snackbar.ok ? 'success' : 'error'" timeout="6000" location="bottom right">
          {{ snackbar.msg }}
        </v-snackbar>

        <v-data-table-server
            v-model:options="tableOptions"
            :headers="deviceHeaders"
            :items="devStore.devices"
            :items-length="devStore.totalCount"
            :loading="devStore.loading"
            :items-per-page-options="[25, 50, 100]"
            density="compact"
            rounded="lg"
            elevation="1"
            hover
            @click:row="(_, { item }) => openViewer(item)"
            @update:options="onTableOptions"
          >
            <template #item.is_active="{ item }">
              <v-chip :color="item.is_active ? 'success' : 'default'" size="x-small" label>{{ item.is_active ? 'Yes' : 'No' }}</v-chip>
            </template>
            <template #item.tags="{ item }">
              <v-chip
                v-for="tag in item.tags"
                :key="tag"
                size="x-small"
                label
                class="mr-1"
                @click.stop="deviceTag = tag; applyDeviceFilters()"
              >{{ tag }}</v-chip>
            </template>
            <template #item.credential="{ item }">{{ credName(item.credential) }}</template>
            <template #item.actions="{ item }">
              <div class="d-flex ga-1" @click.stop>
                <v-btn size="x-small" variant="tonal" color="primary" :loading="collecting === item.id" @click="collect(item)">Run</v-btn>
                <v-btn size="x-small" variant="tonal" color="secondary" @click="triggerImport(item)">Import</v-btn>
                <v-btn size="x-small" variant="tonal" @click="openEditDevice(item)">Edit</v-btn>
                <v-btn size="x-small" variant="tonal" color="error" @click="removeDevice(item.id)">Delete</v-btn>
              </div>
            </template>
          </v-data-table-server>

        <!-- Device form dialog -->
        <v-dialog v-model="deviceForm.show" max-width="700" scrollable>
          <v-card rounded="lg">
            <v-card-title>{{ deviceForm.id ? 'Edit' : 'Add' }} Device</v-card-title>
            <v-card-text>
              <v-row dense>
                <v-col cols="12" sm="6"><v-text-field v-model="deviceForm.name" label="Name *" /></v-col>
                <v-col cols="12" sm="6"><v-text-field v-model="deviceForm.hostname" label="Hostname / IP / FQDN *" /></v-col>
                <v-col cols="12" sm="6">
                  <v-select v-model="deviceForm.connection_type" label="Connection Type" :items="connTypeItems" @update:modelValue="onConnectionTypeChange" />
                </v-col>
                <v-col cols="12" sm="6"><v-text-field v-model.number="deviceForm.port" label="Port" type="number" :placeholder="String(defaultPort(deviceForm.connection_type))" /></v-col>
                <v-col cols="12" sm="12">
                  <div class="d-flex align-center ga-2">
                    <v-select v-model="deviceForm.credential" label="Credential" :items="credentialItems" clearable class="flex-grow-1" />
                    <v-btn icon="mdi-plus" size="small" variant="tonal" color="primary" title="Add new credential" @click="openNewCredFromDevice" />
                  </div>
                </v-col>
                <template v-if="deviceForm.connection_type === 'agent'">
                  <v-col cols="12" sm="6">
                    <v-text-field v-model.number="deviceForm.agent_port" label="Agent Port" type="number" placeholder="9322" hint="TCP port the agent is listening on" persistent-hint />
                  </v-col>
                  <v-col cols="12" sm="6" class="d-flex align-center">
                    <v-alert density="compact" variant="tonal" color="info" rounded="lg" icon="mdi-information-outline" class="text-body-2 w-100">
                      Download the agent installer from
                      <router-link to="/agent-download" @click="deviceForm.show = false">Download Agent</router-link>.
                    </v-alert>
                  </v-col>
                </template>
              </v-row>

              <v-text-field v-model="deviceForm.tagsRaw" label="Tags (comma-separated)" placeholder="prod, linux, web" class="mt-3" />
              <v-textarea v-model="deviceForm.notes" label="Notes" rows="2" class="mt-1" />
              <v-checkbox v-model="deviceForm.is_active" label="Active" density="compact" hide-details />

              <v-alert v-if="deviceForm.error" type="error" variant="tonal" density="compact" class="mt-3">{{ deviceForm.error }}</v-alert>

              <v-alert v-if="deviceForm.testResult" :type="deviceForm.testResult.ok ? 'success' : 'error'" variant="tonal" density="compact" class="mt-3">
                <div class="font-weight-bold">{{ deviceForm.testResult.ok ? 'Connection successful' : 'Connection failed' }}</div>
                <pre v-if="deviceForm.testResult.detail" class="mt-1" style="background:transparent;padding:0;font-size:.82rem;white-space:pre-wrap;word-break:break-word">{{ deviceForm.testResult.detail }}</pre>
              </v-alert>
            </v-card-text>
            <v-card-actions>
              <v-btn
                variant="tonal"
                :loading="deviceForm.testing"
                :disabled="!deviceForm.hostname || !canTestConnection(deviceForm.connection_type)"
                @click="testConnInModal"
              >Test Connection</v-btn>
              <v-spacer />
              <v-btn @click="deviceForm.show = false">Cancel</v-btn>
              <v-btn color="primary" @click="saveDevice">Save</v-btn>
            </v-card-actions>
          </v-card>
        </v-dialog>

        <!-- Run dialog: policy or script job picker -->
        <v-dialog v-model="collectDialog.show" max-width="480">
          <v-card rounded="lg">
            <v-card-title class="d-flex align-center pt-4 pb-2">
              Run — {{ collectDialog.device?.name }}
            </v-card-title>
            <v-divider />
            <v-card-text>
              <div v-if="collectDialog.loading" class="text-medium-emphasis py-4 text-center">Loading…</div>
              <template v-else>
                <!-- Mode toggle -->
                <v-btn-toggle v-model="collectDialog.mode" mandatory density="compact" class="mb-4 w-100" style="width:100%">
                  <v-btn value="policy" style="flex:1">Policy</v-btn>
                  <v-btn value="scriptjob" style="flex:1">Script Job</v-btn>
                </v-btn-toggle>

                <!-- Policy list -->
                <template v-if="collectDialog.mode === 'policy'">
                  <template v-if="collectDialog.policies.length === 0">
                    <v-alert type="warning" variant="tonal" density="compact" icon="mdi-alert-circle-outline">
                      <div class="font-weight-medium mb-1">No active policies assigned to this device.</div>
                      <div class="text-body-2">Create or edit a Policy and add this device to it.</div>
                    </v-alert>
                    <v-btn variant="tonal" color="primary" class="mt-3" prepend-icon="mdi-shield-check-outline" to="/policies" @click="collectDialog.show = false">Go to Policies</v-btn>
                  </template>
                  <v-radio-group v-else v-model="collectDialog.policyId" hide-details>
                    <v-radio v-for="p in collectDialog.policies" :key="p.id" :label="p.name" :value="p.id" />
                  </v-radio-group>
                </template>

                <!-- Script Job list -->
                <template v-else>
                  <template v-if="collectDialog.scriptJobs.length === 0">
                    <v-alert type="warning" variant="tonal" density="compact" icon="mdi-alert-circle-outline">
                      <div class="font-weight-medium mb-1">No active script jobs found.</div>
                      <div class="text-body-2">Create a Script Job on the Scripts page first.</div>
                    </v-alert>
                    <v-btn variant="tonal" color="primary" class="mt-3" prepend-icon="mdi-script-text-outline" to="/scripts" @click="collectDialog.show = false">Go to Scripts</v-btn>
                  </template>
                  <v-radio-group v-else v-model="collectDialog.scriptJobId" hide-details>
                    <v-radio v-for="sj in collectDialog.scriptJobs" :key="sj.id" :value="sj.id">
                      <template #label>
                        <div>
                          <div>{{ sj.name }}</div>
                          <div class="text-caption text-medium-emphasis">{{ sj.description }}</div>
                        </div>
                      </template>
                    </v-radio>
                  </v-radio-group>
                </template>

                <v-alert v-if="collectDialog.error" type="error" variant="tonal" density="compact" class="mt-3">{{ collectDialog.error }}</v-alert>
              </template>
            </v-card-text>
            <v-divider />
            <v-card-actions class="pa-3">
              <v-spacer />
              <v-btn @click="collectDialog.show = false">Cancel</v-btn>
              <v-btn
                color="primary"
                variant="tonal"
                :loading="collectDialog.running"
                :disabled="collectDialog.mode === 'policy' ? !collectDialog.policyId : !collectDialog.scriptJobId"
                @click="submitCollect"
              >Run</v-btn>
            </v-card-actions>
          </v-card>
        </v-dialog>

        <!-- Hidden file input for baseline import -->
        <input ref="importFileInput" type="file" accept=".json,application/json" style="display:none" @change="onImportFileSelected" />

        <!-- Import baseline confirm dialog -->
        <v-dialog v-model="importDialog.show" max-width="480">
          <v-card rounded="lg">
            <v-card-title class="d-flex align-center pt-4">
              <v-icon icon="mdi-file-import-outline" class="mr-2" color="secondary" />
              Import Baseline — {{ importDialog.device?.name }}
            </v-card-title>
            <v-card-text>
              <div v-if="importDialog.parsed" class="mb-3">
                <v-alert type="info" variant="tonal" density="compact">
                  <strong>{{ importDialog.filename }}</strong> loaded successfully.
                  <span v-if="importDialog.parsed.device?.hostname"> Device: <strong>{{ importDialog.parsed.device.hostname }}</strong>.</span>
                </v-alert>
              </div>
              <p class="text-body-2 text-medium-emphasis">
                This will update the baseline for <strong>{{ importDialog.device?.name }}</strong> and run
                drift detection against the previous baseline. This action is logged.
              </p>
              <v-alert v-if="importDialog.error" type="error" variant="tonal" density="compact" class="mt-3">{{ importDialog.error }}</v-alert>
            </v-card-text>
            <v-card-actions>
              <v-spacer />
              <v-btn @click="importDialog.show = false">Cancel</v-btn>
              <v-btn color="secondary" :loading="importDialog.running" @click="submitImport">Import</v-btn>
            </v-card-actions>
          </v-card>
        </v-dialog>

        <!-- Device viewer dialog -->
        <v-dialog v-model="viewerOpen" max-width="1200" scrollable>
          <v-card v-if="viewer.device" rounded="lg">
            <v-card-title>
              {{ viewer.device.name }}
              <div class="text-caption text-medium-emphasis font-weight-regular">{{ viewer.device.hostname }} · {{ viewer.device.device_type }} · {{ viewer.device.os_type }}</div>
            </v-card-title>
            <v-tabs v-model="viewer.tab" color="primary" density="compact" class="border-b">
              <v-tab value="info">Info</v-tab>
              <v-tab value="baseline" @click="loadBaseline">Baseline</v-tab>
            </v-tabs>
            <v-card-text>
              <v-window v-model="viewer.tab">
                <v-window-item value="info">
                  <v-table density="compact">
                    <tbody>
                      <tr v-for="row in infoRows(viewer.device)" :key="row.label">
                        <td class="font-weight-medium text-no-wrap pr-6" style="width:160px">{{ row.label }}</td>
                        <td>{{ row.value }}</td>
                      </tr>
                    </tbody>
                  </v-table>
                </v-window-item>
                <v-window-item value="baseline">
                  <div v-if="viewer.baselineLoading" class="pa-4 text-medium-emphasis">Loading baseline…</div>
                  <div v-else-if="!viewer.baseline" class="pa-4 text-medium-emphasis">No baseline established yet. Run a policy against this device first.</div>
                  <div v-else>
                    <p class="text-caption text-medium-emphasis mb-3">Established {{ fmt(viewer.baseline.established_at) }} by {{ viewer.baseline.established_by }}</p>
                    <CanonicalViewer :data="viewer.baseline.parsed_data" />
                  </div>
                </v-window-item>
              </v-window>
            </v-card-text>
            <v-card-actions>
              <v-spacer />
              <v-btn @click="viewerOpen = false">Close</v-btn>
            </v-card-actions>
          </v-card>
        </v-dialog>
      </v-window-item>

      <!-- ── CREDENTIALS TAB ──────────────────────────────────────────── -->
      <v-window-item value="credentials">
        <div class="d-flex justify-end mb-3">
          <v-btn color="primary" prepend-icon="mdi-plus" @click="openNewCred">Add Credential</v-btn>
        </div>

        <v-card elevation="1" rounded="lg">
          <v-data-table-server
            v-model:options="credTableOptions"
            :headers="credHeaders"
            :items="credentials"
            :items-length="totalCredentials"
            :loading="credLoading"
            @update:options="onCredTableOptions"
          >
            <template #item.actions="{ item }">
              <div class="d-flex ga-1">
                <v-btn size="x-small" variant="tonal" icon="mdi-pencil" @click="openEditCred(item)" />
                <v-btn size="x-small" color="error" variant="tonal" icon="mdi-delete" @click="removeCred(item.id)" />
              </div>
            </template>
          </v-data-table-server>
        </v-card>

      </v-window-item>
    </v-window>
    <!-- Credential dialog -->
    <v-dialog v-model="credForm.show" max-width="480" scrollable>
      <v-card rounded="lg">
        <v-card-title>{{ credForm.id ? 'Edit' : 'Add' }} Credential</v-card-title>
        <v-card-text>
          <v-text-field v-model="credForm.name" label="Name *" class="mb-2" data-lpignore="true" />
          <v-select v-model="credForm.credential_type" label="Type" :items="credTypeItems" class="mb-2" />
          <v-text-field v-if="credForm.credential_type !== 'api_token'" v-model="credForm.username" label="Username" class="mb-2" autocomplete="off" data-lpignore="true" />
          <v-text-field v-if="credForm.credential_type === 'password'" v-model="credForm.password" label="Password" type="password" autocomplete="new-password" placeholder="leave blank to keep existing" class="mb-2" data-lpignore="true" />
          <v-textarea v-if="credForm.credential_type === 'private_key'" v-model="credForm.private_key" label="Private Key (PEM)" rows="8" style="font-family:monospace;font-size:.82rem" placeholder="-----BEGIN ... PRIVATE KEY-----&#10;...&#10;-----END ... PRIVATE KEY-----" class="mb-2" />
          <v-text-field v-if="credForm.credential_type === 'api_token'" v-model="credForm.token" label="Token" type="password" autocomplete="new-password" placeholder="leave blank to keep existing" class="mb-2" data-lpignore="true" />
          <v-textarea v-model="credForm.notes" label="Notes" rows="2" />
          <v-alert v-if="credForm.error" type="error" variant="tonal" density="compact" class="mt-3">{{ credForm.error }}</v-alert>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="credForm.show = false">Cancel</v-btn>
          <v-btn color="primary" @click="saveCred">Save</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
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
import { ref, computed, onMounted } from 'vue'
import { useDevicesStore } from '../stores/devices'
import api from '../api'
import CanonicalViewer from '../components/CanonicalViewer.vue'

const confirmDialog = ref({ open: false, message: '', resolve: () => {} })
function askConfirm(message) {
  return new Promise(resolve => {
    confirmDialog.value = { open: true, message, resolve: (val) => { confirmDialog.value.open = false; resolve(val) } }
  })
}

const devStore = useDevicesStore()

// ── help dialog ─────────────────────────────────────────────────────────────
const showHelp = ref(false)

// ── filter state ────────────────────────────────────────────────────────────
const deviceSearch   = ref('')
const deviceConnType = ref('')
const deviceActive   = ref('')
const deviceTag      = ref('')
const allTags        = ref([])

const connItems   = [{ title: 'All', value: '' }, { title: 'SSH', value: 'ssh' }, { title: 'WinRM', value: 'winrm' }, { title: 'Telnet', value: 'telnet' }, { title: 'Agent', value: 'agent' }]
const activeItems = [{ title: 'All', value: '' }, { title: 'Yes', value: 'true' }, { title: 'No', value: 'false' }]

const SORT_FIELD = { name: 'name', created_at: 'created_at' }

const tableOptions = ref({ page: 1, itemsPerPage: 25, sortBy: [] })

function buildDeviceParams(options = tableOptions.value) {
  const params = { page: options.page, page_size: options.itemsPerPage }
  if (deviceSearch.value)   params.search          = deviceSearch.value
  if (deviceConnType.value) params.connection_type  = deviceConnType.value
  if (deviceActive.value)   params.is_active        = deviceActive.value
  if (deviceTag.value)      params.tags             = deviceTag.value
  if (options.sortBy?.length) {
    const { key, order } = options.sortBy[0]
    const field = SORT_FIELD[key] ?? key
    params.ordering = order === 'desc' ? `-${field}` : field
  }
  return params
}

function onTableOptions(options) {
  tableOptions.value = options
  devStore.fetchDevices(buildDeviceParams(options))
}

function resetAndFetchDevices() {
  const opts = { ...tableOptions.value, page: 1 }
  tableOptions.value = opts
  devStore.fetchDevices(buildDeviceParams(opts))
}

function applyDeviceFilters() { resetAndFetchDevices() }
function clearDeviceFilters() {
  deviceSearch.value = ''; deviceConnType.value = ''; deviceActive.value = ''; deviceTag.value = ''
  resetAndFetchDevices()
}

// ── table headers ────────────────────────────────────────────────────────────
const deviceHeaders = [
  { title: 'Name',       key: 'name',            sortable: true  },
  { title: 'Hostname',   key: 'hostname' },
  { title: 'Connection', key: 'connection_type' },
  { title: 'Tags',       key: 'tags',            sortable: false },
  { title: 'Credential', key: 'credential' },
  { title: 'Active',     key: 'is_active' },
  { title: '',           key: 'actions', sortable: false, align: 'end' },
]

const credHeaders = [
  { title: 'Name',     key: 'name' },
  { title: 'Type',     key: 'credential_type' },
  { title: 'Username', key: 'username' },
  { title: 'Notes',    key: 'notes' },
  { title: '',         key: 'actions', sortable: false, align: 'end' },
]

// ── tabs ─────────────────────────────────────────────────────────────────────
const activeTab = ref('devices')

// ── snackbar ─────────────────────────────────────────────────────────────────
const snackbar = ref({ show: false, ok: true, msg: '' })
function showSnack(ok, msg) { snackbar.value = { show: true, ok, msg } }

// ── device viewer ─────────────────────────────────────────────────────────────
const viewerOpen = ref(false)
const viewer     = ref({ device: null, tab: 'info', baseline: null, baselineLoading: false })

function fmt(iso) { return new Date(iso).toLocaleString() }

function infoRows(d) {
  return [
    { label: 'Name',        value: d.name },
    { label: 'Hostname',    value: d.fqdn || d.hostname },
    { label: 'Port',        value: d.port },
    { label: 'Connection',  value: d.connection_type },
    { label: 'Credential',  value: credName(d.credential) },
    ...(d.connection_type === 'agent' ? [{ label: 'Agent Port', value: d.agent_port ?? 9322 }] : []),
    { label: 'Active',      value: d.is_active ? 'Yes' : 'No' },
    ...(d.tags?.length ? [{ label: 'Tags',  value: d.tags.join(', ') }] : []),
    ...(d.notes         ? [{ label: 'Notes', value: d.notes }]          : []),
  ]
}

function openViewer(device) {
  viewer.value = { device, tab: 'info', baseline: null, baselineLoading: false }
  viewerOpen.value = true
}

async function loadBaseline() {
  if (viewer.value.baseline !== null || viewer.value.baselineLoading) return
  viewer.value.baselineLoading = true
  try {
    const { data } = await api.get('/baselines/', { params: { device: viewer.value.device.id } })
    viewer.value.baseline = (data.results ?? data)[0] ?? null
  } finally {
    viewer.value.baselineLoading = false
  }
}

// ── credentials ───────────────────────────────────────────────────────────────
const credentials    = ref([])
const allCredentials = ref([])
const credLoading    = ref(false)
const totalCredentials = ref(0)
const credTableOptions = ref({ page: 1, itemsPerPage: 20, sortBy: [] })

const credentialItems = computed(() => [
  { title: '— none —', value: null },
  ...allCredentials.value.map(c => ({ title: `${c.name} (${c.credential_type})`, value: c.id })),
])

const credTypeItems = [
  { title: 'Username / Password', value: 'password' },
  { title: 'Username / Private Key', value: 'private_key' },
  { title: 'API Token', value: 'api_token' },
]

async function loadAllCredentials() {
  const { data } = await api.get('/devices/credentials/', { params: { page_size: 500 } })
  allCredentials.value = data.results ?? data
}

async function loadCredentials(options = credTableOptions.value) {
  credLoading.value = true
  try {
    const params = { page: options.page, page_size: options.itemsPerPage }
    if (options.sortBy?.length) {
      const { key, order } = options.sortBy[0]
      params.ordering = order === 'desc' ? `-${key}` : key
    }
    const { data } = await api.get('/devices/credentials/', { params })
    credentials.value = data.results ?? data
    totalCredentials.value = data.count ?? credentials.value.length
  } finally {
    credLoading.value = false
  }
}

function onCredTableOptions(options) {
  credTableOptions.value = options
  loadCredentials(options)
}

function credName(credId) {
  if (!credId) return '—'
  const c = allCredentials.value.find(c => c.id === credId)
  return c ? c.name : `#${credId}`
}

const afterCredSave = ref(null)

const credForm = ref(blankCred())
function blankCred() {
  return { show: false, id: null, name: '', credential_type: 'password', username: '', password: '', private_key: '', token: '', notes: '', error: '' }
}
function openNewCred()  { afterCredSave.value = null; credForm.value = { ...blankCred(), show: true } }
function openNewCredFromDevice() {
  afterCredSave.value = (newCred) => { deviceForm.value.credential = newCred.id }
  credForm.value = { ...blankCred(), show: true }
}
function openEditCred(c) {
  credForm.value = { ...blankCred(), show: true, id: c.id, name: c.name, credential_type: c.credential_type, username: c.username || '', notes: c.notes || '' }
}

async function saveCred() {
  credForm.value.error = ''
  const payload = { name: credForm.value.name, credential_type: credForm.value.credential_type, username: credForm.value.username, notes: credForm.value.notes }
  if (credForm.value.password)    payload.password    = credForm.value.password
  if (credForm.value.private_key) payload.private_key = credForm.value.private_key
  if (credForm.value.token)       payload.token       = credForm.value.token
  try {
    if (credForm.value.id) {
      await api.patch(`/devices/credentials/${credForm.value.id}/`, payload)
    } else {
      const { data } = await api.post('/devices/credentials/', payload)
      if (afterCredSave.value) { afterCredSave.value(data); afterCredSave.value = null }
    }
    credForm.value.show = false
    loadCredentials()
    loadAllCredentials()
  } catch (e) {
    credForm.value.error = JSON.stringify(e.response?.data ?? 'Save failed.')
  }
}

async function removeCred(id) {
  if (!await askConfirm('Delete this credential?')) return
  await api.delete(`/devices/credentials/${id}/`)
  loadCredentials()
  loadAllCredentials()
}

// ── devices ───────────────────────────────────────────────────────────────────
const testing   = ref(null)
const collecting = ref(null)

const DEFAULT_PORTS = { ssh: 22, telnet: 23, winrm: 5985, https: 443, agent: 9322 }
const TESTABLE_TYPES = new Set(['ssh', 'telnet', 'winrm', 'agent'])
function canTestConnection(type) { return TESTABLE_TYPES.has(type) }
function defaultPort(t) { return DEFAULT_PORTS[t] ?? '' }

const connTypeItems = [
  { title: 'SSH',                  value: 'ssh' },
  { title: 'Telnet',               value: 'telnet' },
  { title: 'WinRM',                value: 'winrm' },
  { title: 'HTTPS / API',          value: 'https' },
  { title: 'Agent Pull (port 9322)', value: 'agent' },
]

function onConnectionTypeChange() {
  const def = DEFAULT_PORTS[deviceForm.value.connection_type]
  if (def) deviceForm.value.port = def
}

const deviceForm = ref(blankDevice())
function blankDevice() {
  return { show: false, id: null, name: '', hostname: '', port: 22, connection_type: 'ssh', credential: null, agent_port: 9322, tagsRaw: '', notes: '', is_active: true, error: '', testing: false, testResult: null }
}
function openNewDevice()  { deviceForm.value = { ...blankDevice(), show: true } }
function openEditDevice(d) {
  deviceForm.value = { ...blankDevice(), show: true, id: d.id, name: d.name, hostname: d.fqdn || d.hostname, port: d.port, connection_type: d.connection_type, credential: d.credential ?? null, agent_port: d.agent_port ?? 9322, tagsRaw: (d.tags ?? []).join(', '), notes: d.notes || '', is_active: d.is_active }
}

async function saveDevice() {
  deviceForm.value.error = ''
  const payload = { name: deviceForm.value.name, hostname: deviceForm.value.hostname, fqdn: deviceForm.value.hostname, port: deviceForm.value.port, connection_type: deviceForm.value.connection_type, credential: deviceForm.value.credential, tags: deviceForm.value.tagsRaw.split(',').map(t => t.trim()).filter(Boolean), notes: deviceForm.value.notes, is_active: deviceForm.value.is_active }
  if (deviceForm.value.connection_type === 'agent') {
    payload.agent_port = deviceForm.value.agent_port || 9322
  }
  try {
    if (deviceForm.value.id) {
      await devStore.updateDevice(deviceForm.value.id, payload)
      deviceForm.value.show = false
    } else {
      await devStore.createDevice(payload)
      deviceForm.value.show = false
    }
    loadAllTags()
  } catch (e) {
    deviceForm.value.error = JSON.stringify(e.response?.data ?? 'Save failed.')
  }
}

async function removeDevice(id) {
  if (await askConfirm('Delete this device?')) await devStore.deleteDevice(id)
}

// ── run dialog (policy or script job) ─────────────────────────────────────
const collectDialog = ref({
  show: false, device: null, mode: 'policy',
  policies: [], policyId: null,
  scriptJobs: [], scriptJobId: null,
  loading: false, running: false, error: '',
})

async function collect(device) {
  collecting.value = device.id
  collectDialog.value = {
    show: false, device, mode: 'policy',
    policies: [], policyId: null,
    scriptJobs: [], scriptJobId: null,
    loading: true, running: false, error: '',
  }
  try {
    const [polRes, sjRes] = await Promise.all([
      api.get('/policies/', { params: { devices: device.id, is_active: true, page_size: 500 } }),
      api.get('/scripts/script-jobs/', { params: { is_active: true, page_size: 500 } }),
    ])
    const policies   = polRes.data.results ?? polRes.data
    const scriptJobs = sjRes.data.results  ?? sjRes.data
    collectDialog.value.policies    = policies
    collectDialog.value.policyId    = policies[0]?.id ?? null
    collectDialog.value.scriptJobs  = scriptJobs
    collectDialog.value.scriptJobId = scriptJobs[0]?.id ?? null
    collectDialog.value.loading = false
    collectDialog.value.show = true
  } catch (e) {
    console.error('[collect] error:', e)
    showSnack(false, `✗ ${device?.name ?? 'Device'}: Failed to load options.`)
  } finally {
    collecting.value = null
  }
}

async function submitCollect() {
  collectDialog.value.running = true
  collectDialog.value.error = ''
  const { device, mode, policyId, scriptJobId } = collectDialog.value
  collecting.value = device.id
  try {
    if (mode === 'policy') {
      const { data } = await api.post(`/devices/${device.id}/collect/`, { policy_id: policyId })
      showSnack(true, `✓ ${device.name}: ${data.detail}`)
    } else {
      await api.post(`/scripts/script-jobs/${scriptJobId}/run/`, { device_id: device.id })
      showSnack(true, `✓ ${device.name}: Script job started.`)
    }
    collectDialog.value.show = false
  } catch (e) {
    collectDialog.value.error = e.response?.data?.detail ?? 'Failed to start run.'
  } finally {
    collecting.value = null
    collectDialog.value.running = false
  }
}

async function testConn(device) {
  testing.value = device.id
  try {
    const { data } = await api.post(`/devices/${device.id}/test-connection/`)
    showSnack(true, `✓ ${device.name}: ${data.detail}`)
  } catch (e) {
    showSnack(false, `✗ ${device.name}: ${e.response?.data?.detail ?? 'Connection failed.'}`)
  } finally {
    testing.value = null
  }
}

async function testConnInModal() {
  deviceForm.value.testing = true
  deviceForm.value.testResult = null
  try {
    let data
    if (deviceForm.value.id) {
      ;({ data } = await api.post(`/devices/${deviceForm.value.id}/test-connection/`))
    } else {
      ;({ data } = await api.post('/devices/test-connection/', { connection_type: deviceForm.value.connection_type, hostname: deviceForm.value.hostname, port: deviceForm.value.connection_type === 'agent' ? (deviceForm.value.agent_port || 9322) : deviceForm.value.port, credential: deviceForm.value.credential }))
    }
    deviceForm.value.testResult = { ok: true, detail: data.detail }
  } catch (e) {
    const resp = e.response?.data
    const detail = resp?.detail ?? resp?.error ?? JSON.stringify(resp) ?? 'Connection failed.'
    const tb = resp?.traceback ?? null
    deviceForm.value.testResult = { ok: false, detail: tb ? `${detail}\n\n${tb}` : detail }
  } finally {
    deviceForm.value.testing = false
  }
}

// ── import baseline ────────────────────────────────────────────────────────
const importFileInput = ref(null)
const importDialog = ref({ show: false, device: null, filename: '', parsed: null, running: false, error: '' })

function triggerImport(device) {
  importDialog.value = { show: false, device, filename: '', parsed: null, running: false, error: '' }
  importFileInput.value.value = ''
  importFileInput.value.click()
}

function onImportFileSelected(event) {
  const file = event.target.files?.[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const parsed = JSON.parse(e.target.result)
      importDialog.value.filename = file.name
      importDialog.value.parsed = parsed
      importDialog.value.error = ''
      importDialog.value.show = true
    } catch {
      showSnack(false, 'Could not parse file — make sure it is a valid JSON baseline.')
    }
  }
  reader.readAsText(file)
}

async function submitImport() {
  importDialog.value.running = true
  importDialog.value.error = ''
  try {
    const { data } = await api.post('/baselines/import/', {
      device_id: importDialog.value.device.id,
      canonical_data: importDialog.value.parsed,
    })
    importDialog.value.show = false
    const msg = data.created
      ? `✓ Baseline imported for ${importDialog.value.device.name}.`
      : `✓ Baseline updated for ${importDialog.value.device.name}. ${data.drift_changes} change(s) detected.`
    showSnack(true, msg)
  } catch (e) {
    importDialog.value.error = e.response?.data?.error ?? 'Import failed.'
  } finally {
    importDialog.value.running = false
  }
}

async function loadAllTags() {
  const { data } = await api.get('/devices/tags/')
  allTags.value = data
}

onMounted(() => {
  // initial device fetch triggered by @update:options
  loadCredentials()
  loadAllCredentials()
  loadAllTags()
})
</script>
