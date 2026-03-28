import { defineStore } from 'pinia'
import api from '../api'

const PAGE_SIZE = 50

export const useJobsStore = defineStore('jobs', {
  state: () => ({
    jobs: [],
    loading: false,
    ws: null,
    page: 1,
    totalCount: 0,
    totalPages: 1,
    lastParams: {},
  }),
  actions: {
    async fetchJobs(params = {}) {
      this.loading = true
      this.lastParams = params
      try {
        const { data } = await api.get('/jobs/', { params: { page: this.page, page_size: PAGE_SIZE, ...params } })
        this.jobs = data.results ?? data
        this.totalCount = data.count ?? this.jobs.length
        this.totalPages = Math.max(1, Math.ceil(this.totalCount / PAGE_SIZE))
      } finally {
        this.loading = false
      }
    },
    goPage(n) {
      this.page = n
      this.fetchJobs(this.lastParams)
    },
    connectWebSocket() {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const token = localStorage.getItem('access_token') ?? ''
      this.ws = new WebSocket(`${proto}://${location.host}/ws/jobs/?token=${encodeURIComponent(token)}`)
      this.ws.onmessage = (event) => {
        const update = JSON.parse(event.data)
        const idx = this.jobs.findIndex((j) => j.id === update.job_id)
        if (idx === -1) {
          // New job started while page was open — fetch it
          api.get(`/jobs/${update.job_id}/`).then(({ data }) => {
            this.jobs.unshift(data)
          }).catch(() => {})
          return
        }

        const job = { ...this.jobs[idx], status: update.status }
        if (update.policy_name) job.policy_name = update.policy_name
        job.current_device = update.current_device ?? null

        if (update.device_result) {
          const dr = update.device_result
          const results = [...(job.device_results ?? [])]
          const ri = results.findIndex((r) => r.id === dr.id)
          if (ri !== -1) results[ri] = { ...results[ri], ...dr }
          else results.push(dr)
          job.device_results = results
        }

        this.jobs[idx] = job
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
