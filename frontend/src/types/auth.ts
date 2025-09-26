// src/types/auth.ts

/** Jetons retournés par /auth/login et /auth/refresh */
export type Tokens = {
    access_token: string
    refresh_token?: string
}

/** Payload attendu par /auth/login côté frontend */
export type LoginPayload = {
    identifier: string
    password: string
}

// Profil renvoyé par l'API /my/profile (note : _id)
export interface ProfileBaseApi {
    _id: string
    email: string
    username: string
    role: 'admin' | 'user'
}

// Profil normalisé pour le front (id au lieu de _id)
export interface ProfileBase {
    id: string
    email: string
    username: string
    role: 'admin' | 'user'
}

export interface UserLocation {
    lat: number
    lon: number
    coords: string
    updated_at: string // ISO
}

// Objet utilisateur unifié côté front
export type Me = ProfileBase & {
    location?: UserLocation | null
}

// Utilitaire de mapping API -> front
export const mapProfileBase = (api: ProfileBaseApi): ProfileBase => ({
    id: api._id,
    email: api.email,
    username: api.username,
    role: api.role,
})