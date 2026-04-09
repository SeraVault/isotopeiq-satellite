<template>
  <v-autocomplete
    :model-value="modelValue"
    :label="label"
    :items="items"
    item-title="title"
    item-value="value"
    :loading="loading"
    :clearable="clearable"
    no-filter
    v-bind="$attrs"
    @update:model-value="onSelect"
    @update:search="onSearch"
  />
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '../api'

const props = defineProps({
  modelValue: { default: null },
  label:      { type: String, default: 'Device' },
  clearable:  { type: Boolean, default: true },
})
const emit = defineEmits(['update:modelValue'])

const devices  = ref([])
const loading  = ref(false)
const selected = ref(null) // { title, value } of the current selection

const items = computed(() => {
  const list = devices.value.map(d => ({ title: d.name, value: d.id }))
  // Keep the selected item present even when the user types a search that doesn't match it
  if (selected.value && !list.find(i => i.value === selected.value.value)) {
    list.unshift(selected.value)
  }
  return list
})

let searchTimer = null

function onSearch(val) {
  clearTimeout(searchTimer)
  // Don't re-search if the user just selected an item (val === item title)
  if (val === selected.value?.title) return
  loading.value = true
  searchTimer = setTimeout(async () => {
    try {
      const { data } = await api.get('/devices/', { params: { search: val || '', page_size: 50 } })
      devices.value = data.results ?? data
    } finally {
      loading.value = false
    }
  }, 300)
}

function onSelect(val) {
  if (val) {
    selected.value = items.value.find(i => i.value === val) ?? null
  } else {
    selected.value = null
  }
  emit('update:modelValue', val)
}

onMounted(async () => {
  loading.value = true
  try {
    const { data } = await api.get('/devices/', { params: { page_size: 50 } })
    devices.value = data.results ?? data
    // If a value is already selected, ensure it's in our list
    if (props.modelValue) {
      const found = devices.value.find(d => d.id === props.modelValue)
      if (found) {
        selected.value = { title: found.name, value: found.id }
      } else {
        // Fetch just this device to show its name
        const { data: d } = await api.get(`/devices/${props.modelValue}/`)
        selected.value = { title: d.name, value: d.id }
      }
    }
  } finally {
    loading.value = false
  }
})
</script>
