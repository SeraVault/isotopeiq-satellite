import axios from 'axios'
import { ref } from 'vue'

const api = axios.create({ baseURL: '/api' })

// Reactive auth state — components import this instead of reading localStorage
export const isLoggedIn = ref(!!localStorage.getItem('access_token'))

export function setTokens(access, refresh, username) {
  localStorage.setItem('access_token', access)
  if (refresh) localStorage.setItem('refresh_token', refresh)
  if (username) localStorage.setItem('username', username)
  isLoggedIn.value = true
}

export function clearTokens() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  localStorage.removeItem('username')
  isLoggedIn.value = false
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    if (error.response?.status === 401) {
      const refresh = localStorage.getItem('refresh_token')
      if (refresh && !error.config._retry) {
        error.config._retry = true
        try {
          const { data } = await axios.post('/api/token/refresh/', { refresh })
          setTokens(data.access, data.refresh || null)
          error.config.headers.Authorization = `Bearer ${data.access}`
          return api(error.config)
        } catch {
          clearTokens()
        }
      } else {
        clearTokens()
      }
    }
    return Promise.reject(error)
  }
)

export default api
