import axios from 'axios'
import { useAuthStore } from '@/store/auth'

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL || '/api' })

let refreshing: Promise<void> | null = null

api.interceptors.request.use(cfg => {
  const auth = useAuthStore()
  if (auth.accessToken) (cfg.headers ||= {}).Authorization = `Bearer ${auth.accessToken}`
  return cfg
})

api.interceptors.response.use(
  r => r,
  async err => {
    const { response, config } = err || {}
    if (response?.status === 401 && !(config as any)?._retry) {
      const auth = useAuthStore()
      if (!auth.refreshToken) { auth.logout(); return Promise.reject(err) }
      ;(config as any)._retry = true
      refreshing ||= auth.refresh().catch(() => { /* no-op */ })
      await refreshing.finally(() => (refreshing = null))
      if (auth.accessToken) {
        (config.headers ||= {}).Authorization = `Bearer ${auth.accessToken}`
        return api(config) // rejoue la requête
      }
    }
    return Promise.reject(err)
  }
)

export default api
