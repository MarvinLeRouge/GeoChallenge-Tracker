import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { useAuthStore } from '@/store/auth'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  withCredentials: false,
})

let refreshPromise: Promise<void> | null = null

// Attach Authorization (restore from sessionStorage if needed)
api.interceptors.request.use((config) => {
  const auth = useAuthStore()

  if (!auth.accessToken) {
    const cached = sessionStorage.getItem('access_token') || ''
    if (cached) auth.accessToken = cached
  }
  if (auth.accessToken) {
    (config.headers ??= {}).Authorization = `Bearer ${auth.accessToken}`
  }
  return config
})

// Lazy refresh on 401, single-flight, then replay
api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError) => {
    const resp = error.response
    const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined

    if (resp?.status === 401 && original && !original._retry) {
      // don't loop on refresh endpoint
      if (original.url?.includes('/auth/refresh')) {
        useAuthStore().logout()
        return Promise.reject(error)
      }

      const auth = useAuthStore()
      if (!auth.refreshToken) {
        auth.logout()
        return Promise.reject(error)
      }

      original._retry = true

      if (!refreshPromise) {
        refreshPromise = auth.refresh().finally(() => {
          refreshPromise = null
        })
      }

      try {
        await refreshPromise
        if (auth.accessToken) {
          (original.headers ??= {}).Authorization = `Bearer ${auth.accessToken}`
        }
        return api(original)
      } catch (e) {
        useAuthStore().logout()
        return Promise.reject(e)
      }
    }

    return Promise.reject(error)
  }
)

export default api
