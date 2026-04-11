<template>
  <div>
    <!-- ── Stats bar ──────────────────────────────────────────────────────── -->
    <div class="d-flex align-center flex-wrap ga-2 mb-4">
      <template v-if="totalAdded || totalRemoved || totalChanged">
        <v-chip v-if="totalAdded"   color="success" size="small" label prepend-icon="mdi-plus-circle-outline">{{ totalAdded }} added</v-chip>
        <v-chip v-if="totalRemoved" color="error"   size="small" label prepend-icon="mdi-minus-circle-outline">{{ totalRemoved }} removed</v-chip>
        <v-chip v-if="totalChanged" color="warning" size="small" label prepend-icon="mdi-circle-edit-outline">{{ totalChanged }} changed</v-chip>
      </template>
      <span v-else class="text-medium-emphasis text-body-2">No differences detected</span>
      <v-spacer />
      <v-checkbox v-model="changedOnly" label="Changed only" density="compact" hide-details class="flex-grow-0" />
    </div>

    <!-- ── KV summary cards ───────────────────────────────────────────────── -->
    <v-row dense class="mb-3">
      <template v-for="sec in kvSections" :key="sec.key">
        <v-col v-if="!changedOnly || sec.hasChanges" cols="12" sm="6">
          <v-card variant="tonal" :color="sec.hasChanges ? 'warning' : 'secondary'" rounded="lg">
            <v-card-text class="pa-3">
              <div class="d-flex align-center mb-2">
                <div class="text-caption font-weight-bold text-uppercase"
                     :class="sec.hasChanges ? 'text-warning' : 'text-primary'"
                     style="letter-spacing:.08em">{{ sec.title }}</div>
                <v-btn
                  v-if="allowIgnore"
                  icon="mdi-eye-off-outline"
                  size="x-small"
                  variant="text"
                  color="medium-emphasis"
                  class="ml-1 ignore-btn"
                  :title="`Exclude entire '${sec.title}' section from drift`"
                  @click="emitExcludeSection(sec.key)"
                />
              </div>
              <v-table density="compact">
                <thead>
                  <tr>
                    <th class="text-caption" style="width:140px">Field</th>
                    <th class="text-caption text-medium-emphasis" style="width:40%">Baseline</th>
                    <th class="text-caption">Current</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="row in sec.rows" :key="row.key"
                      :class="row.changed ? 'diff-row-changed' : ''">
                    <td class="text-primary font-weight-medium" style="white-space:nowrap;font-size:.8rem">
                      {{ toLabel(row.key) }}
                      <v-btn
                        v-if="allowIgnore && row.changed"
                        icon="mdi-eye-off-outline"
                        size="x-small"
                        variant="text"
                        color="medium-emphasis"
                        class="ml-1 ignore-btn"
                        :title="`Add '${row.key}' as a drift exclusion`"
                        @click="emitIgnoreKv(sec.key, row.key)"
                      />
                    </td>
                    <td class="text-medium-emphasis" style="font-size:.8rem;word-break:break-word">{{ row.baselineStr }}</td>
                    <td :class="row.changed ? 'font-weight-bold' : ''" style="font-size:.8rem;word-break:break-word">{{ row.currentStr }}</td>
                  </tr>
                </tbody>
              </v-table>
            </v-card-text>
          </v-card>
        </v-col>
      </template>
    </v-row>

    <!-- ── Array sections ────────────────────────────────────────────────── -->
    <v-expansion-panels variant="accordion" multiple :model-value="autoOpen">
      <template v-for="sec in arraySections" :key="sec.key">
        <v-expansion-panel v-if="!changedOnly || sec.hasChanges" :value="sec.key">
          <v-expansion-panel-title>
            <div class="d-flex align-center ga-2">
              <span class="text-body-2 font-weight-bold">{{ sec.title }}</span>
              <v-chip v-if="sec.added"   color="success" size="x-small" label>+{{ sec.added }}</v-chip>
              <v-chip v-if="sec.removed" color="error"   size="x-small" label>-{{ sec.removed }}</v-chip>
              <v-chip v-if="sec.changed" color="warning" size="x-small" label>~{{ sec.changed }}</v-chip>
              <v-chip v-if="!sec.added && !sec.removed && !sec.changed" color="default" size="x-small" label>{{ sec.rows.length }}</v-chip>
              <v-btn
                v-if="allowIgnore && !sec.key.includes('.')"
                icon="mdi-eye-off-outline"
                size="x-small"
                variant="text"
                color="medium-emphasis"
                class="ignore-btn"
                :title="`Exclude entire '${sec.title}' section from drift`"
                @click.stop="emitExcludeSection(sec.key)"
              />
            </div>
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <v-table density="compact" class="diff-table">
              <thead>
                <tr>
                  <th v-for="col in sec.cols" :key="col" class="text-caption" style="white-space:nowrap">{{ toLabel(col) }}</th>
                  <th class="text-caption" style="width:100px">Change</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="(row, idx) in sec.rows" :key="idx">
                  <tr v-if="!changedOnly || row._status !== 'unchanged'"
                      :class="diffRowClass(row._status)">
                    <td v-for="col in sec.cols" :key="col" style="font-size:.82rem">
                      <!-- Changed row: show old → new for fields that differ -->
                      <template v-if="row._status === 'changed' && row._fieldChanged?.[col]">
                        <span class="text-medium-emphasis text-decoration-line-through" style="margin-right:2px">{{ cellStr(row._baseline, col, sec.format) }}</span>
                        <span class="mx-1 text-medium-emphasis" aria-hidden="true">→</span>
                        <span class="font-weight-bold">{{ cellStr(row._current, col, sec.format) }}</span>
                        <v-btn
                          v-if="allowIgnore && !isIdCol(sec.key, col)"
                          icon="mdi-eye-off-outline"
                          size="x-small"
                          variant="text"
                          color="medium-emphasis"
                          class="ml-1 ignore-btn"
                          :title="`Add '${col}' field as a drift exclusion`"
                          @click="emitIgnoreArrayField(sec.key, col)"
                        />
                      </template>
                      <!-- Removed row: show baseline data -->
                      <template v-else-if="row._status === 'removed'">
                        <span class="text-medium-emphasis">{{ cellStr(row._baseline, col, sec.format) }}</span>
                      </template>
                      <!-- Added / unchanged: show current (merged into row) -->
                      <template v-else>{{ cellStr(row, col, sec.format) }}</template>
                    </td>
                    <td>
                      <div class="d-flex align-center ga-1">
                        <v-chip v-if="row._status !== 'unchanged'" size="x-small" :color="statusColor(row._status)" label>{{ row._status }}</v-chip>
                        <v-btn
                          v-if="allowIgnore && ITEM_KEY_FIELD[sec.key] && row._status !== 'unchanged'"
                          icon="mdi-eye-off-outline"
                          size="x-small"
                          variant="text"
                          color="medium-emphasis"
                          :title="`Exclude this item from drift`"
                          @click="emitExcludeItem(sec.key, row)"
                        />
                      </div>
                    </td>
                  </tr>
                </template>
              </tbody>
            </v-table>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </template>
    </v-expansion-panels>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  baseline:     { type: Object,  default: null },
  current:      { type: Object,  default: null },
  allowIgnore:  { type: Boolean, default: false },
})

const emit = defineEmits(['ignore-field'])

// ── Ignore helpers ────────────────────────────────────────────────────────────

// Identifier columns that shouldn't be individually ignored
const ID_COLS = {
  'sysctl':              ['key'],
  'filesystem':          ['mount'],
  'services':            ['name'],
  'users':               ['username'],
  'groups':              ['group_name'],
  'packages':            ['name'],
  'listening_services':  ['port', 'protocol'],
  'firewall_rules':      ['chain'],
  'ssh_keys':            ['username', 'key_type'],
  'scheduled_tasks':     ['name'],
  'kernel_modules':      ['name'],
  'pci_devices':         ['slot'],
  'storage_devices':     ['name'],
  'usb_devices':         ['bus_id'],
  'certificates':        ['thumbprint', 'subject'],
  'vpn_tunnels':         ['name'],
  'shares':              ['name'],
  'logging_targets':     ['destination'],
  'vlans':               ['id'],
  'routing_protocols':   ['protocol'],
  'acls':                ['name'],
  'network.interfaces':  ['name'],
  'network.routes':      ['destination', 'gateway'],
  'network.hosts_file':  ['hostname', 'ip'],
}

function isIdCol(secKey, col) {
  return (ID_COLS[secKey] ?? []).includes(col)
}

function emitIgnoreKv(secKey, fieldName) {
  const section = secKey === 'network_kv' ? 'network' : secKey
  emit('ignore-field', { section, spec_type: 'section_field', field_name: fieldName, aux: '' })
}

function emitIgnoreArrayField(secKey, col) {
  if (secKey.includes('.')) {
    const [section, aux] = secKey.split('.')
    emit('ignore-field', { section, spec_type: 'nested_field', field_name: col, aux })
  } else {
    emit('ignore-field', { section: secKey, spec_type: 'item_field', field_name: col, aux: '' })
  }
}

// Map from section key to the identity field used for exclude_key rules.
// Sections with compound identity keys (listening_services, firewall_rules,
// ssh_keys) are excluded — use item_field exclusions for those instead.
const ITEM_KEY_FIELD = {
  users:             'username',
  groups:            'group_name',
  packages:          'name',
  services:          'name',
  filesystem:        'mount',
  scheduled_tasks:   'name',
  startup_items:     'name',
  kernel_modules:    'name',
  pci_devices:       'slot',
  storage_devices:   'name',
  usb_devices:       'bus_id',
  sysctl:            'key',
  certificates:      'thumbprint',
  vpn_tunnels:       'name',
  shares:            'name',
  logging_targets:   'destination',
  vlans:             'id',
  routing_protocols: 'protocol',
  acls:              'name',
}

function emitExcludeSection(secKey) {
  // network_kv is displayed as the network object section
  const section = secKey === 'network_kv' ? 'network' : secKey.split('.')[0]
  emit('ignore-field', { section, spec_type: 'exclude_section', field_name: '*', aux: '' })
}

function emitExcludeItem(secKey, row) {
  const keyField = ITEM_KEY_FIELD[secKey]
  if (!keyField) return
  const source = row._status === 'removed' ? row._baseline : (row._current ?? row)
  const keyValue = source?.[keyField]
  if (keyValue === undefined || keyValue === null) return
  emit('ignore-field', { section: secKey, spec_type: 'exclude_key', field_name: String(keyValue), aux: keyField })
}


const changedOnly = ref(false)

// ── Helpers ──────────────────────────────────────────────────────────────────

function toLabel(k) {
  return String(k).replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function fmtVal(v) {
  if (v === null || v === undefined) return ''
  if (typeof v === 'boolean') return v ? 'Yes' : 'No'
  if (Array.isArray(v)) return v.map(fmtVal).join(', ')
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

function eq(a, b) {
  return JSON.stringify(a) === JSON.stringify(b)
}

// ── KV diff ───────────────────────────────────────────────────────────────────
// Returns [{key, baseline, current, baselineStr, currentStr, changed}]

function kvDiff(baseObj, curObj) {
  const b = baseObj || {}
  const c = curObj  || {}
  const keys = new Set([...Object.keys(b), ...Object.keys(c)])
  return [...keys].map(key => ({
    key,
    baseline:    b[key] ?? null,
    current:     c[key] ?? null,
    baselineStr: fmtVal(b[key]),
    currentStr:  fmtVal(c[key]),
    changed:     !eq(b[key], c[key]),
  }))
}

// ── List diff ─────────────────────────────────────────────────────────────────
// Returns rows merged with _status, _baseline, _current, _fieldChanged

function listDiff(baseArr, curArr, idFn) {
  const bMap = new Map((baseArr || []).map(r => [idFn(r), r]))
  const cMap = new Map((curArr  || []).map(r => [idFn(r), r]))
  const allKeys = [...new Set([...bMap.keys(), ...cMap.keys()])]

  return allKeys.map(k => {
    const bi = bMap.get(k)
    const ci = cMap.get(k)
    let status
    if (!bi)           status = 'added'
    else if (!ci)      status = 'removed'
    else if (!eq(bi, ci)) status = 'changed'
    else               status = 'unchanged'

    let fieldChanged = {}
    if (status === 'changed' && bi && ci) {
      const allFields = new Set([...Object.keys(bi), ...Object.keys(ci)])
      for (const f of allFields) fieldChanged[f] = !eq(bi[f], ci[f])
    }

    return {
      ...(ci || bi),
      _status:       status,
      _baseline:     bi ?? null,
      _current:      ci ?? null,
      _fieldChanged: fieldChanged,
    }
  })
}

// ── Canonical section helpers ─────────────────────────────────────────────────

function flatSecurity(sec) {
  if (!sec) return null
  const { password_policy, ...rest } = sec
  const flat = { ...rest }
  if (password_policy)
    Object.entries(password_policy).forEach(([k, v]) => { flat[`policy_${k}`] = v })
  return flat
}

function flatSnmp(snmp) {
  if (!snmp) return null
  return {
    enabled:      snmp.enabled,
    versions:     snmp.versions,
    communities:  snmp.communities,
    trap_targets: snmp.trap_targets,
    location:     snmp.location,
    contact:      snmp.contact,
    v3_user_count: snmp.v3_users?.length ?? 0,
  }
}

// ── KV sections (summary cards) ───────────────────────────────────────────────

const kvSections = computed(() => {
  const b = props.baseline || {}
  const c = props.current  || {}

  const defs = [
    { key: 'device',     title: 'Device',     bData: b.device,                       cData: c.device },
    { key: 'hardware',   title: 'Hardware',   bData: b.hardware,                     cData: c.hardware },
    { key: 'os',         title: 'OS',         bData: b.os,                           cData: c.os },
    { key: 'security',   title: 'Security',   bData: flatSecurity(b.security),       cData: flatSecurity(c.security) },
    { key: 'ssh_config', title: 'SSH Config', bData: b.ssh_config,                   cData: c.ssh_config },
    { key: 'snmp',       title: 'SNMP',       bData: flatSnmp(b.snmp),               cData: flatSnmp(c.snmp) },
    {
      key: 'network_kv', title: 'Network',
      bData: b.network ? { default_gateway: b.network.default_gateway, dns_servers: b.network.dns_servers } : null,
      cData: c.network ? { default_gateway: c.network.default_gateway, dns_servers: c.network.dns_servers } : null,
    },
  ]

  return defs.map(d => {
    if (!d.bData && !d.cData) return null
    const rows = kvDiff(d.bData, d.cData).filter(r => r.baselineStr || r.currentStr)
    if (!rows.length) return null
    return { key: d.key, title: d.title, rows, hasChanges: rows.some(r => r.changed) }
  }).filter(Boolean)
})

// ── Array section definitions ─────────────────────────────────────────────────

const ARRAY_DEFS = [
  {
    key: 'network.interfaces', title: 'Network Interfaces',
    path: d => d.network?.interfaces,
    idFn: r => r.name,
    cols: ['name', 'mac', 'ipv4', 'admin_status', 'oper_status', 'speed', 'mtu'],
    format: { ipv4: a => a?.join(', ') },
  },
  {
    key: 'network.routes', title: 'Network Routes',
    path: d => d.network?.routes,
    idFn: r => `${r.destination}|${r.gateway}`,
    cols: ['destination', 'gateway', 'interface', 'metric'],
  },
  {
    key: 'network.hosts_file', title: 'Hosts File',
    path: d => d.network?.hosts_file,
    idFn: r => r.hostname || r.ip,
    cols: ['ip', 'hostname'],
  },
  {
    key: 'users', title: 'Users',
    path: d => d.users,
    idFn: r => r.username,
    cols: ['username', 'uid', 'shell', 'groups', 'disabled', 'last_login'],
    format: { groups: a => a?.join(', '), disabled: v => v === true ? 'Yes' : v === false ? 'No' : '' },
  },
  {
    key: 'groups', title: 'Groups',
    path: d => d.groups,
    idFn: r => r.group_name,
    cols: ['group_name', 'gid', 'members'],
    format: { members: a => a?.join(', ') },
  },
  {
    key: 'packages', title: 'Packages',
    path: d => d.packages,
    idFn: r => r.name,
    cols: ['name', 'version', 'vendor', 'install_date'],
  },
  {
    key: 'services', title: 'Services',
    path: d => d.services,
    idFn: r => r.name,
    cols: ['name', 'status', 'startup'],
  },
  {
    key: 'filesystem', title: 'Filesystem',
    path: d => d.filesystem,
    idFn: r => r.mount,
    cols: ['mount', 'type', 'size_gb', 'free_gb'],
  },
  {
    key: 'listening_services', title: 'Listening Services',
    path: d => d.listening_services,
    idFn: r => `${r.protocol}:${r.port}`,
    cols: ['port', 'protocol', 'local_address', 'process_name'],
  },
  {
    key: 'firewall_rules', title: 'Firewall Rules',
    path: d => d.firewall_rules,
    idFn: r => `${r.chain}|${r.action}|${r.protocol}|${r.source}|${r.destination}`,
    cols: ['chain', 'action', 'protocol', 'source', 'destination'],
  },
  {
    key: 'ssh_keys', title: 'SSH Keys',
    path: d => d.ssh_keys,
    idFn: r => `${r.username}:${r.key_type}`,
    cols: ['username', 'key_type', 'comment'],
  },
  {
    key: 'scheduled_tasks', title: 'Scheduled Tasks',
    path: d => d.scheduled_tasks,
    idFn: r => r.name,
    cols: ['name', 'type', 'user', 'schedule', 'enabled'],
    format: { enabled: v => v === true ? 'Yes' : v === false ? 'No' : '' },
  },
  {
    key: 'kernel_modules', title: 'Kernel Modules',
    path: d => d.kernel_modules,
    idFn: r => r.name,
    cols: ['name', 'type', 'description'],
  },
  {
    key: 'pci_devices', title: 'PCI Devices',
    path: d => d.pci_devices,
    idFn: r => r.slot,
    cols: ['slot', 'class', 'vendor', 'device', 'driver'],
  },
  {
    key: 'storage_devices', title: 'Storage Devices',
    path: d => d.storage_devices,
    idFn: r => r.name,
    cols: ['name', 'type', 'model', 'vendor', 'size', 'serial', 'interface', 'removable'],
  },
  {
    key: 'usb_devices', title: 'USB Devices',
    path: d => d.usb_devices,
    idFn: r => r.bus_id,
    cols: ['bus_id', 'vendor_id', 'product_id', 'manufacturer', 'product'],
  },
  {
    key: 'sysctl', title: 'System Parameters',
    path: d => d.sysctl,
    idFn: r => r.key,
    cols: ['key', 'value'],
  },
  {
    key: 'certificates', title: 'Certificates',
    path: d => d.certificates,
    idFn: r => r.thumbprint || r.subject,
    cols: ['subject', 'issuer', 'not_before', 'not_after'],
  },
  {
    key: 'vpn_tunnels', title: 'VPN Tunnels',
    path: d => d.vpn_tunnels,
    idFn: r => r.name,
    cols: ['name', 'type', 'local_address', 'remote_address', 'status'],
  },
  {
    key: 'shares', title: 'Shares',
    path: d => d.shares,
    idFn: r => r.name,
    cols: ['name', 'type', 'path', 'permissions'],
  },
  {
    key: 'logging_targets', title: 'Logging Targets',
    path: d => d.logging_targets,
    idFn: r => r.destination,
    cols: ['destination', 'type', 'protocol'],
  },
  {
    key: 'vlans', title: 'VLANs',
    path: d => d.vlans,
    idFn: r => String(r.id),
    cols: ['id', 'name', 'state'],
  },
  {
    key: 'routing_protocols', title: 'Routing Protocols',
    path: d => d.routing_protocols,
    idFn: r => r.protocol,
    cols: ['protocol', 'instance', 'router_id'],
  },
  {
    key: 'acls', title: 'ACLs',
    path: d => d.acls,
    idFn: r => r.name,
    cols: ['name', 'type'],
  },
]

const arraySections = computed(() => {
  const b = props.baseline || {}
  const c = props.current  || {}

  return ARRAY_DEFS.map(def => {
    const bArr = def.path(b) || []
    const cArr = def.path(c) || []
    if (!bArr.length && !cArr.length) return null

    const rows    = listDiff(bArr, cArr, def.idFn)
    const added   = rows.filter(r => r._status === 'added').length
    const removed = rows.filter(r => r._status === 'removed').length
    const changed = rows.filter(r => r._status === 'changed').length

    return {
      key:        def.key,
      title:      def.title,
      rows,
      cols:       def.cols,
      format:     def.format || {},
      added, removed, changed,
      hasChanges: added + removed + changed > 0,
    }
  }).filter(Boolean)
})

// ── Totals ────────────────────────────────────────────────────────────────────

const totalAdded   = computed(() => arraySections.value.reduce((s, x) => s + x.added,   0))
const totalRemoved = computed(() => arraySections.value.reduce((s, x) => s + x.removed, 0))
const totalChanged = computed(() => {
  const kv  = kvSections.value.reduce((s, x)    => s + x.rows.filter(r => r.changed).length, 0)
  const arr = arraySections.value.reduce((s, x) => s + x.changed, 0)
  return kv + arr
})

// Auto-open panels that have changes
const autoOpen = computed(() => arraySections.value.filter(s => s.hasChanges).map(s => s.key))

// ── Cell rendering ────────────────────────────────────────────────────────────

function cellStr(obj, col, format) {
  if (!obj) return ''
  const v = obj[col]
  return format?.[col] ? format[col](v) : fmtVal(v)
}

function diffRowClass(status) {
  if (status === 'added')   return 'diff-row-added'
  if (status === 'removed') return 'diff-row-removed'
  if (status === 'changed') return 'diff-row-changed'
  return ''
}

function statusColor(status) {
  if (status === 'added')   return 'success'
  if (status === 'removed') return 'error'
  if (status === 'changed') return 'warning'
  return 'default'
}
</script>

<style scoped>
.diff-row-added   { background: rgba(var(--v-theme-success), 0.10) }
.diff-row-removed { background: rgba(var(--v-theme-error),   0.10); opacity: .8 }
.diff-row-changed { background: rgba(var(--v-theme-warning),  0.10) }
.diff-table :deep(td) { vertical-align: middle }
.ignore-btn { opacity: 0.4; transition: opacity .15s }
.ignore-btn:hover { opacity: 1 }
</style>
