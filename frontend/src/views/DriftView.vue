<template>
  <div>
    <h1>Drift Events</h1>
    <button @click="store.fetchEvents()">Refresh</button>

    <div v-if="store.loading">Loading…</div>
    <table v-else>
      <thead>
        <tr><th>Device</th><th>Status</th><th>Detected</th><th>Diff Keys</th><th>Actions</th></tr>
      </thead>
      <tbody>
        <tr v-for="event in store.events" :key="event.id">
          <td>{{ event.device }}</td>
          <td><span :class="`badge badge-${event.status}`">{{ event.status }}</span></td>
          <td>{{ new Date(event.created_at).toLocaleString() }}</td>
          <td>{{ Object.keys(event.diff).join(', ') || '—' }}</td>
          <td>
            <button @click="selected = event">View Diff</button>
            <button v-if="event.status === 'new'" @click="store.acknowledge(event.id)">Acknowledge</button>
            <button v-if="event.status !== 'resolved'" @click="store.resolve(event.id)">Resolve</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-if="!store.loading && !store.events.length">No drift events.</p>

    <div v-if="selected" class="modal">
      <div class="modal-box modal-md">
        <h2>Drift on {{ selected.device }}</h2>
        <p style="margin:.5rem 0"><span :class="`badge badge-${selected.status}`">{{ selected.status }}</span> &mdash; {{ new Date(selected.created_at).toLocaleString() }}</p>
        <pre>{{ JSON.stringify(selected.diff, null, 2) }}</pre>
        <div style="margin-top:1rem">
          <button @click="selected = null">Close</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useDriftStore } from '../stores/drift'

const store = useDriftStore()
const selected = ref(null)

onMounted(() => store.fetchEvents())
</script>
