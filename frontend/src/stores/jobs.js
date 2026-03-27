import { defineStore } from 'pinia'
import api from '../api'

export const useJobsStore = defineStore('jobs', {
  state: () => ({ jobs: [], loading: false, ws: null }),
  actions: {
    async fetchJobs(params = {}) {
      this.loading = true
      try {
        const { data } = await api.get('/jobs/', { params })
        this.jobs = data.results ?? data
      } finally {
        this.loading = false
      }
    },
    connectWebSocket() {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const token = localStorage.getItem('access_token') ?? ''
      this.ws = new WebSocket(`${proto}://${location.host}/ws/jobs/?token=${encodeURIComponent(token)}`)
      this.ws.onmessage = (event) => {
        const update = JSON.parse(event.data)
        const idx = this.jobs.findIndex((j) => j.id === update.job_id)
        if (idx !== -1) {
          this.jobs[idx] = { ...this.jobs[idx], status: update.status }
        }
      }
    },
    disconnectWebSocket() {
      if (this.ws) {
        this.ws.close()
        this.ws = null
      }
    },
  },
})
