import { defineStore } from 'pinia'
import api from '../api'

export const useVolatileRulesStore = defineStore('volatileRules', {
  state: () => ({
    rules: [],
    loading: false,
    totalCount: 0,
    lastParams: {},
  }),
  actions: {
    async fetchRules(params = {}) {
      this.loading = true
      this.lastParams = params
      try {
        const { data } = await api.get('/drift/volatile-rules/', { params })
        this.rules = data.results ?? data
        this.totalCount = data.count ?? this.rules.length
      } finally {
        this.loading = false
      }
    },
    async createRule(payload) {
      const { data } = await api.post('/drift/volatile-rules/', payload)
      this.rules.unshift(data)
      this.totalCount++
      return data
    },
    async updateRule(id, payload) {
      const { data } = await api.patch(`/drift/volatile-rules/${id}/`, payload)
      const idx = this.rules.findIndex(r => r.id === id)
      if (idx !== -1) this.rules[idx] = data
      return data
    },
    async deleteRule(id) {
      await api.delete(`/drift/volatile-rules/${id}/`)
      this.rules = this.rules.filter(r => r.id !== id)
      this.totalCount--
    },
  },
})
