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
    </div>

    <div class="diff-body">
      <CodeDiff
        :old-string="oldJson"
        :new-string="newJson"
        :output-format="sideBySide ? 'side-by-side' : 'line-by-line'"
        :context="context"
        language="json"
        theme="light"
        :highlight="true"
      />
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

const oldJson = computed(() => {
  const data = hideVolatile.value ? stripVolatile(props.baseline) : props.baseline
  return JSON.stringify(data ?? {}, null, 2)
})

const newJson = computed(() => {
  const data = hideVolatile.value ? stripVolatile(props.current) : props.current
  return JSON.stringify(data ?? {}, null, 2)
})
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
.diff-body {
  overflow: auto;
  max-height: 65vh;
}
:deep(.d2h-wrapper),
:deep(.d2h-file-wrapper) {
  max-height: none;
  overflow: visible;
}
</style>
