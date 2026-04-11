<template>
  <div>
    <div class="d-flex align-center mb-5">
      <div>
        <div class="text-h5 font-weight-bold">Drift Exclusions</div>
        <div class="text-caption text-medium-emphasis">
          Fields matching these rules are excluded from drift comparison.
          Changes take effect within 60 seconds on the next policy run.
        </div>
      </div>
      <v-spacer />
      <v-btn variant="tonal" prepend-icon="mdi-help-circle-outline" class="mr-2" @click="showHelp = true">How it works</v-btn>
      <v-btn color="primary" prepend-icon="mdi-plus" @click="openNew">Add Rule</v-btn>
    </div>

    <v-data-table-server
      v-model:options="tableOptions"
      :headers="headers"
      :items="store.rules"
      :items-length="store.totalCount"
      :loading="store.loading"
      :items-per-page-options="[25, 50, 100]"
      density="compact"
      rounded="lg"
      elevation="1"
      no-data-text="No rules defined."
      @update:options="onTableOptions"
    >
      <template #item.section="{ item }">
        <code class="text-caption">{{ item.section }}</code>
      </template>

      <template #item.spec_type="{ item }">
        <v-chip :color="specTypeColor(item.spec_type)" size="x-small" label>
          {{ specTypeLabel(item.spec_type) }}
        </v-chip>
      </template>

      <template #item.field_name="{ item }">
        <span v-if="item.spec_type === 'exclude_section'" class="text-caption text-medium-emphasis">(entire section)</span>
        <template v-else>
          <code class="text-caption">{{ item.field_name }}</code>
          <span v-if="item.aux" class="text-caption text-medium-emphasis ml-1">
            ({{ auxLabel(item.spec_type) }}: <code>{{ item.aux }}</code>)
          </span>
        </template>
      </template>

      <template #item.is_active="{ item }">
        <v-switch
          :model-value="item.is_active"
          color="success"
          density="compact"
          hide-details
          :loading="toggling === item.id"
          @update:model-value="toggleActive(item)"
        />
      </template>

      <template #item.actions="{ item }">
        <div class="d-flex ga-1 justify-end">
          <v-btn size="x-small" variant="tonal" icon="mdi-pencil" @click="openEdit(item)" />
          <v-btn size="x-small" variant="tonal" color="error" icon="mdi-delete" @click="remove(item)" />
        </div>
      </template>
    </v-data-table-server>

    <!-- Add / Edit dialog -->
    <v-dialog v-model="form.show" max-width="580" scrollable>
      <v-card rounded="lg">
        <v-card-title>{{ form.id ? 'Edit Rule' : 'Add Rule' }}</v-card-title>
        <v-divider />
        <v-card-text class="pa-4">

          <v-select
            v-model="form.section"
            label="Section *"
            :items="SECTIONS"
            density="compact"
            class="mb-3"
          />

          <v-select
            v-model="form.spec_type"
            label="Rule type *"
            :items="SPEC_TYPE_ITEMS"
            density="compact"
            class="mb-1"
          />
          <div class="text-caption text-medium-emphasis mb-3">{{ specTypeHint(form.spec_type) }}</div>

          <!-- nested_field: aux = nested array key -->
          <v-text-field
            v-if="form.spec_type === 'nested_field'"
            v-model="form.aux"
            label="Nested array key *"
            density="compact"
            placeholder="e.g. neighbors, ports"
            hint="Name of the nested array within each item"
            persistent-hint
            class="mb-3"
          />

          <!-- exclude_key: aux = key field name -->
          <v-text-field
            v-if="form.spec_type === 'exclude_key'"
            v-model="form.aux"
            label="Key field name"
            density="compact"
            placeholder="key"
            hint="The item sub-field to match on (usually 'key' for sysctl)"
            persistent-hint
            class="mb-3"
          />

          <v-text-field
            v-if="form.spec_type !== 'exclude_section'"
            v-model="form.field_name"
            :label="fieldNameLabel(form.spec_type)"
            density="compact"
            class="mb-3"
          />
          <v-alert
            v-else
            type="info"
            variant="tonal"
            density="compact"
            class="mb-3"
          >
            The entire <strong>{{ form.section || 'selected' }}</strong> section will be excluded from drift comparison.
          </v-alert>

          <v-textarea
            v-model="form.description"
            label="Description"
            rows="2"
            density="compact"
            placeholder="Why should this field be excluded from drift?"
          />

          <v-alert v-if="form.error" type="error" variant="tonal" density="compact" class="mt-3">
            {{ form.error }}
          </v-alert>
        </v-card-text>
        <v-divider />
        <v-card-actions>
          <v-spacer />
          <v-btn @click="form.show = false">Cancel</v-btn>
          <v-btn color="primary" :loading="form.saving" @click="save">Save</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Confirm delete -->
    <v-dialog v-model="confirmDialog.open" max-width="400" persistent>
      <v-card rounded="lg">
        <v-card-title class="pt-4">Delete Rule</v-card-title>
        <v-card-text>{{ confirmDialog.message }}</v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="confirmDialog.resolve(false)">Cancel</v-btn>
          <v-btn color="error" variant="tonal" @click="confirmDialog.resolve(true)">Delete</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- ── Help dialog ─────────────────────────────────────────────────────── -->
    <v-dialog v-model="showHelp" max-width="720" scrollable>
      <v-card rounded="lg">
        <v-card-title class="d-flex align-center pt-4 pb-2">
          <v-icon icon="mdi-tune" class="mr-2" color="primary" />
          Drift Exclusions
          <v-spacer />
          <v-btn icon="mdi-close" variant="text" @click="showHelp = false" />
        </v-card-title>
        <v-divider />
        <v-card-text class="pa-5" style="font-size:0.92rem;line-height:1.7">

          <p class="mb-3">
            <strong>Drift Exclusions</strong> tell IsotopeIQ Satellite which fields to ignore during
            drift comparison. Some values change legitimately on every collection run — timestamps,
            lease counters, uptime — and without exclusion rules they would generate constant false-positive
            drift alerts.
          </p>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">How it works</div>
          <p class="mb-3">
            Each rule targets a <strong>Section</strong> of the canonical document (e.g. <code>network</code>,
            <code>services</code>) and specifies which field — or which nested field — to exclude.
            Rules are loaded by the drift engine before any comparison; matched fields are stripped from
            both the stored baseline and the new result before diffing, so they never appear as drift.
          </p>
          <p class="mb-2">
            Rules take effect within 60 seconds without a server restart.
            Disabling a rule re-enables drift detection for that field immediately on the next policy run.
          </p>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">Rule types</div>
          <v-table density="compact" class="mb-3 rounded-lg" style="border:1px solid rgba(0,0,0,.12)">
            <tbody>
              <tr>
                <td class="font-weight-medium" style="width:28%">Exact field</td>
                <td>Excludes a single named field on every item in the section. Use for simple scalar
                  fields like <code>last_seen</code> or <code>uptime</code>.</td>
              </tr>
              <tr>
                <td class="font-weight-medium">Regex field</td>
                <td>Excludes any field whose name matches a regular expression. Useful when a set of
                  related fields share a naming pattern.</td>
              </tr>
              <tr>
                <td class="font-weight-medium">Nested field</td>
                <td>Excludes a field inside a nested array within each section item. Specify the
                  <em>nested array key</em> (e.g. <code>neighbors</code>) and the field within
                  each nested item to ignore.</td>
              </tr>
              <tr>
                <td class="font-weight-medium">Exclude key</td>
                <td>Excludes items from a key=value section (e.g. <code>sysctl</code>) where the
                  item's key field matches. Useful for frequently-changing kernel parameters.</td>
              </tr>
              <tr>
                <td class="font-weight-medium">Exclude section</td>
                <td>Skips the entire section during drift comparison. Use sparingly — this silences
                  all drift for that section.</td>
              </tr>
            </tbody>
          </v-table>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">Common examples</div>
          <v-table density="compact" class="mb-3 rounded-lg" style="border:1px solid rgba(0,0,0,.12)">
            <tbody>
              <tr><td class="font-weight-medium" style="width:28%"><code>os</code> / exact / <code>uptime</code></td><td>Ignores the uptime counter which increments on every collection.</td></tr>
              <tr><td class="font-weight-medium"><code>network</code> / exact / <code>leases</code></td><td>Ignores DHCP lease counts that fluctuate continuously.</td></tr>
              <tr><td class="font-weight-medium"><code>services</code> / regex / <code>.*_pid$</code></td><td>Ignores any field ending in <code>_pid</code> across all service entries.</td></tr>
              <tr><td class="font-weight-medium"><code>sysctl</code> / exclude key / <code>kernel.random.entropy_avail</code></td><td>Ignores the entropy counter sysctl entry.</td></tr>
            </tbody>
          </v-table>

          <v-divider class="my-3" />
          <div class="text-subtitle-2 font-weight-bold mb-2">Canonical schema reference</div>
          <p class="mb-3 text-medium-emphasis" style="font-size:0.88rem">
            The <em>Section</em> field on every exclusion must match one of the top-level keys below.
            Required sections are always present; optional sections only appear when the collection
            script populates them.
          </p>

          <!-- Required sections -->
          <div class="text-caption font-weight-bold text-medium-emphasis mb-1 mt-2">Required sections</div>
          <v-table density="compact" class="mb-3 rounded-lg" style="border:1px solid rgba(0,0,0,.12);font-size:0.82rem">
            <thead><tr>
              <th style="width:22%">Section</th>
              <th style="width:12%">Type</th>
              <th>Fields</th>
            </tr></thead>
            <tbody>
              <tr>
                <td><code>device</code></td>
                <td class="text-medium-emphasis">object</td>
                <td><code>hostname</code>, <code>fqdn</code>, <code>device_type</code>, <code>vendor</code>, <code>model</code></td>
              </tr>
              <tr>
                <td><code>hardware</code></td>
                <td class="text-medium-emphasis">object</td>
                <td><code>cpu_model</code>, <code>cpu_cores</code>, <code>memory_gb</code>, <code>bios_version</code>, <code>serial_number</code>, <code>architecture</code>, <code>virtualization_type</code></td>
              </tr>
              <tr>
                <td><code>os</code></td>
                <td class="text-medium-emphasis">object</td>
                <td><code>name</code>, <code>version</code>, <code>build</code>, <code>kernel</code>, <code>timezone</code>, <code>ntp_servers</code>, <code>ntp_synced</code></td>
              </tr>
              <tr>
                <td><code>network</code></td>
                <td class="text-medium-emphasis">object</td>
                <td><code>interfaces[ ]</code>, <code>dns_servers</code>, <code>default_gateway</code>, <code>routes[ ]</code>, <code>hosts_file[ ]</code>, <code>open_ports</code><br>
                  <span class="text-medium-emphasis" style="font-size:0.8rem">Each interface: <code>name</code>, <code>mac</code>, <code>ipv4</code>, <code>ipv6</code>, <code>admin_status</code>, <code>oper_status</code>, <code>mtu</code>, <code>speed</code>, <code>duplex</code>, <code>interface_type</code> (<code>physical</code> | <code>bridge</code> | <code>bond</code> | <code>vlan</code> | <code>tun</code> | <code>tunnel</code> | <code>macvlan</code> | <code>other</code>)</span></td>
              </tr>
              <tr>
                <td><code>users</code></td>
                <td class="text-medium-emphasis">array</td>
                <td><code>username</code>, <code>uid</code>, <code>groups</code>, <code>home</code>, <code>shell</code>, <code>disabled</code>, <code>password_last_set</code>, <code>last_login</code>, <code>sudo_privileges</code></td>
              </tr>
              <tr>
                <td><code>groups</code></td>
                <td class="text-medium-emphasis">array</td>
                <td><code>group_name</code>, <code>gid</code>, <code>members</code></td>
              </tr>
              <tr>
                <td><code>packages</code></td>
                <td class="text-medium-emphasis">array</td>
                <td><code>name</code>, <code>version</code>, <code>vendor</code>, <code>install_date</code>, <code>source</code></td>
              </tr>
              <tr>
                <td><code>services</code></td>
                <td class="text-medium-emphasis">array</td>
                <td><code>name</code>, <code>status</code>, <code>startup</code></td>
              </tr>
              <tr>
                <td><code>filesystem</code></td>
                <td class="text-medium-emphasis">array</td>
                <td><code>mount</code>, <code>type</code>, <code>size_gb</code>, <code>free_gb</code>, <code>mount_options</code>, <code>suid_files</code></td>
              </tr>
              <tr>
                <td><code>security</code></td>
                <td class="text-medium-emphasis">object</td>
                <td><code>firewall_enabled</code>, <code>antivirus</code>, <code>secure_boot</code>, <code>selinux_mode</code>, <code>apparmor_status</code>, <code>audit_logging_enabled</code>, <code>uac_enabled</code>, <code>defender_enabled</code>, <code>password_policy{ }</code></td>
              </tr>
            </tbody>
          </v-table>

          <!-- Optional sections -->
          <div class="text-caption font-weight-bold text-medium-emphasis mb-1 mt-2">Optional sections</div>
          <v-table density="compact" class="mb-3 rounded-lg" style="border:1px solid rgba(0,0,0,.12);font-size:0.82rem">
            <thead><tr>
              <th style="width:22%">Section</th>
              <th style="width:12%">Type</th>
              <th>Fields</th>
            </tr></thead>
            <tbody>
              <tr>
                <td><code>scheduled_tasks</code></td>
                <td class="text-medium-emphasis">array</td>
                <td><code>name</code>, <code>type</code>, <code>command</code>, <code>schedule</code>, <code>user</code>, <code>enabled</code></td>
              </tr>
              <tr>
                <td><code>startup_items</code></td>
                <td class="text-medium-emphasis">array</td>
                <td><code>name</code>, <code>type</code>, <code>command</code>, <code>path</code>, <code>enabled</code></td>
              </tr>
              <tr>
                <td><code>ssh_keys</code></td>
                <td class="text-medium-emphasis">array</td>
                <td><code>username</code>, <code>key_type</code>, <code>public_key</code>, <code>comment</code></td>
              </tr>
              <tr>
                <td><code>kernel_modules</code></td>
                <td class="text-medium-emphasis">array</td>
                <td><code>name</code>, <code>type</code>, <code>description</code>, <code>path</code>, <code>hash</code>, <code>signed</code></td>
              </tr>
              <tr>
                <td><code>pci_devices</code></td>
                <td class="text-medium-emphasis">array</td>
                <td><code>slot</code>, <code>class</code>, <code>vendor</code>, <code>device</code>, <code>driver</code>, <code>subsystem_vendor</code>, <code>subsystem_device</code></td>
              </tr>
              <tr>
                <td><code>storage_devices</code></td>
                <td class="text-medium-emphasis">array</td>
                <td><code>name</code>, <code>type</code>, <code>model</code>, <code>vendor</code>, <code>size</code>, <code>serial</code>, <code>interface</code>, <code>removable</code></td>
              </tr>
              <tr>
                <td><code>usb_devices</code></td>
                <td class="text-medium-emphasis">array</td>
                <td><code>bus_id</code>, <code>vendor_id</code>, <code>product_id</code>, <code>manufacturer</code>, <code>product</code></td>
              </tr>
              <tr>
                <td><code>listening_services</code></td>
                <td class="text-medium-emphasis">array</td>
                <td><code>protocol</code>, <code>local_address</code>, <code>port</code>, <code>process_name</code>, <code>pid</code>, <code>user</code></td>
              </tr>
              <tr>
                <td><code>certificates</code></td>
                <td class="text-medium-emphasis">array</td>
                <td><code>subject</code>, <code>issuer</code>, <code>thumbprint</code>, <code>serial</code>, <code>not_before</code>, <code>not_after</code>, <code>store</code></td>
              </tr>
              <tr>
                <td><code>firewall_rules</code></td>
                <td class="text-medium-emphasis">array</td>
                <td><code>chain</code>, <code>direction</code>, <code>action</code>, <code>protocol</code>, <code>source</code>, <code>destination</code>, <code>port</code>, <code>enabled</code>, <code>description</code>, <code>source_tool</code></td>
              </tr>
              <tr>
                <td><code>sysctl</code></td>
                <td class="text-medium-emphasis">array</td>
                <td><code>key</code>, <code>value</code></td>
              </tr>
              <tr>
                <td><code>ssh_config</code></td>
                <td class="text-medium-emphasis">object</td>
                <td><code>port</code>, <code>protocol</code>, <code>permit_root_login</code>, <code>password_authentication</code>, <code>pubkey_authentication</code>, <code>permit_empty_passwords</code>, <code>x11_forwarding</code>, <code>max_auth_tries</code>, <code>allow_users</code>, <code>deny_users</code>, <code>allow_groups</code>, <code>deny_groups</code>, <code>use_pam</code></td>
              </tr>
              <tr>
                <td><code>snmp</code></td>
                <td class="text-medium-emphasis">object</td>
                <td><code>enabled</code>, <code>versions</code>, <code>communities</code>, <code>v3_users[ ]</code>, <code>trap_targets</code>, <code>location</code>, <code>contact</code></td>
              </tr>
              <tr>
                <td><code>shares</code></td>
                <td class="text-medium-emphasis">array</td>
                <td><code>name</code>, <code>type</code>, <code>path</code>, <code>comment</code>, <code>permissions</code>, <code>read_only</code>, <code>enabled</code></td>
              </tr>
              <tr>
                <td><code>logging_targets</code></td>
                <td class="text-medium-emphasis">array</td>
                <td><code>type</code>, <code>destination</code>, <code>protocol</code>, <code>facility</code>, <code>enabled</code></td>
              </tr>
              <tr>
                <td><code>vpn_tunnels</code></td>
                <td class="text-medium-emphasis">array</td>
                <td><code>name</code>, <code>type</code>, <code>local_address</code>, <code>remote_address</code>, <code>status</code>, <code>cipher_suite</code>, <code>auth_method</code></td>
              </tr>
              <tr>
                <td><code>vlans</code> <span class="text-caption text-medium-emphasis">(network devices)</span></td>
                <td class="text-medium-emphasis">array</td>
                <td><code>id</code>, <code>name</code>, <code>state</code></td>
              </tr>
              <tr>
                <td><code>acls</code> <span class="text-caption text-medium-emphasis">(network devices)</span></td>
                <td class="text-medium-emphasis">array</td>
                <td><code>name</code>, <code>type</code>, <code>entries[ ]</code></td>
              </tr>
              <tr>
                <td><code>routing_protocols</code> <span class="text-caption text-medium-emphasis">(network devices)</span></td>
                <td class="text-medium-emphasis">array</td>
                <td><code>protocol</code>, <code>instance</code>, <code>router_id</code>, <code>networks</code>, <code>neighbors[ ]</code></td>
              </tr>
              <tr>
                <td><code>aaa</code> <span class="text-caption text-medium-emphasis">(network devices)</span></td>
                <td class="text-medium-emphasis">object</td>
                <td><code>tacacs_servers</code>, <code>radius_servers</code>, <code>authentication_lists</code>, <code>authorization_lists</code>, <code>accounting_lists</code></td>
              </tr>
              <tr>
                <td><code>spanning_tree</code> <span class="text-caption text-medium-emphasis">(network devices)</span></td>
                <td class="text-medium-emphasis">object</td>
                <td><code>mode</code>, <code>root_bridge</code>, <code>root_priority</code>, <code>root_address</code>, <code>ports[ ]</code></td>
              </tr>
              <tr>
                <td><code>custom</code></td>
                <td class="text-medium-emphasis">object</td>
                <td>Free-form object — any fields populated by custom parsers.</td>
              </tr>
            </tbody>
          </v-table>

        </v-card-text>
        <v-divider />
        <v-card-actions class="pa-3">
          <v-spacer />
          <v-btn color="primary" variant="tonal" @click="showHelp = false">Got it</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useVolatileRulesStore } from '../stores/volatileRules'

const store = useVolatileRulesStore()

const showHelp = ref(false)

// ── Table ─────────────────────────────────────────────────────────────────────

const headers = [
  { title: 'Section',    key: 'section',    sortable: true  },
  { title: 'Type',       key: 'spec_type',  sortable: false },
  { title: 'Field / Value', key: 'field_name', sortable: true },
  { title: 'Active',     key: 'is_active',  sortable: false },
  { title: '',           key: 'actions',    sortable: false, align: 'end' },
]

const tableOptions = ref({ page: 1, itemsPerPage: 50, sortBy: [] })

function onTableOptions(options) {
  tableOptions.value = options
  const params = { page: options.page, page_size: options.itemsPerPage }
  store.fetchRules(params)
}

// ── Canonical sections ────────────────────────────────────────────────────────

const SECTIONS = [
  'device', 'hardware', 'os', 'security', 'ssh_config', 'snmp',
  'network', 'filesystem', 'users', 'packages', 'services',
  'listening_services', 'routes', 'interfaces', 'sysctl',
  'certificates', 'arp_table', 'routing_protocols',
  'vpn_tunnels', 'vlans', 'spanning_tree', 'pci_devices',
  'storage_devices', 'usb_devices',
]

// ── Spec type helpers ─────────────────────────────────────────────────────────

const SPEC_TYPE_ITEMS = [
  { title: 'Section field — drop a field from the section object', value: 'section_field' },
  { title: 'Item field — drop a field from each array item',       value: 'item_field'    },
  { title: 'Nested field — drop a field from a nested array',      value: 'nested_field'  },
  { title: 'Exclude item by key value',                            value: 'exclude_key'   },
  { title: 'Exclude section — omit entire section from comparison',value: 'exclude_section'},
]

function specTypeLabel(t) {
  return { section_field: 'section field', item_field: 'item field',
           nested_field: 'nested field', exclude_key: 'exclude key',
           exclude_section: 'exclude section' }[t] ?? t
}

function specTypeColor(t) {
  return { section_field: 'info', item_field: 'primary',
           nested_field: 'secondary', exclude_key: 'warning',
           exclude_section: 'error' }[t] ?? 'default'
}

function specTypeHint(t) {
  return {
    section_field:    'Removes a scalar field from the section dict (e.g. os.ntp_synced).',
    item_field:       'Removes a field from every item in the section array (e.g. filesystem[*].free_gb).',
    nested_field:     'Removes a field from items inside a nested array within each item (e.g. routing_protocols[*].neighbors[*].state).',
    exclude_key:      'Removes entire items from the section array when item[key_field] matches the given value. Useful for sysctl runtime counters.',
    exclude_section:  'Removes the entire section from both sides before comparison. Use this to completely ignore a section (e.g. listening_services).',
  }[t] ?? ''
}

function auxLabel(t) {
  if (t === 'nested_field') return 'nested key'
  if (t === 'exclude_key')  return 'key field'
  return 'aux'
}

function fieldNameLabel(t) {
  if (t === 'exclude_key') return 'Key value to exclude *'
  return 'Field name *'
}

// ── Active toggle ─────────────────────────────────────────────────────────────

const toggling = ref(null)

async function toggleActive(rule) {
  toggling.value = rule.id
  try {
    await store.updateRule(rule.id, { is_active: !rule.is_active })
  } finally {
    toggling.value = null
  }
}

// ── Add / Edit dialog ─────────────────────────────────────────────────────────

function blankForm() {
  return { show: false, id: null, section: '', spec_type: 'item_field', field_name: '', aux: '', description: '', saving: false, error: '' }
}
const form = ref(blankForm())

function openNew() {
  form.value = { ...blankForm(), show: true }
}

function openEdit(rule) {
  form.value = {
    show: true, id: rule.id,
    section: rule.section, spec_type: rule.spec_type,
    field_name: rule.field_name, aux: rule.aux,
    description: rule.description,
    saving: false, error: '',
  }
}

async function save() {
  form.value.error = ''
  const payload = {
    section:     form.value.section,
    spec_type:   form.value.spec_type,
    field_name:  form.value.spec_type === 'exclude_section' ? '*' : form.value.field_name.trim(),
    aux:         form.value.aux.trim(),
    description: form.value.description,
  }
  if (!payload.section) {
    form.value.error = 'Section is required.'
    return
  }
  if (form.value.spec_type !== 'exclude_section' && !payload.field_name) {
    form.value.error = 'Field name is required.'
    return
  }
  if (form.value.spec_type === 'nested_field' && !payload.aux) {
    form.value.error = 'Nested array key is required for nested_field rules.'
    return
  }
  form.value.saving = true
  try {
    if (form.value.id) {
      await store.updateRule(form.value.id, payload)
    } else {
      await store.createRule(payload)
    }
    form.value.show = false
  } catch (e) {
    form.value.error = JSON.stringify(e.response?.data ?? 'Save failed.')
  } finally {
    form.value.saving = false
  }
}

// ── Delete ────────────────────────────────────────────────────────────────────

const confirmDialog = ref({ open: false, message: '', resolve: () => {} })
function askConfirm(message) {
  return new Promise(resolve => {
    confirmDialog.value = { open: true, message, resolve: (val) => { confirmDialog.value.open = false; resolve(val) } }
  })
}

async function remove(rule) {
  const ok = await askConfirm(`Delete rule "${rule.section} / ${rule.field_name}"? Future drift comparisons will no longer ignore this field.`)
  if (!ok) return
  await store.deleteRule(rule.id)
}
</script>
