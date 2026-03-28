import { defineStore } from 'pinia'
import api from '../api'

const PAGE_SIZE = 50

export const useDriftStore = defineStore('drift', {
  state: () => ({
    events: [],
    loading: false,
    volatileFields: null,
    page: 1,
    totalCount: 0,
    totalPages: 1,
    lastParams: {},
  }),
  actions: {
    async fetchEvents(params = {}) {
      this.loading = true
      this.lastParams = params
      try {
        const { data } = await api.get('/drift/', { params: { page: this.page, page_size: PAGE_SIZE, ...params } })
        this.events = data.results ?? data
        this.totalCount = data.count ?? this.events.length
        this.totalPages = Math.max(1, Math.ceil(this.totalCount / PAGE_SIZE))
      } finally {
        this.loading = false
      }
    },
    goPage(n) {
      this.page = n
      this.fetchEvents(this.lastParams)
    },
    async fetchVolatileFields() {
      if (this.volatileFields) return
      const { data } = await api.get('/drift/volatile-fields/')
      this.volatileFields = data
    },
    async acknowledge(id, reason) {
      const { data } = await api.post(`/drift/${id}/acknowledge/`, { reason })
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
