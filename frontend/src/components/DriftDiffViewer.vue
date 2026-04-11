<template>
  <div>
    <div v-if="volatileFields" class="mb-3">
      <v-checkbox v-model="hideVolatile" label="Hide excluded fields" density="compact" hide-details />
    </div>
    <CanonicalDiffViewer
      :baseline="filteredBaseline"
      :current="filteredCurrent"
      :allow-ignore="true"
      @ignore-field="onIgnoreField"
    />
    <v-snackbar v-model="snackbar.show" :color="snackbar.color" timeout="4000" location="bottom right">
      {{ snackbar.msg }}
      <template #actions>
        <v-btn variant="text" @click="snackbar.show = false">Dismiss</v-btn>
      </template>
    </v-snackbar>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import api from '../api'
import CanonicalDiffViewer from './CanonicalDiffViewer.vue'

const props = defineProps({
  baseline:       { type: Object, default: null },
  current:        { type: Object, default: null },
  volatileFields: { type: Object, default: null },
})

const emit = defineEmits(['rule-created'])

const hideVolatile = ref(true)
const snackbar = ref({ show: false, msg: '', color: 'success' })

async function onIgnoreField({ section, spec_type, field_name, aux }) {
  try {
    await api.post('/drift/volatile-rules/', { section, spec_type, field_name, aux, is_active: true })
    snackbar.value = {
      show: true,
      color: 'success',
      msg: spec_type === 'exclude_section'
        ? `Drift exclusion added: ${section} — entire section`
        : spec_type === 'exclude_key'
          ? `Drift exclusion added: ${section} [${field_name}]`
          : `Drift exclusion added: ${section} › ${field_name}`,
    }
    emit('rule-created')
  } catch (e) {
    const detail = e.response?.data?.non_field_errors?.[0]
      ?? e.response?.data?.detail
      ?? 'Failed to create rule'
    snackbar.value = { show: true, color: 'error', msg: detail }
  }
}

function stripVolatile(data) {
  if (!props.volatileFields || !data) return data
  data = JSON.parse(JSON.stringify(data))
  for (const [section, spec] of Object.entries(props.volatileFields)) {
    if (!(section in data)) continue
    if (spec.exclude_section) {
      delete data[section]
      continue
    }
    const sectionData = data[section]
    if (spec.fields && typeof sectionData === 'object' && !Array.isArray(sectionData)) {
      for (const f of spec.fields) delete sectionData[f]
    }
    if (spec.items && Array.isArray(sectionData)) {
      for (const item of sectionData)
        if (item && typeof item === 'object')
          for (const f of spec.items) delete item[f]
    }
    if (spec.exclude_keys && Array.isArray(sectionData)) {
      const { key_field, values } = spec.exclude_keys
      data[section] = sectionData.filter(item => !values.includes(item?.[key_field]))
    }
    if (spec.exclude_key_prefixes && Array.isArray(data[section])) {
      const { key_field, prefixes } = spec.exclude_key_prefixes
      data[section] = data[section].filter(item =>
        !prefixes.some(p => String(item?.[key_field] ?? '').startsWith(p))
      )
    }
    if (spec.nested) {
      const items = Array.isArray(sectionData) ? sectionData : [sectionData]
      for (const item of items) {
        if (!item || typeof item !== 'object') continue
        for (const [nestedKey, nestedFields] of Object.entries(spec.nested))
          for (const nested of (item[nestedKey] ?? []))
            if (nested && typeof nested === 'object')
              for (const f of nestedFields) delete nested[f]
      }
    }
  }
  return data
}

const filteredBaseline = computed(() =>
  hideVolatile.value ? stripVolatile(props.baseline) : props.baseline
)
const filteredCurrent = computed(() =>
  hideVolatile.value ? stripVolatile(props.current) : props.current
)
</script>
