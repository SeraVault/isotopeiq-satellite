<template>
  <div class="cv">

    <!-- ── Device + Hardware + OS (summary cards) ───────────────────────── -->
    <div class="cv-summary-row">
      <div class="cv-summary-card" v-if="d.device && anyValues(d.device)">
        <div class="cv-card-title">Device</div>
        <kv :data="d.device" />
      </div>
      <div class="cv-summary-card" v-if="d.hardware && anyValues(d.hardware)">
        <div class="cv-card-title">Hardware</div>
        <kv :data="d.hardware" />
      </div>
      <div class="cv-summary-card" v-if="d.os && anyValues(d.os)">
        <div class="cv-card-title">OS</div>
        <kv :data="d.os" />
      </div>
      <div class="cv-summary-card" v-if="d.security && anyValues(d.security)">
        <div class="cv-card-title">Security</div>
        <kv :data="flatSecurity(d.security)" />
      </div>
    </div>

    <!-- ── Network ───────────────────────────────────────────────────────── -->
    <section-block title="Network" :count="(d.network?.interfaces?.length ?? 0)" v-if="d.network">
      <template v-if="d.network.default_gateway">
        <div class="cv-meta-line">Default gateway: <strong>{{ d.network.default_gateway }}</strong></div>
      </template>
      <template v-if="d.network.dns_servers?.length">
        <div class="cv-meta-line">DNS: <strong>{{ d.network.dns_servers.join(', ') }}</strong></div>
      </template>
      <cv-table
        v-if="d.network.interfaces?.length"
        :rows="d.network.interfaces"
        :cols="['name','mac','ipv4','ipv6','admin_status','oper_status','speed','mtu']"
        :format="{ ipv4: arr => arr?.join(', '), ipv6: arr => arr?.join(', ') }"
      />
      <cv-table
        v-if="d.network.routes?.length"
        title="Routes"
        :rows="d.network.routes"
        :cols="['destination','gateway','interface','metric']"
      />
      <cv-table
        v-if="d.network.hosts_file?.length"
        title="Hosts File"
        :rows="d.network.hosts_file"
        :cols="['ip','hostname']"
      />
    </section-block>

    <!-- ── Users ─────────────────────────────────────────────────────────── -->
    <section-block title="Users" :count="d.users?.length" v-if="d.users?.length">
      <cv-table
        :rows="d.users"
        :cols="['username','uid','shell','home','groups','sudo_privileges','disabled','last_login']"
        :format="{ groups: arr => arr?.join(', '), disabled: v => v === true ? 'Yes' : v === false ? 'No' : '' }"
        searchable
      />
    </section-block>

    <!-- ── Groups ────────────────────────────────────────────────────────── -->
    <section-block title="Groups" :count="d.groups?.length" v-if="d.groups?.length">
      <cv-table
        :rows="d.groups"
        :cols="['group_name','gid','members']"
        :format="{ members: arr => arr?.join(', ') }"
        searchable
      />
    </section-block>

    <!-- ── Packages ──────────────────────────────────────────────────────── -->
    <section-block title="Packages" :count="d.packages?.length" v-if="d.packages?.length">
      <cv-table
        :rows="d.packages"
        :cols="['name','version','vendor','source','install_date']"
        searchable
      />
    </section-block>

    <!-- ── Installed Software ────────────────────────────────────────────── -->
    <section-block title="Installed Software" :count="d.installed_software?.length" v-if="d.installed_software?.length">
      <cv-table
        :rows="d.installed_software"
        :cols="['name','version','vendor','source','install_date']"
        searchable
      />
    </section-block>

    <!-- ── Services ──────────────────────────────────────────────────────── -->
    <section-block title="Services" :count="d.services?.length" v-if="d.services?.length">
      <cv-table
        :rows="d.services"
        :cols="['name','status','startup']"
        :badges="{ status: { running: 'success', stopped: 'failed', unknown: 'pending' }, startup: { enabled: 'success', disabled: 'partial', manual: 'pending', unknown: 'pending' } }"
        searchable
      />
    </section-block>

    <!-- ── Filesystem ────────────────────────────────────────────────────── -->
    <section-block title="Filesystem" :count="d.filesystem?.length" v-if="d.filesystem?.length">
      <cv-table
        :rows="d.filesystem"
        :cols="['mount','type','size_gb','free_gb','mount_options']"
        :format="{ mount_options: arr => arr?.join(', '), size_gb: v => v != null ? v + ' GB' : '', free_gb: v => v != null ? v + ' GB' : '' }"
      />
    </section-block>

    <!-- ── Listening Services ────────────────────────────────────────────── -->
    <section-block title="Listening Services" :count="d.listening_services?.length" v-if="d.listening_services?.length">
      <cv-table
        :rows="d.listening_services"
        :cols="['port','protocol','local_address','process_name','pid','user']"
        searchable
      />
    </section-block>

    <!-- ── Firewall Rules ────────────────────────────────────────────────── -->
    <section-block title="Firewall Rules" :count="d.firewall_rules?.length" v-if="d.firewall_rules?.length">
      <cv-table
        :rows="d.firewall_rules"
        :cols="['chain','direction','action','protocol','source','destination','port','source_tool']"
        searchable
      />
    </section-block>

    <!-- ── SSH Keys ───────────────────────────────────────────────────────── -->
    <section-block title="SSH Authorized Keys" :count="d.ssh_keys?.length" v-if="d.ssh_keys?.length">
      <cv-table
        :rows="d.ssh_keys"
        :cols="['username','key_type','comment','public_key']"
        :truncate="['public_key']"
      />
    </section-block>

    <!-- ── SSH Config ─────────────────────────────────────────────────────── -->
    <section-block title="SSH Config" v-if="d.ssh_config && anyValues(d.ssh_config)">
      <kv :data="d.ssh_config" />
    </section-block>

    <!-- ── Scheduled Tasks ───────────────────────────────────────────────── -->
    <section-block title="Scheduled Tasks" :count="d.scheduled_tasks?.length" v-if="d.scheduled_tasks?.length">
      <cv-table
        :rows="d.scheduled_tasks"
        :cols="['name','type','user','schedule','command','enabled']"
        :format="{ enabled: v => v === true ? 'Yes' : v === false ? 'No' : '' }"
        searchable
      />
    </section-block>

    <!-- ── Kernel Modules ────────────────────────────────────────────────── -->
    <section-block title="Kernel Modules" :count="d.kernel_modules?.length" v-if="d.kernel_modules?.length">
      <cv-table
        :rows="d.kernel_modules"
        :cols="['name','type','description','signed']"
        :format="{ signed: v => v === true ? 'Yes' : v === false ? 'No' : '' }"
        searchable
      />
    </section-block>

    <!-- ── Sysctl ─────────────────────────────────────────────────────────── -->
    <section-block title="Sysctl" :count="d.sysctl?.length" v-if="d.sysctl?.length" :collapsed="true">
      <cv-table
        :rows="d.sysctl"
        :cols="['key','value']"
        searchable
      />
    </section-block>

    <!-- ── Certificates ───────────────────────────────────────────────────── -->
    <section-block title="Certificates" :count="d.certificates?.length" v-if="d.certificates?.length">
      <cv-table
        :rows="d.certificates"
        :cols="['subject','issuer','not_before','not_after','store','thumbprint']"
        :truncate="['thumbprint']"
        searchable
      />
    </section-block>

    <!-- ── VPN Tunnels ────────────────────────────────────────────────────── -->
    <section-block title="VPN Tunnels" :count="d.vpn_tunnels?.length" v-if="d.vpn_tunnels?.length">
      <cv-table
        :rows="d.vpn_tunnels"
        :cols="['name','type','local_address','remote_address','status','auth_method']"
        :badges="{ status: { up: 'success', down: 'failed', unknown: 'pending' } }"
      />
    </section-block>

    <!-- ── Shares ─────────────────────────────────────────────────────────── -->
    <section-block title="Shares" :count="d.shares?.length" v-if="d.shares?.length">
      <cv-table
        :rows="d.shares"
        :cols="['name','type','path','permissions','read_only','enabled']"
        :format="{ read_only: v => v === true ? 'Yes' : v === false ? 'No' : '', enabled: v => v === true ? 'Yes' : v === false ? 'No' : '' }"
      />
    </section-block>

    <!-- ── Logging Targets ───────────────────────────────────────────────── -->
    <section-block title="Logging Targets" :count="d.logging_targets?.length" v-if="d.logging_targets?.length">
      <cv-table
        :rows="d.logging_targets"
        :cols="['destination','type','protocol','facility','enabled']"
        :format="{ enabled: v => v === true ? 'Yes' : v === false ? 'No' : '' }"
      />
    </section-block>

    <!-- ── VLANs ──────────────────────────────────────────────────────────── -->
    <section-block title="VLANs" :count="d.vlans?.length" v-if="d.vlans?.length">
      <cv-table :rows="d.vlans" :cols="['id','name','state']" />
    </section-block>

    <!-- ── Routing Protocols ─────────────────────────────────────────────── -->
    <section-block title="Routing Protocols" :count="d.routing_protocols?.length" v-if="d.routing_protocols?.length">
      <cv-table
        :rows="d.routing_protocols"
        :cols="['protocol','instance','router_id','networks']"
        :format="{ networks: arr => arr?.join(', ') }"
      />
    </section-block>

    <!-- ── Custom ─────────────────────────────────────────────────────────── -->
    <section-block title="Custom" v-if="d.custom && anyValues(d.custom)">
      <kv :data="d.custom" />
    </section-block>

  </div>
</template>

<script setup>
import { ref, computed, defineComponent, h } from 'vue'

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
    Object.entries(password_policy).forEach(([k, v]) => {
      flat[`policy_${k}`] = v
    })
  }
  return flat
}

// ── KeyValue sub-component ────────────────────────────────────────────────────
const kv = defineComponent({
  props: { data: Object },
  setup(props) {
    function fmt(v) {
      if (v === null || v === undefined) return ''
      if (typeof v === 'boolean') return v ? 'Yes' : 'No'
      if (Array.isArray(v)) return v.join(', ')
      return String(v)
    }
    function label(k) {
      return k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
    }
    return () => h('dl', { class: 'cv-kv' },
      Object.entries(props.data ?? {})
        .filter(([, v]) => v !== null && v !== undefined && v !== '')
        .map(([k, v]) => [
          h('dt', label(k)),
          h('dd', fmt(v)),
        ]).flat()
    )
  },
})

// ── SectionBlock sub-component ────────────────────────────────────────────────
const sectionBlock = defineComponent({
  props: {
    title: String,
    count: { type: Number, default: null },
    collapsed: { type: Boolean, default: true },
  },
  setup(props, { slots }) {
    const open = ref(!props.collapsed)
    return () => h('div', { class: 'cv-section' }, [
      h('div', {
        class: 'cv-section-header',
        onClick: () => { open.value = !open.value },
      }, [
        h('span', { class: 'cv-section-toggle' }, open.value ? '▾' : '▸'),
        h('span', { class: 'cv-section-title' }, props.title),
        props.count != null
          ? h('span', { class: 'cv-section-count' }, props.count)
          : null,
      ]),
      open.value ? h('div', { class: 'cv-section-body' }, slots.default?.()) : null,
    ])
  },
})

// ── CvTable sub-component ─────────────────────────────────────────────────────
const cvTable = defineComponent({
  props: {
    rows:      { type: Array,  default: () => [] },
    cols:      { type: Array,  default: null },       // null = auto from first row
    title:     { type: String, default: null },
    format:    { type: Object, default: () => ({}) }, // col -> fn(value)
    badges:    { type: Object, default: () => ({}) }, // col -> { value: badgeClass }
    truncate:  { type: Array,  default: () => [] },   // cols to truncate
    searchable:{ type: Boolean, default: false },
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
      if (v === null || v === undefined) return ''
      if (typeof v === 'boolean') return v ? 'Yes' : 'No'
      if (Array.isArray(v)) return v.join(', ')
      return String(v)
    }

    function badgeClass(col, row) {
      if (!props.badges[col]) return null
      const raw = row[col]
      return props.badges[col][raw] ?? null
    }

    function label(k) {
      return k.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
    }

    return () => {
      const nodes = []

      if (props.title) {
        nodes.push(h('div', { class: 'cv-table-title' }, props.title))
      }

      if (props.searchable) {
        nodes.push(h('input', {
          class: 'cv-search',
          placeholder: 'Filter…',
          value: search.value,
          onInput: e => { search.value = e.target.value },
        }))
      }

      if (!filtered.value.length) {
        nodes.push(h('p', { class: 'text-muted', style: 'padding:.5rem 0' }, 'No entries.'))
        return h('div', nodes)
      }

      nodes.push(
        h('table', [
          h('thead', h('tr',
            headers.value.map(col => h('th', label(col)))
          )),
          h('tbody',
            filtered.value.map(row =>
              h('tr',
                headers.value.map(col => {
                  const bc = badgeClass(col, row)
                  const val = cellVal(row, col)
                  const isTrunc = props.truncate.includes(col)
                  return h('td',
                    bc
                      ? h('span', { class: `badge badge-${bc}` }, val)
                      : isTrunc
                        ? h('span', { class: 'cv-trunc', title: val }, val)
                        : val
                  )
                })
              )
            )
          ),
        ])
      )

      return h('div', nodes)
    }
  },
})
</script>

<style scoped>
.cv {
  display: flex;
  flex-direction: column;
  gap: 0;
  font-size: .875rem;
}

/* ── Summary cards ──────────────────────────────────────────────────────── */
.cv-summary-row {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: .75rem;
  margin-bottom: 1rem;
}
.cv-summary-card {
  background: #16213e;
  border-radius: 10px;
  padding: 1rem 1.1rem;
  box-shadow: 0 2px 8px rgba(0,0,0,.18);
  border: 1px solid rgba(79,195,247,.15);
}
.cv-card-title {
  font-size: .68rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .1em;
  color: #4fc3f7;
  margin-bottom: .6rem;
  padding-bottom: .4rem;
  border-bottom: 1px solid rgba(79,195,247,.2);
}

/* ── Key-value (inside summary cards) ──────────────────────────────────── */
.cv-kv {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: .2rem .75rem;
  font-size: .82rem;
}
.cv-kv :global(dt) {
  color: #7a9abf;
  white-space: nowrap;
  font-weight: 500;
}
.cv-kv :global(dd) {
  color: #c8d8f0;
  word-break: break-word;
}

/* ── Sections ───────────────────────────────────────────────────────────── */
.cv-section {
  border: 1px solid #e8edf2;
  border-radius: 8px;
  margin-bottom: .4rem;
  background: #fff;
  overflow: hidden;
  box-shadow: 0 1px 2px rgba(0,0,0,.04);
}
.cv-section-header {
  display: flex;
  align-items: center;
  gap: .6rem;
  padding: .6rem 1rem;
  cursor: pointer;
  user-select: none;
  background: linear-gradient(to right, #f7f9fc, #f0f4f8);
  border-bottom: 1px solid transparent;
  transition: background .12s;
}
.cv-section-header:hover {
  background: linear-gradient(to right, #eaf4fd, #dff0fb);
}
.cv-section-toggle {
  color: #4fc3f7;
  font-size: .8rem;
  width: .9rem;
  flex-shrink: 0;
  transition: transform .15s;
}
.cv-section-title {
  font-weight: 600;
  font-size: .88rem;
  color: #1a2a4a;
  flex: 1;
}
.cv-section-count {
  background: #e0f3fd;
  color: #0d7ab5;
  font-size: .7rem;
  font-weight: 700;
  padding: .15rem .5rem;
  border-radius: 999px;
  letter-spacing: .02em;
}
.cv-section-body {
  padding: .85rem 1rem 1rem;
  background: #fff;
  border-top: 1px solid #eef1f5;
}
.cv-meta-line {
  font-size: .84rem;
  margin-bottom: .45rem;
  color: #556;
}

/* ── Tables ─────────────────────────────────────────────────────────────── */
.cv-table-wrap { overflow-x: auto; margin-top: .25rem; }

.cv-table-title {
  font-size: .72rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: .07em;
  color: #7a9abf;
  margin: 1rem 0 .4rem;
  padding-left: .1rem;
}

/* ── Search ─────────────────────────────────────────────────────────────── */
.cv-search {
  display: block;
  width: 100%;
  max-width: 280px;
  padding: .32rem .65rem;
  border: 1px solid #cdd5df;
  border-radius: 5px;
  font-size: .83rem;
  margin-bottom: .6rem;
  background: #f8fafc;
  color: #2a3a50;
  transition: border-color .15s, box-shadow .15s;
}
.cv-search:focus {
  outline: none;
  border-color: #4fc3f7;
  box-shadow: 0 0 0 2px rgba(79,195,247,.18);
  background: #fff;
}

/* ── Truncated cells ────────────────────────────────────────────────────── */
.cv-trunc {
  display: inline-block;
  max-width: 180px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: bottom;
  cursor: help;
  color: #7a9abf;
  font-family: monospace;
  font-size: .78rem;
}
</style>
