import { defineStore } from 'pinia'
import api from '@/api/http'
import { isAxiosError } from 'axios'
import type { Me, ProfileBaseApi, UserLocation, Tokens, LoginPayload } from '@/types/auth'
import { mapProfileBase } from '@/types/auth'

export const useAuthStore = defineStore('auth', {
  state: () => ({
    accessToken: '' as string,
    refreshToken: (localStorage.getItem('refresh_token') || '') as string,
    user: null as Me | null,
    initialized: false,
  }),
  getters: { isAuthenticated: s => !!s.accessToken },
  actions: {
    setTokens(tokens: Tokens) {
      this.accessToken = tokens.access_token || ''
      sessionStorage.setItem('access_token', this.accessToken)
      if (tokens.refresh_token) {
        this.refreshToken = tokens.refresh_token
        localStorage.setItem('refresh_token', this.refreshToken)
      }
    },
    // 1) Profil de base immédiatement après login
    async fetchProfileBase() {
      const { data } = await api.get<ProfileBaseApi>('/my/profile')
      const base = mapProfileBase(data)
      this.user = { ...(this.user ?? {} as Me), ...base }
    },

    // 2) Localisation pour enrichir
    async fetchLocation() {
      const { data } = await api.get<UserLocation>('/my/profile/location')
      this.user = { ...(this.user ?? {} as Me), location: data }
    },
    async login({ identifier, password }: LoginPayload) {
      const body = new URLSearchParams()
      body.set('username', identifier) // email OU username
      body.set('password', password)
      const { data } = await api.post<Tokens>('/auth/login', body, {
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
      })
      this.setTokens(data)
      // Enchaînement : profil de base puis localisation (indépendants)
      try { await this.fetchProfileBase() } catch (e: unknown) {
        if (isAxiosError(e)) console.warn('fetchProfileBase failed:', e.response?.status)
      }
      try { await this.fetchLocation() } catch (e: unknown) {
        if (isAxiosError(e)) console.warn('fetchLocation failed:', e.response?.status)
      }
    },
    async refresh() {
      if (!this.refreshToken) throw new Error('no refresh')
      const { data } = await api.post<Tokens>('/auth/refresh', { refresh_token: this.refreshToken })
      this.setTokens(data)
    },
    logout() {
      this.accessToken = ''
      this.refreshToken = ''
      this.user = null
      sessionStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
    },
    async init() {
      if (this.initialized) return
      this.initialized = true
      // 👉 restaurer l'access, ne PAS appeler refresh ici
      this.accessToken = sessionStorage.getItem('access_token') || ''
      if (!this.accessToken) return            // ⟵ évite le 401 au premier chargement
      await Promise.allSettled([this.fetchProfileBase(), this.fetchLocation()])
    }
  }
})
