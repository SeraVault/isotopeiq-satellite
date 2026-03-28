import { defineStore } from 'pinia'
import api from '../api'

const PAGE_SIZE = 50

export const useDevicesStore = defineStore('devices', {
  state: () => ({
    devices: [],
    loading: false,
    error: null,
    page: 1,
    totalCount: 0,
    totalPages: 1,
    lastParams: {},
  }),
  actions: {
    async fetchDevices(params = {}) {
      this.loading = true
      this.lastParams = params
      try {
        const { data } = await api.get('/devices/', { params: { page: this.page, page_size: PAGE_SIZE, ...params } })
        this.devices = data.results ?? data
        this.totalCount = data.count ?? this.devices.length
        this.totalPages = Math.max(1, Math.ceil(this.totalCount / PAGE_SIZE))
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },
    goPage(n) {
      this.page = n
      this.fetchDevices(this.lastParams)
    },
    async createDevice(payload) {
      const { data } = await api.post('/devices/', payload)
      this.devices.unshift(data)
      this.totalCount++
      return data
    },
    async updateDevice(id, payload) {
      const { data } = await api.patch(`/devices/${id}/`, payload)
      const idx = this.devices.findIndex((d) => d.id === id)
      if (idx !== -1) this.devices[idx] = data
      return data
    },
    async deleteDevice(id) {
      await api.delete(`/devices/${id}/`)
      this.devices = this.devices.filter((d) => d.id !== id)
      this.totalCount--
    },
  },
})
