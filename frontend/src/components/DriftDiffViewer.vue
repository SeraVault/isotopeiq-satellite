<template>
  <div class="drift-diff-viewer">
    <div class="diff-toolbar">
      <label class="toggle-label">
        <input type="checkbox" v-model="sideBySide" />
        Side by side
      </label>
      <label class="toggle-label" style="margin-left:.75rem">
        Context lines
        <select v-model="context" style="margin-left:.35rem;padding:.1rem .3rem;font-size:.8rem">
          <option :value="3">3</option>
          <option :value="10">10</option>
          <option :value="50">50</option>
          <option :value="999999">All</option>
        </select>
      </label>
      <label v-if="volatileFields" class="toggle-label" style="margin-left:.75rem">
        <input type="checkbox" v-model="hideVolatile" />
        Hide volatile fields
      </label>
      <span v-if="noChangesAnywhere" class="text-muted" style="margin-left:auto;font-size:.83rem">No differences detected</span>
    </div>

    <div class="sections">
      <div v-for="section in sections" :key="section.key" class="section-block">
        <button
          class="section-header"
          :class="{ 'section-header--changed': section.hasChanges, 'section-header--open': openSections.has(section.key) }"
          @click="toggle(section)"
        >
          <span class="section-chevron">{{ openSections.has(section.key) ? '▾' : '▸' }}</span>
          <span class="section-name">{{ section.key }}</span>
          <span v-if="section.hasChanges" class="badge badge-failed" style="margin-left:.5rem;font-size:.72rem">changed</span>
          <span v-else class="badge badge-success" style="margin-left:.5rem;font-size:.72rem">unchanged</span>
          <span v-if="section.large" class="text-muted" style="margin-left:.5rem;font-size:.75rem">(large — opens slowly)</span>
        </button>
        <div v-if="openSections.has(section.key)" class="section-body">
          <p v-if="!section.hasChanges" class="no-changes">No changes in this section.</p>
          <CodeDiff
            v-else
            :old-string="section.oldJson"
            :new-string="section.newJson"
            :output-format="sideBySide ? 'side-by-side' : 'line-by-line'"
            :context="context"
            language="json"
            theme="light"
            :highlight="true"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { CodeDiff } from 'v-code-diff'

const props = defineProps({
  baseline:       { type: Object, default: null },
  current:        { type: Object, default: null },
  volatileFields: { type: Object, default: null },
})

const sideBySide   = ref(true)
const context      = ref(10)
const hideVolatile = ref(true)

// Sections with many entries that will be slow to diff
const LARGE_SECTIONS = new Set(['sysctl', 'packages', 'installed_software', 'kernel_modules'])

function stripVolatile(data) {
  if (!props.volatileFields || !data) return data
  data = JSON.parse(JSON.stringify(data))
  for (const [section, spec] of Object.entries(props.volatileFields)) {
    if (!(section in data)) continue
    const sectionData = data[section]
    if (spec.fields && typeof sectionData === 'object' && !Array.isArray(sectionData)) {
      for (const f of spec.fields) delete sectionData[f]
    }
    if (spec.items && Array.isArray(sectionData)) {
      for (const item of sectionData)
        if (item && typeof item === 'object')
          for (const f of spec.items) delete item[f]
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

const strippedBaseline = computed(() =>
  hideVolatile.value ? stripVolatile(props.baseline) : props.baseline
)
const strippedCurrent = computed(() =>
  hideVolatile.value ? stripVolatile(props.current) : props.current
)

const sections = computed(() => {
  const base = strippedBaseline.value ?? {}
  const curr = strippedCurrent.value ?? {}
  const keys = new Set([...Object.keys(base), ...Object.keys(curr)])
  return [...keys].sort().map(key => {
    const oldJson = JSON.stringify(base[key] ?? null, null, 2)
    const newJson = JSON.stringify(curr[key] ?? null, null, 2)
    return {
      key,
      oldJson,
      newJson,
      hasChanges: oldJson !== newJson,
      large: LARGE_SECTIONS.has(key),
    }
  })
})

const noChangesAnywhere = computed(() => sections.value.every(s => !s.hasChanges))

// Auto-open sections that have changes, but not large ones
const openSections = ref(new Set())
const openedForDiff = ref(false)

// Watch for sections becoming available and auto-open changed non-large ones
import { watch } from 'vue'
watch(sections, (newSections) => {
  if (openedForDiff.value) return
  const changed = newSections.filter(s => s.hasChanges && !s.large)
  if (changed.length) {
    openSections.value = new Set(changed.map(s => s.key))
    openedForDiff.value = true
  }
}, { immediate: true })

function toggle(section) {
  const next = new Set(openSections.value)
  if (next.has(section.key)) next.delete(section.key)
  else next.add(section.key)
  openSections.value = next
}
</script>

<style scoped>
.drift-diff-viewer {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.diff-toolbar {
  display: flex;
  align-items: center;
  gap: .5rem;
  margin-bottom: .75rem;
  padding: .4rem .75rem;
  background: #f5f5f5;
  border-radius: 5px;
  border: 1px solid #e8e8e8;
  flex-shrink: 0;
  flex-wrap: wrap;
}
.toggle-label {
  display: flex;
  align-items: center;
  gap: .35rem;
  font-size: .83rem;
  cursor: pointer;
  user-select: none;
}
.sections {
  overflow-y: auto;
  max-height: 65vh;
  display: flex;
  flex-direction: column;
  gap: .35rem;
}
.section-block {
  border: 1px solid #e8e8e8;
  border-radius: 6px;
  overflow: hidden;
}
.section-header {
  width: 100%;
  display: flex;
  align-items: center;
  gap: .4rem;
  padding: .45rem .75rem;
  background: #fafafa;
  border: none;
  cursor: pointer;
  text-align: left;
  font-size: .85rem;
  font-weight: 600;
  color: #333;
  user-select: none;
}
.section-header:hover { background: #f0f0f0; }
.section-header--changed { background: #fff8f0; }
.section-header--changed:hover { background: #fef0e0; }
.section-chevron { font-size: .7rem; color: #888; width: .8rem; }
.section-name { text-transform: capitalize; letter-spacing: .01em; }
.section-body {
  border-top: 1px solid #e8e8e8;
}
.no-changes {
  padding: .5rem .75rem;
  font-size: .82rem;
  color: #888;
  margin: 0;
}
:deep(.d2h-wrapper),
:deep(.d2h-file-wrapper) {
  max-height: 50vh;
  overflow: auto;
}
</style>
