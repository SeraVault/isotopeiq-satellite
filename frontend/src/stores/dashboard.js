import { defineStore } from 'pinia'
import api from '../api'

// Merge an incoming array into an existing reactive array in-place.
// Existing items are updated with Object.assign, new items are spliced in at
// the correct position, and removed items are spliced out — so Vue only
// patches the DOM rows that actually changed.
function mergeList(current, incoming, key = 'id') {
  const incomingIds = new Set(incoming.map(i => i[key]))
  // Remove stale rows (iterate backwards to keep indices stable)
  for (let i = current.length - 1; i >= 0; i--) {
    if (!incomingIds.has(current[i][key])) current.splice(i, 1)
  }
  // Update existing / insert new rows in order
  incoming.forEach((item, idx) => {
    const existing = current.findIndex(c => c[key] === item[key])
    if (existing !== -1) {
      Object.assign(current[existing], item)
    } else {
      current.splice(idx, 0, item)
    }
  })
}

export const useDashboardStore = defineStore('dashboard', {
  state: () => ({
    stats: { devices: 0, policies: 0, running_jobs: 0, new_drift: 0 },
    driftEvents: [],
    recentJobs: [],
    baselines: [],
    loading: false,
  }),
  actions: {
    async refresh() {
      // Only show the loading state on the initial fetch (lists are empty).
      // Background polls must not toggle `loading` or the template will
      // tear down and recreate the table on every tick.
      const initial = this.driftEvents.length === 0 && this.recentJobs.length === 0
      if (initial) this.loading = true
      try {
        const [devRes, polRes, runRes, bundleRunRes, driftRes, jobsRes, blRes] = await Promise.all([
          api.get('/devices/',   { params: { page_size: 1 } }),
          api.get('/policies/',  { params: { page_size: 1 } }),
          api.get('/jobs/',      { params: { status: 'running', page_size: 1 } }),
          api.get('/scripts/script-jobs/results/', { params: { status: 'running', page_size: 1 } }),
          api.get('/drift/',     { params: { status: 'new', page_size: 50 } }),
          api.get('/jobs/',      { params: { page_size: 20, ordering: '-started_at' } }),
          api.get('/baselines/', { params: { page_size: 100, ordering: '-established_at' } }),
        ])
        // Patch scalar stats in-place so stat card computeds don't needlessly re-run
        Object.assign(this.stats, {
          devices:      devRes.data.count   ?? 0,
          policies:     polRes.data.count   ?? 0,
          running_jobs: (runRes.data.count ?? 0) + (bundleRunRes.data.count ?? 0),
          new_drift:    driftRes.data.count ?? 0,
        })
        mergeList(this.driftEvents, driftRes.data.results ?? driftRes.data ?? [])
        mergeList(this.recentJobs,  jobsRes.data.results  ?? jobsRes.data  ?? [])
        mergeList(this.baselines,   blRes.data.results    ?? blRes.data    ?? [])
      } finally {
        this.loading = false
      }
    },
  },
})
