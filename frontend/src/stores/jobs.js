import { defineStore } from 'pinia'
import api from '../api'

export const useJobsStore = defineStore('jobs', {
  state: () => ({
    jobs: [],
    loading: false,
    totalCount: 0,
    lastParams: {},
    _pollTimer: null,
  }),
  actions: {
    async fetchJobs(params = {}) {
      if (this.jobs.length === 0) this.loading = true
      this.lastParams = params
      try {
        const { data } = await api.get('/jobs/', { params })
        this.jobs = data.results ?? data
        this.totalCount = data.count ?? this.jobs.length
      } finally {
        this.loading = false
      }
    },
    startPolling() {
      this.stopPolling()
      this._pollTimer = setInterval(() => this.fetchJobs(this.lastParams), 3000)
    },
    stopPolling() {
      if (this._pollTimer) {
        clearInterval(this._pollTimer)
        this._pollTimer = null
      }
    },
  },
})
