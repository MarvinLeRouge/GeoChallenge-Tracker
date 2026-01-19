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
}