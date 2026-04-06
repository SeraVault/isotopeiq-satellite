import axios from 'axios'
import { ref } from 'vue'

const api = axios.create({ baseURL: '/api' })

// Reactive auth state — components import this instead of reading localStorage
export const isLoggedIn = ref(!!localStorage.getItem('access_token'))

export function setTokens(access, refresh, username, isSuperuser) {
  localStorage.setItem('access_token', access)
  if (refresh) localStorage.setItem('refresh_token', refresh)
  if (isSuperuser !== undefined) localStorage.setItem('is_superuser', isSuperuser ? '1' : '')
  if (username) localStorage.setItem('username', username)
  isLoggedIn.value = true
}

export function clearTokens() {
  localStorage.removeItem('access_token')
  localStorage.removeItem('refresh_token')
  localStorage.removeItem('is_superuser')
  localStorage.removeItem('username')
  isLoggedIn.value = false
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Single in-flight refresh promise — prevents the 6 simultaneous dashboard
// poll requests from all trying to refresh the token at the same time.
let refreshPromise = null

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    if (error.response?.status === 401) {
      const refresh = localStorage.getItem('refresh_token')
      if (refresh && !error.config._retry) {
        error.config._retry = true
        if (!refreshPromise) {
          refreshPromise = axios.post('/api/token/refresh/', { refresh })
            .then(({ data }) => {
              setTokens(data.access, data.refresh || null)
              window.dispatchEvent(new CustomEvent('auth:tokenRefreshed'))
              return data.access
            })
            .catch((err) => {
              clearTokens()
              return Promise.reject(err)
            })
            .finally(() => {
              refreshPromise = null
            })
        }
        try {
          const access = await refreshPromise
          error.config.headers.Authorization = `Bearer ${access}`
          return api(error.config)
        } catch {
          return Promise.reject(error)
        }
      } else {
        clearTokens()
      }
    }
    return Promise.reject(error)
  }
)

export default api
