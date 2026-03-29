import { defineStore } from 'pinia'
import api from '../api'
import { useDashboardStore } from './dashboard'

export const useDriftStore = defineStore('drift', {
  state: () => ({
    events: [],
    loading: false,
    volatileFields: null,
    totalCount: 0,
    lastParams: {},
    _pollTimer: null,
  }),
  actions: {
    async fetchEvents(params = {}) {
      if (this.events.length === 0) this.loading = true
      this.lastParams = params
      try {
        const { data } = await api.get('/drift/', { params })
        this.events = data.results ?? data
        this.totalCount = data.count ?? this.events.length
      } finally {
        this.loading = false
      }
    },
    async fetchVolatileFields() {
      if (this.volatileFields) return
      const { data } = await api.get('/drift/volatile-fields/')
      this.volatileFields = data
    },
    async acknowledge(id, reason) {
      const { data } = await api.post(`/drift/${id}/acknowledge/`, { reason })
      const idx = this.events.findIndex((e) => e.id === id)
      if (idx !== -1) {
        const wasNew = this.events[idx].status === 'new'
        this.events[idx] = data
        if (wasNew && data.status !== 'new') {
          const db = useDashboardStore()
          db.stats.new_drift = Math.max(0, db.stats.new_drift - 1)
        }
      }
    },
    async resolve(id) {
      const { data } = await api.post(`/drift/${id}/resolve/`)
      const idx = this.events.findIndex((e) => e.id === id)
      if (idx !== -1) {
        const wasNew = this.events[idx].status === 'new'
        this.events[idx] = data
        if (wasNew && data.status !== 'new') {
          const db = useDashboardStore()
          db.stats.new_drift = Math.max(0, db.stats.new_drift - 1)
        }
      }
    },

    startPolling() {
      this.stopPolling()
      this._pollTimer = setInterval(() => this.fetchEvents(this.lastParams), 3000)
    },
    stopPolling() {
      if (this._pollTimer) { clearInterval(this._pollTimer); this._pollTimer = null }
    },
  },
})

