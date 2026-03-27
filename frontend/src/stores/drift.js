import { defineStore } from 'pinia'
import api from '../api'

export const useDriftStore = defineStore('drift', {
  state: () => ({ events: [], loading: false }),
  actions: {
    async fetchEvents() {
      this.loading = true
      try {
        const { data } = await api.get('/drift/')
        this.events = data.results ?? data
      } finally {
        this.loading = false
      }
    },
    async acknowledge(id) {
      const { data } = await api.post(`/drift/${id}/acknowledge/`)
      const idx = this.events.findIndex((e) => e.id === id)
      if (idx !== -1) this.events[idx] = data
    },
    async resolve(id) {
      const { data } = await api.post(`/drift/${id}/resolve/`)
      const idx = this.events.findIndex((e) => e.id === id)
      if (idx !== -1) this.events[idx] = data
    },
  },
})
