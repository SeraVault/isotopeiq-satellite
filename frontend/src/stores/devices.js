import { defineStore } from 'pinia'
import api from '../api'

export const useDevicesStore = defineStore('devices', {
  state: () => ({ devices: [], loading: false, error: null }),
  actions: {
    async fetchDevices() {
      this.loading = true
      try {
        const { data } = await api.get('/devices/')
        this.devices = data.results ?? data
      } catch (e) {
        this.error = e.message
      } finally {
        this.loading = false
      }
    },
    async createDevice(payload) {
      const { data } = await api.post('/devices/', payload)
      this.devices.push(data)
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
    },
  },
})
