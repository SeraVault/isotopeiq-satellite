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
    _buildWsUrl() {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const token = localStorage.getItem('access_token') ?? ''
      return `${proto}://${location.host}/ws/jobs/?token=${encodeURIComponent(token)}`
    },

    connectWebSocket() {
      // Clean up any previous socket before opening a new one.
      if (this.ws) {
        this.ws.onclose = null
        this.ws.onerror = null
        this.ws.close()
        this.ws = null
      }

      this._wsActive = true
      this._wsRetryDelay = this._wsRetryDelay ?? 1000

      this.ws = new WebSocket(this._buildWsUrl())

      this.ws.onopen = () => {
        // Reset backoff on successful connection.
        this._wsRetryDelay = 1000
      }

      this.ws.onclose = () => {
        this.ws = null
        if (!this._wsActive) return
        // Back off exponentially, cap at 30 s.
        this._wsRetryTimer = setTimeout(() => {
          if (this._wsActive) this.connectWebSocket()
        }, this._wsRetryDelay)
        this._wsRetryDelay = Math.min(this._wsRetryDelay * 2, 30000)
      }

      this.ws.onerror = () => {
        // Let onclose handle the retry — just close cleanly.
        if (this.ws) this.ws.close()
      }

      // When the HTTP interceptor silently refreshes the access token, the
      // current WS is still authenticated with the old (now expired) token.
      // Reconnect immediately so the new token is picked up.
      if (!this._wsTokenListener) {
        this._wsTokenListener = () => {
          if (this._wsActive) {
            clearTimeout(this._wsRetryTimer)
            this._wsRetryDelay = 1000
            this.connectWebSocket()
          }
        }
        window.addEventListener('auth:tokenRefreshed', this._wsTokenListener)
      }

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
      this._wsActive = false
      clearTimeout(this._wsRetryTimer)
      if (this._wsTokenListener) {
        window.removeEventListener('auth:tokenRefreshed', this._wsTokenListener)
        this._wsTokenListener = null
      }
      if (this.ws) {
        this.ws.onclose = null
        this.ws.onerror = null
        this.ws.close()
        this.ws = null
      }
    },
  },
})
