export interface CacheTypeStats {
  type_id: string
  type_label: string
  type_code: string
  count: number
}

export interface UserStatsOut {
  user_id: string
  username: string
  total_caches_found: number
  total_challenges: number
  active_challenges: number
  completed_challenges: number
  first_cache_found_at: string | null
  last_cache_found_at: string | null
  created_at: string
  last_activity_at: string | null
  cache_types_stats?: CacheTypeStats[]
}