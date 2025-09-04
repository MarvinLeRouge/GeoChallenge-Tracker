import { defineStore } from 'pinia'
import api from '@/api/http'

type Tokens = { access_token: string; refresh_token?: string }
type LoginPayload = { identifier: string; password: string }

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: '' as string,
    refreshToken: (localStorage.getItem('refresh_token') || '') as string,
    user: null as any,
    initialized: false,
  }),
  getters: { isAuthenticated: s => !!s.accessToken },
  actions: {
    setTokens(tokens: Tokens) {
      this.accessToken = tokens.access_token || ''
      if (tokens.refresh_token) {
        this.refreshToken = tokens.refresh_token
        localStorage.setItem('refresh_token', tokens.refresh_token)
      }
    },
    async login({ identifier, password }: LoginPayload) {
      const body = new URLSearchParams()
      body.set('username', identifier) // email OU username
      body.set('password', password)
      const { data } = await api.post<Tokens>('/auth/login', body, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
      })
      this.setTokens(data)
      await this.fetchMe().catch(() => {})
    },
    async refresh() {
      if (!this.refreshToken) throw new Error('no refresh')
      const { data } = await api.post<Tokens>('/auth/refresh', { refresh_token: this.refreshToken })
      this.setTokens(data)
    },
    async fetchMe() {
      const { data } = await api.get('/my/profile/location')
      this.user = data
    },
    logout() {
      this.accessToken = ''
      this.refreshToken = ''
      this.user = null
      localStorage.removeItem('refresh_token')
    },
    async init() {
      if (this.initialized) return
      this.initialized = true
      if (this.refreshToken) {
        try { await this.refresh(); await this.fetchMe() } catch { this.logout() }
      }
    }
  }
})
