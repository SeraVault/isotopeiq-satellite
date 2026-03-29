<template>
  <div>
    <div class="d-flex align-center mb-5">
      <div>
        <div class="text-h5 font-weight-bold">Volatile Field Rules</div>
        <div class="text-caption text-medium-emphasis">
          Fields matching these rules are excluded from drift comparison.
          Changes take effect within 60 seconds on the next policy run.
        </div>
      </div>
      <v-spacer />
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
            placeholder="Why is this field volatile?"
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
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useVolatileRulesStore } from '../stores/volatileRules'

const store = useVolatileRulesStore()

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
