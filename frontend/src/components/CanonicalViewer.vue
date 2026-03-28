<template>
  <div>
    <!-- ── Summary cards ──────────────────────────────────────────────── -->
    <v-row dense class="mb-3">
      <v-col v-if="d.device && anyValues(d.device)" cols="12" sm="6" md="3">
        <v-card variant="tonal" color="secondary" rounded="lg">
          <v-card-text class="pa-3">
            <div class="text-caption font-weight-bold text-uppercase text-primary mb-2" style="letter-spacing:.08em">Device</div>
            <CvKv :data="d.device" />
          </v-card-text>
        </v-card>
      </v-col>
      <v-col v-if="d.hardware && anyValues(d.hardware)" cols="12" sm="6" md="3">
        <v-card variant="tonal" color="secondary" rounded="lg">
          <v-card-text class="pa-3">
            <div class="text-caption font-weight-bold text-uppercase text-primary mb-2" style="letter-spacing:.08em">Hardware</div>
            <CvKv :data="d.hardware" />
          </v-card-text>
        </v-card>
      </v-col>
      <v-col v-if="d.os && anyValues(d.os)" cols="12" sm="6" md="3">
        <v-card variant="tonal" color="secondary" rounded="lg">
          <v-card-text class="pa-3">
            <div class="text-caption font-weight-bold text-uppercase text-primary mb-2" style="letter-spacing:.08em">OS</div>
            <CvKv :data="d.os" />
          </v-card-text>
        </v-card>
      </v-col>
      <v-col v-if="d.security && anyValues(d.security)" cols="12" sm="6" md="3">
        <v-card variant="tonal" color="secondary" rounded="lg">
          <v-card-text class="pa-3">
            <div class="text-caption font-weight-bold text-uppercase text-primary mb-2" style="letter-spacing:.08em">Security</div>
            <CvKv :data="flatSecurity(d.security)" />
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- ── Sections ────────────────────────────────────────────────────── -->
    <v-expansion-panels variant="accordion" multiple :model-value="openSections">

      <CvSection v-if="d.network" value="network" title="Network" :count="d.network?.interfaces?.length ?? 0">
        <div v-if="d.network.default_gateway" class="text-body-2 mb-1">Default gateway: <strong>{{ d.network.default_gateway }}</strong></div>
        <div v-if="d.network.dns_servers?.length" class="text-body-2 mb-2">DNS: <strong>{{ d.network.dns_servers.join(', ') }}</strong></div>
        <CvTable v-if="d.network.interfaces?.length" :rows="d.network.interfaces" :cols="['name','mac','ipv4','ipv6','admin_status','oper_status','speed','mtu']" :format="{ ipv4: a => a?.join(', '), ipv6: a => a?.join(', ') }" />
        <CvTable v-if="d.network.routes?.length" title="Routes" :rows="d.network.routes" :cols="['destination','gateway','interface','metric']" />
        <CvTable v-if="d.network.hosts_file?.length" title="Hosts File" :rows="d.network.hosts_file" :cols="['ip','hostname']" />
      </CvSection>

      <CvSection v-if="d.users?.length" value="users" title="Users" :count="d.users.length">
        <CvTable :rows="d.users" :cols="['username','uid','shell','home','groups','sudo_privileges','disabled','last_login']" :format="{ groups: a => a?.join(', '), disabled: v => v === true ? 'Yes' : v === false ? 'No' : '' }" searchable />
      </CvSection>

      <CvSection v-if="d.groups?.length" value="groups" title="Groups" :count="d.groups.length">
        <CvTable :rows="d.groups" :cols="['group_name','gid','members']" :format="{ members: a => a?.join(', ') }" searchable />
      </CvSection>

      <CvSection v-if="d.packages?.length" value="packages" title="Packages" :count="d.packages.length">
        <CvTable :rows="d.packages" :cols="['name','version','vendor','source','install_date']" searchable />
      </CvSection>

<CvSection v-if="d.services?.length" value="services" title="Services" :count="d.services.length">
        <CvTable :rows="d.services" :cols="['name','status','startup']"
          :badges="{ status: { running: 'success', stopped: 'error', unknown: 'default' }, startup: { enabled: 'success', disabled: 'default', manual: 'warning', unknown: 'default' } }"
          searchable />
      </CvSection>

      <CvSection v-if="d.filesystem?.length" value="filesystem" title="Filesystem" :count="d.filesystem.length">
        <CvTable :rows="d.filesystem" :cols="['mount','type','size_gb','free_gb','mount_options']" :format="{ mount_options: a => a?.join(', '), size_gb: v => v != null ? v + ' GB' : '', free_gb: v => v != null ? v + ' GB' : '' }" />
      </CvSection>

      <CvSection v-if="d.listening_services?.length" value="listening_services" title="Listening Services" :count="d.listening_services.length">
        <CvTable :rows="d.listening_services" :cols="['port','protocol','local_address','process_name','pid','user']" searchable />
      </CvSection>

      <CvSection v-if="d.firewall_rules?.length" value="firewall_rules" title="Firewall Rules" :count="d.firewall_rules.length">
        <CvTable :rows="d.firewall_rules" :cols="['chain','direction','action','protocol','source','destination','port','source_tool']" searchable />
      </CvSection>

      <CvSection v-if="d.ssh_keys?.length" value="ssh_keys" title="SSH Authorized Keys" :count="d.ssh_keys.length">
        <CvTable :rows="d.ssh_keys" :cols="['username','key_type','comment','public_key']" :truncate="['public_key']" />
      </CvSection>

      <CvSection v-if="d.ssh_config && anyValues(d.ssh_config)" value="ssh_config" title="SSH Config">
        <CvKv :data="d.ssh_config" />
      </CvSection>

      <CvSection v-if="d.scheduled_tasks?.length" value="scheduled_tasks" title="Scheduled Tasks" :count="d.scheduled_tasks.length">
        <CvTable :rows="d.scheduled_tasks" :cols="['name','type','user','schedule','command','enabled']" :format="{ enabled: v => v === true ? 'Yes' : v === false ? 'No' : '' }" searchable />
      </CvSection>

      <CvSection v-if="d.kernel_modules?.length" value="kernel_modules" title="Kernel Modules" :count="d.kernel_modules.length">
        <CvTable :rows="d.kernel_modules" :cols="['name','type','description','signed']" :format="{ signed: v => v === true ? 'Yes' : v === false ? 'No' : '' }" searchable />
      </CvSection>

      <CvSection v-if="d.sysctl?.length" value="sysctl" title="System Parameters" :count="d.sysctl.length">
        <CvTable :rows="d.sysctl" :cols="['key','value']" searchable />
      </CvSection>

      <CvSection v-if="d.certificates?.length" value="certificates" title="Certificates" :count="d.certificates.length">
        <CvTable :rows="d.certificates" :cols="['subject','issuer','not_before','not_after','store','thumbprint']" :truncate="['thumbprint']" searchable />
      </CvSection>

      <CvSection v-if="d.vpn_tunnels?.length" value="vpn_tunnels" title="VPN Tunnels" :count="d.vpn_tunnels.length">
        <CvTable :rows="d.vpn_tunnels" :cols="['name','type','local_address','remote_address','status','auth_method']"
          :badges="{ status: { up: 'success', down: 'error', unknown: 'default' } }" />
      </CvSection>

      <CvSection v-if="d.shares?.length" value="shares" title="Shares" :count="d.shares.length">
        <CvTable :rows="d.shares" :cols="['name','type','path','permissions','read_only','enabled']" :format="{ read_only: v => v === true ? 'Yes' : v === false ? 'No' : '', enabled: v => v === true ? 'Yes' : v === false ? 'No' : '' }" />
      </CvSection>

      <CvSection v-if="d.logging_targets?.length" value="logging_targets" title="Logging Targets" :count="d.logging_targets.length">
        <CvTable :rows="d.logging_targets" :cols="['destination','type','protocol','facility','enabled']" :format="{ enabled: v => v === true ? 'Yes' : v === false ? 'No' : '' }" />
      </CvSection>

      <CvSection v-if="d.vlans?.length" value="vlans" title="VLANs" :count="d.vlans.length">
        <CvTable :rows="d.vlans" :cols="['id','name','state']" />
      </CvSection>

      <CvSection v-if="d.routing_protocols?.length" value="routing_protocols" title="Routing Protocols" :count="d.routing_protocols.length">
        <CvTable :rows="d.routing_protocols" :cols="['protocol','instance','router_id','networks']" :format="{ networks: a => a?.join(', ') }" />
      </CvSection>

      <CvSection v-if="d.custom && anyValues(d.custom)" value="custom" title="Custom">
        <CvKv :data="d.custom" />
      </CvSection>

    </v-expansion-panels>
  </div>
</template>

<script setup>
import { computed, defineComponent, resolveComponent, h, ref } from 'vue'

const props = defineProps({
  data: { type: Object, required: true },
})

const d = computed(() => props.data ?? {})

function anyValues(obj) {
  return obj && Object.values(obj).some(v =>
    v !== null && v !== undefined && v !== '' &&
    !(Array.isArray(v) && v.length === 0)
  )
}

function flatSecurity(sec) {
  if (!sec) return {}
  const { password_policy, ...rest } = sec
  const flat = { ...rest }
  if (password_policy) {
    Object.entries(password_policy).forEach(([k, v]) => { flat[`policy_${k}`] = v })
  }
  return flat
}

const openSections = []

function fmtVal(v) {
  if (v === null || v === undefined) return ''
  if (typeof v === 'boolean') return v ? 'Yes' : 'No'
  if (Array.isArray(v)) return v.join(', ')
  return String(v)
}

function toLabel(k) {
  return k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

// ── CvKv ─────────────────────────────────────────────────────────────────────
const CvKv = defineComponent({
  props: { data: Object },
  setup(props) {
    return () => {
      const VTable = resolveComponent('VTable')
      const entries = Object.entries(props.data ?? {}).filter(([, v]) => v !== null && v !== undefined && v !== '')
      return h(VTable, { density: 'compact' }, {
        default: () => h('tbody', entries.map(([k, v]) =>
          h('tr', [
            h('td', { style: 'width:180px;font-weight:500;color:rgb(var(--v-theme-primary));white-space:nowrap' }, toLabel(k)),
            h('td', { style: 'word-break:break-word' }, fmtVal(v)),
          ])
        )),
      })
    }
  },
})

// ── CvSection ────────────────────────────────────────────────────────────────
const CvSection = defineComponent({
  props: {
    value: String,
    title: String,
    count: { type: Number, default: null },
  },
  setup(props, { slots }) {
    return () => {
      const VExpansionPanel = resolveComponent('VExpansionPanel')
      const VChip = resolveComponent('VChip')
      return h(VExpansionPanel, { value: props.value }, {
        title: () => h('div', { class: 'd-flex align-center ga-2' }, [
          h('span', { class: 'text-body-2 font-weight-bold' }, props.title),
          props.count != null
            ? h(VChip, { size: 'x-small', color: 'primary', label: true }, { default: () => String(props.count) })
            : null,
        ]),
        text: () => slots.default?.(),
      })
    }
  },
})

// ── CvTable ──────────────────────────────────────────────────────────────────
const CvTable = defineComponent({
  props: {
    rows:       { type: Array,   default: () => [] },
    cols:       { type: Array,   default: null },
    title:      { type: String,  default: null },
    format:     { type: Object,  default: () => ({}) },
    badges:     { type: Object,  default: () => ({}) },
    truncate:   { type: Array,   default: () => [] },
    searchable: { type: Boolean, default: false },
  },
  setup(props) {
    const search = ref('')

    const headers = computed(() => {
      if (props.cols) return props.cols
      if (!props.rows.length) return []
      return Object.keys(props.rows[0])
    })

    const filtered = computed(() => {
      if (!search.value.trim()) return props.rows
      const q = search.value.toLowerCase()
      return props.rows.filter(row =>
        Object.values(row).some(v => String(v ?? '').toLowerCase().includes(q))
      )
    })

    function cellVal(row, col) {
      const v = row[col]
      if (props.format[col]) return props.format[col](v)
      return fmtVal(v)
    }

    function badgeColor(col, row) {
      if (!props.badges[col]) return null
      return props.badges[col][row[col]] ?? null
    }

    return () => {
      const VTable = resolveComponent('VTable')
      const VChip = resolveComponent('VChip')
      const VTextField = resolveComponent('VTextField')
      const nodes = []

      if (props.title) {
        nodes.push(h('div', {
          style: 'font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:rgba(var(--v-theme-on-surface),.5);margin:12px 0 4px',
        }, props.title))
      }

      if (props.searchable) {
        nodes.push(h(VTextField, {
          modelValue: search.value,
          'onUpdate:modelValue': v => { search.value = v },
          placeholder: 'Filter…',
          density: 'compact',
          variant: 'outlined',
          hideDetails: true,
          prependInnerIcon: 'mdi-magnify',
          clearable: true,
          style: 'max-width:260px;margin-bottom:8px',
        }))
      }

      if (!filtered.value.length) {
        nodes.push(h('div', { style: 'color:rgba(var(--v-theme-on-surface),.5);font-size:.85rem;padding:8px 0' }, 'No entries.'))
        return h('div', nodes)
      }

      nodes.push(
        h(VTable, { density: 'compact' }, {
          default: () => [
            h('thead', h('tr',
              headers.value.map(col => h('th', { style: 'white-space:nowrap' }, toLabel(col)))
            )),
            h('tbody', filtered.value.map(row =>
              h('tr', headers.value.map(col => {
                const bc = badgeColor(col, row)
                const val = cellVal(row, col)
                const isTrunc = props.truncate.includes(col)
                if (bc) {
                  return h('td', h(VChip, { size: 'x-small', color: bc, label: true }, { default: () => val }))
                }
                if (isTrunc) {
                  return h('td', h('span', {
                    title: val,
                    style: 'display:inline-block;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;vertical-align:bottom;cursor:help;font-family:monospace;font-size:.78rem',
                  }, val))
                }
                return h('td', val)
              }))
            )),
          ],
        })
      )

      return h('div', nodes)
    }
  },
})
</script>
