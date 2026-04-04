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
            When a Policy runs, Satellite connects to each assigned device, executes the
            <strong>Collection Script</strong> remotely, captures the raw output, then pipes it through
            the <strong>Parser Script</strong> to produce a normalised canonical JSON document.
            That document is validated against the canonical schema and stored as the job result.
          </p>
          <p class="mb-3">
            Three collection modes are supported:
          </p>
          <v-table density="compact" class="mb-3 rounded-lg" style="border:1px solid rgba(0,0,0,.12)">
            <tbody>
              <tr>
                <td class="font-weight-medium" style="width:30%">Pull (SSH / WinRM)</td>
                <td>Satellite initiates the connection and runs the script. Requires credentials.</td>
              </tr>
              <tr>
                <td class="font-weight-medium">Agent Pull (port 9322)</td>
                <td>An IsotopeIQ agent runs persistently on the device and listens on TCP port 9322.
                  Satellite calls <code>GET /collect</code> on demand — no credentials or scripts needed.
                  Use the installer scripts in <code>agents/installers/</code> to set up the agent as a service.</td>
              </tr>
              <tr>
                <td class="font-weight-medium">Push</td>
                <td>The device calls <code>POST /api/push/</code> with its push token and sends the
                  pre-collected JSON directly. Useful for devices behind NAT or firewalls.</td>
              </tr>
            </tbody>
          </v-table>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">Credentials</div>
          <p class="mb-3">
            Credentials are stored separately from devices and encrypted at rest using Fernet symmetric
            encryption. A single credential record can be shared across many devices (e.g. a domain
            service account). Supported types:
          </p>
          <v-table density="compact" class="mb-3 rounded-lg" style="border:1px solid rgba(0,0,0,.12)">
            <tbody>
              <tr><td class="font-weight-medium" style="width:30%">SSH Password</td><td>Username + password for Linux/Unix devices.</td></tr>
              <tr><td class="font-weight-medium">SSH Key</td><td>Username + private key (PEM). Recommended for Linux/Unix.</td></tr>
              <tr><td class="font-weight-medium">Windows / WinRM</td><td>Username + password for Windows devices using WinRM.</td></tr>
              <tr><td class="font-weight-medium">API Token</td><td>Bearer token for HTTPS-based collection (network devices, REST APIs).</td></tr>
            </tbody>
          </v-table>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">Device fields</div>
          <v-table density="compact" class="mb-3 rounded-lg" style="border:1px solid rgba(0,0,0,.12)">
            <tbody>
              <tr><td class="font-weight-medium" style="width:30%">Name</td><td>Human-readable label used throughout the UI.</td></tr>
              <tr><td class="font-weight-medium">Hostname / FQDN</td><td>Used as the connection target. FQDN is preferred where DNS is available.</td></tr>
              <tr><td class="font-weight-medium">OS Type</td><td>Informs script selection and canonical section expectations — set this accurately so parsers can behave correctly.</td></tr>
              <tr><td class="font-weight-medium">Connection Type</td><td>SSH, WinRM, HTTPS, Push, or Agent Pull. Determines which transport Satellite uses.</td></tr>
              <tr><td class="font-weight-medium">Credential</td><td>Link to a Credential record. Leave blank for push or agent devices.</td></tr>
              <tr><td class="font-weight-medium">Push Token</td><td>A secret token the device includes when calling the push endpoint. Generate a strong random value.</td></tr>
              <tr><td class="font-weight-medium">Agent Port</td><td>TCP port the IsotopeIQ agent is listening on (default: 9322). Only applies to Agent Pull devices.</td></tr>
              <tr><td class="font-weight-medium">Agent Token</td><td>Per-device secret generated by IsotopeIQ. Copy it from the device form and pass it to the installer with <code>--token</code>. The agent uses it to authenticate incoming poll requests.</td></tr>
              <tr><td class="font-weight-medium">SSH Host Key</td><td>Stored on first successful connection and pinned thereafter — Satellite will refuse connections if the key changes, alerting you to a potential MITM.</td></tr>
              <tr><td class="font-weight-medium">Tags</td><td>Free-form JSON object for grouping, filtering, or passing context to scripts (e.g. <code>{"env":"prod","role":"db"}</code>).</td></tr>
            </tbody>
          </v-table>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">Typical setup flow</div>
          <ol class="pl-4" style="line-height:2">
            <li>Create a <strong>Credential</strong> (Credentials tab) for the account Satellite will use.</li>
            <li>Add one or more <strong>Devices</strong>, selecting the credential and correct OS type.</li>
            <li>Use <strong>Test Connection</strong> to verify SSH/WinRM reachability and cache the host key.</li>
            <li>Create a <strong>Policy</strong> that assigns these devices to collection and parser scripts on a schedule.</li>
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
            <v-col cols="6" sm="4" class="d-flex ga-2 justify-end">
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
            <template #item.credential="{ item }">{{ credName(item.credential) }}</template>
            <template #item.actions="{ item }">
              <div class="d-flex ga-1" @click.stop>
                <v-btn size="x-small" variant="tonal" color="primary" :loading="collecting === item.id" @click="collect(item)">Collect</v-btn>
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
                <v-col cols="12" sm="6"><v-text-field v-model="deviceForm.hostname" label="Hostname / IP *" /></v-col>
                <v-col cols="12" sm="6"><v-text-field v-model="deviceForm.fqdn" label="FQDN" placeholder="optional" /></v-col>
                <v-col cols="12" sm="6"><v-text-field v-model.number="deviceForm.port" label="Port" type="number" :placeholder="String(defaultPort(deviceForm.connection_type))" /></v-col>
                <v-col cols="12" sm="6">
                  <v-select v-model="deviceForm.connection_type" label="Connection Type" :items="connTypeItems" @update:modelValue="onConnectionTypeChange" />
                </v-col>
                <v-col cols="12" sm="6">
                  <v-select v-model="deviceForm.credential" label="Credential" :items="credentialItems" clearable />
                </v-col>
                <v-col v-if="deviceForm.connection_type === 'ssh'" cols="12">
                  <v-text-field v-model="deviceForm.host_key" label="SSH Host Key (optional)" placeholder="base64 public key — run: ssh-keyscan -t rsa <hostname>" style="font-family:monospace" />
                </v-col>
                <template v-if="deviceForm.connection_type === 'agent'">
                  <v-col cols="12" sm="6">
                    <v-text-field v-model.number="deviceForm.agent_port" label="Agent Port" type="number" placeholder="9322" hint="TCP port the agent is listening on" persistent-hint />
                  </v-col>
                  <v-col cols="12" sm="6" class="d-flex align-center">
                    <v-alert v-if="!deviceForm.id" density="compact" variant="tonal" color="info" rounded="lg" icon="mdi-download" class="text-body-2 w-100">
                      Save the device to generate a token and download the installer bundle.
                    </v-alert>
                    <v-btn v-else variant="tonal" color="primary" prepend-icon="mdi-download" @click="openDownloadDialog({ id: deviceForm.id, name: deviceForm.name, agent_port: deviceForm.agent_port })">
                      Download Agent
                    </v-btn>
                  </v-col>
                </template>
              </v-row>

              <v-expansion-panels class="mt-2" variant="accordion">
                <v-expansion-panel title="Inline credentials (fallback)">
                  <v-expansion-panel-text>
                    <v-row dense>
                      <v-col cols="6"><v-text-field v-model="deviceForm.username" label="Username" autocomplete="off" /></v-col>
                      <v-col cols="6"><v-text-field v-model="deviceForm.password" label="Password" type="password" autocomplete="new-password" /></v-col>
                    </v-row>
                  </v-expansion-panel-text>
                </v-expansion-panel>
              </v-expansion-panels>

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

        <!-- Agent token reveal dialog -->
        <v-dialog v-model="tokenDialog.show" max-width="580" persistent>
          <v-card rounded="lg">
            <v-card-title class="d-flex align-center gap-2">
              <v-icon color="primary">mdi-download</v-icon>
              Install Agent — {{ tokenDialog.deviceName }}
            </v-card-title>
            <v-card-text>
              <p class="text-body-2 mb-4">
                Select your OS, download the bundle (config + installer), extract it, then run the installer.
                The agent binary is fetched automatically from this server.
              </p>

              <v-tabs v-model="tokenDialog.os" density="compact" class="mb-4">
                <v-tab value="windows">Windows</v-tab>
                <v-tab value="linux">Linux</v-tab>
                <v-tab value="macos">macOS</v-tab>
              </v-tabs>

              <v-window v-model="tokenDialog.os">
                <v-window-item value="windows">
                  <v-btn block color="primary" variant="tonal" prepend-icon="mdi-folder-zip"
                    @click="downloadBundle(tokenDialog.deviceId, 'windows')">
                    Download isotopeiq-agent-windows.zip
                  </v-btn>
                  <p class="text-body-2 text-medium-emphasis mt-3 mb-0">
                    Extract the ZIP, then run from an elevated command prompt:
                  </p>
                  <v-text-field
                    model-value="windows_install.bat" readonly variant="outlined" density="compact"
                    style="font-family:monospace" class="mt-2"
                    append-inner-icon="mdi-content-copy"
                    @click:append-inner="() => { copyToClipboard('windows_install.bat'); showSnack(true, 'Copied.') }"
                  />
                </v-window-item>

                <v-window-item value="linux">
                  <v-btn block color="primary" variant="tonal" prepend-icon="mdi-folder-zip"
                    @click="downloadBundle(tokenDialog.deviceId, 'linux')">
                    Download isotopeiq-agent-linux.zip
                  </v-btn>
                  <p class="text-body-2 text-medium-emphasis mt-3 mb-0">
                    Extract the ZIP, then run as root:
                  </p>
                  <v-text-field
                    model-value="sudo bash linux_install.sh" readonly variant="outlined" density="compact"
                    style="font-family:monospace" class="mt-2"
                    append-inner-icon="mdi-content-copy"
                    @click:append-inner="() => { copyToClipboard('sudo bash linux_install.sh'); showSnack(true, 'Copied.') }"
                  />
                </v-window-item>

                <v-window-item value="macos">
                  <v-btn block color="primary" variant="tonal" prepend-icon="mdi-folder-zip"
                    @click="downloadBundle(tokenDialog.deviceId, 'macos')">
                    Download isotopeiq-agent-macos.zip
                  </v-btn>
                  <p class="text-body-2 text-medium-emphasis mt-3 mb-0">
                    Extract the ZIP, then run as root:
                  </p>
                  <v-text-field
                    model-value="sudo bash macos_install.sh" readonly variant="outlined" density="compact"
                    style="font-family:monospace" class="mt-2"
                    append-inner-icon="mdi-content-copy"
                    @click:append-inner="() => { copyToClipboard('sudo bash macos_install.sh'); showSnack(true, 'Copied.') }"
                  />
                </v-window-item>
              </v-window>
            </v-card-text>
            <v-divider />
            <v-card-actions class="pa-3">
              <v-spacer />
              <v-btn color="primary" variant="tonal" @click="tokenDialog.show = false">Done</v-btn>
            </v-card-actions>
          </v-card>
        </v-dialog>

        <!-- Collect: policy picker dialog -->
        <v-dialog v-model="collectDialog.show" max-width="420">
          <v-card rounded="lg">
            <v-card-title>Collect — {{ collectDialog.device?.name }}</v-card-title>
            <v-card-subtitle>Select which policy to run</v-card-subtitle>
            <v-card-text>
              <div v-if="collectDialog.loading" class="text-medium-emphasis py-2">Loading policies…</div>
              <v-radio-group v-else v-model="collectDialog.policyId" hide-details>
                <v-radio
                  v-for="p in collectDialog.policies"
                  :key="p.id"
                  :label="p.name"
                  :value="p.id"
                />
              </v-radio-group>
              <v-alert v-if="collectDialog.error" type="error" variant="tonal" density="compact" class="mt-3">{{ collectDialog.error }}</v-alert>
            </v-card-text>
            <v-card-actions>
              <v-spacer />
              <v-btn @click="collectDialog.show = false">Cancel</v-btn>
              <v-btn color="primary" :disabled="!collectDialog.policyId" :loading="collectDialog.running" @click="submitCollect">Run</v-btn>
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
          <v-data-table
            :headers="credHeaders"
            :items="credentials"
            :loading="credLoading"
            hide-default-footer
          >
            <template #item.actions="{ item }">
              <div class="d-flex ga-1">
                <v-btn size="x-small" variant="tonal" icon="mdi-pencil" @click="openEditCred(item)" />
                <v-btn size="x-small" color="error" variant="tonal" icon="mdi-delete" @click="removeCred(item.id)" />
              </div>
            </template>
          </v-data-table>
        </v-card>

        <!-- Credential dialog -->
        <v-dialog v-model="credForm.show" max-width="480" scrollable>
          <v-card rounded="lg">
            <v-card-title>{{ credForm.id ? 'Edit' : 'Add' }} Credential</v-card-title>
            <v-card-text>
              <v-text-field v-model="credForm.name" label="Name *" class="mb-2" />
              <v-select v-model="credForm.credential_type" label="Type" :items="credTypeItems" class="mb-2" />
              <v-text-field v-if="credForm.credential_type !== 'api_token'" v-model="credForm.username" label="Username" class="mb-2" />
              <v-text-field v-if="credForm.credential_type === 'password'" v-model="credForm.password" label="Password" type="password" autocomplete="new-password" placeholder="leave blank to keep existing" class="mb-2" />
              <v-textarea v-if="credForm.credential_type === 'private_key'" v-model="credForm.private_key" label="Private Key (PEM)" rows="8" style="font-family:monospace;font-size:.82rem" placeholder="-----BEGIN ... PRIVATE KEY-----&#10;...&#10;-----END ... PRIVATE KEY-----" class="mb-2" />
              <v-text-field v-if="credForm.credential_type === 'api_token'" v-model="credForm.token" label="Token" type="password" autocomplete="new-password" placeholder="leave blank to keep existing" class="mb-2" />
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
      </v-window-item>
    </v-window>
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

const connItems   = [{ title: 'All', value: '' }, { title: 'SSH', value: 'ssh' }, { title: 'WinRM', value: 'winrm' }, { title: 'Telnet', value: 'telnet' }, { title: 'Push', value: 'push' }, { title: 'Agent', value: 'agent' }]
const activeItems = [{ title: 'All', value: '' }, { title: 'Yes', value: 'true' }, { title: 'No', value: 'false' }]

const SORT_FIELD = { name: 'name', created_at: 'created_at' }

const tableOptions = ref({ page: 1, itemsPerPage: 25, sortBy: [] })

function buildDeviceParams(options = tableOptions.value) {
  const params = { page: options.page, page_size: options.itemsPerPage }
  if (deviceSearch.value)   params.search          = deviceSearch.value
  if (deviceConnType.value) params.connection_type  = deviceConnType.value
  if (deviceActive.value)   params.is_active        = deviceActive.value
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
  deviceSearch.value = ''; deviceConnType.value = ''; deviceActive.value = ''
  resetAndFetchDevices()
}

// ── table headers ────────────────────────────────────────────────────────────
const deviceHeaders = [
  { title: 'Name',       key: 'name',            sortable: true  },
  { title: 'Hostname',   key: 'hostname' },
  { title: 'Connection', key: 'connection_type' },
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
    { label: 'Hostname',    value: d.hostname },
    { label: 'FQDN',        value: d.fqdn || '—' },
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
const credentials = ref([])
const credLoading = ref(false)

const credentialItems = computed(() => [
  { title: '— none (use inline fields) —', value: null },
  ...credentials.value.map(c => ({ title: `${c.name} (${c.credential_type})`, value: c.id })),
])

const credTypeItems = [
  { title: 'Username / Password', value: 'password' },
  { title: 'Username / Private Key', value: 'private_key' },
  { title: 'API Token', value: 'api_token' },
]

async function loadCredentials() {
  credLoading.value = true
  try {
    const { data } = await api.get('/devices/credentials/', { params: { page_size: 500 } })
    credentials.value = data.results ?? data
  } finally {
    credLoading.value = false
  }
}

function credName(credId) {
  if (!credId) return '—'
  const c = credentials.value.find(c => c.id === credId)
  return c ? c.name : `#${credId}`
}

const credForm = ref(blankCred())
function blankCred() {
  return { show: false, id: null, name: '', credential_type: 'password', username: '', password: '', private_key: '', token: '', notes: '', error: '' }
}
function openNewCred()  { credForm.value = { ...blankCred(), show: true } }
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
      const { data } = await api.patch(`/devices/credentials/${credForm.value.id}/`, payload)
      const idx = credentials.value.findIndex(c => c.id === credForm.value.id)
      if (idx !== -1) credentials.value[idx] = data
    } else {
      const { data } = await api.post('/devices/credentials/', payload)
      credentials.value.push(data)
    }
    credForm.value.show = false
  } catch (e) {
    credForm.value.error = JSON.stringify(e.response?.data ?? 'Save failed.')
  }
}

async function removeCred(id) {
  if (!await askConfirm('Delete this credential?')) return
  await api.delete(`/devices/credentials/${id}/`)
  credentials.value = credentials.value.filter(c => c.id !== id)
}

// ── devices ───────────────────────────────────────────────────────────────────
const testing   = ref(null)
const collecting = ref(null)

const DEFAULT_PORTS = { ssh: 22, telnet: 23, winrm: 5985, https: 443, push: null, agent: 9322 }
const TESTABLE_TYPES = new Set(['ssh', 'telnet', 'winrm', 'agent'])
function canTestConnection(type) { return TESTABLE_TYPES.has(type) }
function defaultPort(t) { return DEFAULT_PORTS[t] ?? '' }

const connTypeItems = [
  { title: 'SSH',                  value: 'ssh' },
  { title: 'Telnet',               value: 'telnet' },
  { title: 'WinRM',                value: 'winrm' },
  { title: 'HTTPS / API',          value: 'https' },
  { title: 'Push',                 value: 'push' },
  { title: 'Agent Pull (port 9322)', value: 'agent' },
]

function onConnectionTypeChange() {
  const def = DEFAULT_PORTS[deviceForm.value.connection_type]
  if (def) deviceForm.value.port = def
}

const deviceForm = ref(blankDevice())
function blankDevice() {
  return { show: false, id: null, name: '', hostname: '', fqdn: '', port: 22, connection_type: 'ssh', credential: null, username: '', password: '', host_key: '', agent_port: 9322, tagsRaw: '', notes: '', is_active: true, error: '', testing: false, testResult: null }
}
function openNewDevice()  { deviceForm.value = { ...blankDevice(), show: true } }
function openEditDevice(d) {
  deviceForm.value = { ...blankDevice(), show: true, id: d.id, name: d.name, hostname: d.hostname, fqdn: d.fqdn || '', port: d.port, connection_type: d.connection_type, credential: d.credential ?? null, host_key: d.host_key || '', agent_port: d.agent_port ?? 9322, tagsRaw: (d.tags ?? []).join(', '), notes: d.notes || '', is_active: d.is_active }
}

async function saveDevice() {
  deviceForm.value.error = ''
  const payload = { name: deviceForm.value.name, hostname: deviceForm.value.hostname, fqdn: deviceForm.value.fqdn, port: deviceForm.value.port, connection_type: deviceForm.value.connection_type, credential: deviceForm.value.credential, host_key: deviceForm.value.host_key, tags: deviceForm.value.tagsRaw.split(',').map(t => t.trim()).filter(Boolean), notes: deviceForm.value.notes, is_active: deviceForm.value.is_active }
  if (deviceForm.value.username) payload.username = deviceForm.value.username
  if (deviceForm.value.password) payload.password = deviceForm.value.password
  if (deviceForm.value.connection_type === 'agent') {
    payload.agent_port = deviceForm.value.agent_port || 9322
  }
  try {
    if (deviceForm.value.id) {
      await devStore.updateDevice(deviceForm.value.id, payload)
      deviceForm.value.show = false
    } else {
      const created = await devStore.createDevice(payload)
      deviceForm.value.show = false
      if (created.connection_type === 'agent') {
        tokenDialog.value = { show: true, deviceId: created.id, deviceName: created.name, port: created.agent_port ?? 9322, os: 'windows' }
      }
    }
  } catch (e) {
    deviceForm.value.error = JSON.stringify(e.response?.data ?? 'Save failed.')
  }
}

// ── agent download dialog ──────────────────────────────────────────────────
const tokenDialog = ref({ show: false, deviceId: null, deviceName: '', port: 9322, os: 'windows' })

function copyToClipboard(text) {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text)
  } else {
    const el = document.createElement('textarea')
    el.value = text
    el.style.position = 'fixed'
    el.style.opacity = '0'
    document.body.appendChild(el)
    el.focus()
    el.select()
    document.execCommand('copy')
    document.body.removeChild(el)
  }
}

async function downloadBundle(deviceId, os, deviceName) {
  try {
    const { data } = await api.get(`/devices/${deviceId}/agent-bundle/`, {
      params: { os },
      responseType: 'blob',
    })
    const name = (deviceName || tokenDialog.value.deviceName || deviceId).replace(/[^\w\-.]/g, '_')
    const url = URL.createObjectURL(data)
    const a = document.createElement('a')
    a.href = url
    a.download = `isotopeiq-agent-${name}-${os}.zip`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch {
    showSnack(false, 'Bundle download failed.')
  }
}

function openDownloadDialog(device) {
  tokenDialog.value = { show: true, deviceId: device.id, deviceName: device.name, port: device.agent_port ?? 9322, os: 'windows' }
}

async function removeDevice(id) {
  if (await askConfirm('Delete this device?')) await devStore.deleteDevice(id)
}

// ── collect dialog ─────────────────────────────────────────────────────────
const collectDialog = ref({ show: false, device: null, policies: [], policyId: null, loading: false, running: false, error: '' })

async function collect(device) {
  // Agent Pull devices: no policy selection — satellite calls the agent directly.
  if (device.connection_type === 'agent') {
    collecting.value = device.id
    try {
      await api.post('/jobs/trigger-agent-pull/', { device_id: device.id })
      showSnack(true, `✓ ${device.name}: Agent pull triggered — check Job Monitor for results.`)
    } catch (e) {
      showSnack(false, `✗ ${device.name}: ${e.response?.data?.detail ?? 'Failed to trigger agent pull.'}`)
    } finally {
      collecting.value = null
    }
    return
  }

  collecting.value = device.id
  collectDialog.value = { show: false, device, policies: [], policyId: null, loading: true, running: false, error: '' }
  try {
    const { data } = await api.get('/policies/', { params: { devices: device.id, is_active: true, page_size: 500 } })
    const policies = data.results ?? data
    if (policies.length === 0) {
      showSnack(false, `✗ ${device.name}: No active policies assigned.`)
      return
    }
    collectDialog.value.policies = policies
    collectDialog.value.policyId = policies[0].id
    collectDialog.value.loading = false
    collectDialog.value.show = true
  } catch (e) {
    console.error('[collect] error:', e)
    showSnack(false, `✗ ${device?.name ?? 'Device'}: Failed to load policies.`)
  } finally {
    collecting.value = null
  }
}

async function submitCollect() {
  collectDialog.value.running = true
  collectDialog.value.error = ''
  await runCollect(collectDialog.value.device, collectDialog.value.policyId)
  collectDialog.value.show = false
  collectDialog.value.running = false
}

async function runCollect(device, policyId) {
  collecting.value = device.id
  try {
    const { data } = await api.post(`/devices/${device.id}/collect/`, { policy_id: policyId })
    showSnack(true, `✓ ${device.name}: ${data.detail}`)
  } catch (e) {
    const msg = e.response?.data?.detail ?? 'Failed to start collection.'
    if (collectDialog.value.show) {
      collectDialog.value.error = msg
    } else {
      showSnack(false, `✗ ${device.name}: ${msg}`)
    }
  } finally {
    collecting.value = null
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
      ;({ data } = await api.post('/devices/test-connection/', { connection_type: deviceForm.value.connection_type, hostname: deviceForm.value.hostname, port: deviceForm.value.connection_type === 'agent' ? (deviceForm.value.agent_port || 9322) : deviceForm.value.port, host_key: deviceForm.value.host_key, credential: deviceForm.value.credential, username: deviceForm.value.username, password: deviceForm.value.password }))
    }
    deviceForm.value.testResult = { ok: true, detail: data.detail }
  } catch (e) {
    const resp = e.response?.data
    deviceForm.value.testResult = { ok: false, detail: resp?.detail ?? resp?.error ?? JSON.stringify(resp) ?? 'Connection failed.' }
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

onMounted(() => {
  // initial device fetch triggered by @update:options
  loadCredentials()
})
</script>
