<template>
  <div class="drift-diff-viewer">
    <div class="d-flex align-center flex-wrap ga-4 mb-3 pa-3 rounded-lg" style="background:#f5f5f5;border:1px solid #e8e8e8">
      <v-checkbox v-model="sideBySide" label="Side by side" density="compact" hide-details />
      <v-select
        v-model="context"
        label="Context lines"
        :items="[{title:'3',value:3},{title:'10',value:10},{title:'50',value:50},{title:'All',value:999999}]"
        item-title="title"
        item-value="value"
        density="compact"
        variant="outlined"
        hide-details
        style="max-width:130px"
      />
      <v-checkbox v-if="volatileFields" v-model="hideVolatile" label="Hide volatile fields" density="compact" hide-details />
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
