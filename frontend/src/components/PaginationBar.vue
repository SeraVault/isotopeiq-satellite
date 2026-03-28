<template>
  <div v-if="totalPages > 1 || totalCount > 0" class="pagination-bar">
    <span class="pagination-count">{{ totalCount }} total</span>
    <div class="pagination-controls">
      <button :disabled="page <= 1" @click="$emit('go', page - 1)">← Prev</button>
      <span class="text-muted">Page {{ page }} of {{ totalPages }}</span>
      <button :disabled="page >= totalPages" @click="$emit('go', page + 1)">Next →</button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  page:       { type: Number, required: true },
  totalPages: { type: Number, required: true },
  totalCount: { type: Number, required: true },
})
defineEmits(['go'])
</script>

<style scoped>
.pagination-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: .75rem;
  font-size: .85rem;
}
.pagination-controls {
  display: flex;
  align-items: center;
  gap: .5rem;
}
.pagination-count {
  color: #888;
}
</style>
