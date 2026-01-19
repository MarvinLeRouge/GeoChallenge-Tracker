export interface UserLocationOut {
  id: string
  lat: number
  lon: number
  updated_at: string
  coords: string
}

export interface UserLocationIn {
  lat: number | null
  lon: number | null
  position?: string | null
}

export interface UserProfileOut {
  id: string
  username: string
  email: string
  location?: {
    lat: number | null
    lon: number | null
    updated_at?: string
  } | null
}