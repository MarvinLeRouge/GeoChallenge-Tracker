// src/types/challenges.ts

/** Statistiques renvoyées par /my/challenges/sync */
export type ChallengeSyncStats = Record<string, number>

/** Types et tailles de cache pour les filtres */
export interface CacheType {
  _id: string
  code: string
  name: string
}

export interface CacheSize {
  _id: string
  code: string
  name: string
}

/** Résultat de vérification Matrix D/T */
export interface MatrixResult {
  total_combinations: number
  completed_combinations: number
  completion_rate: number
  missing_combinations: Array<{
    difficulty: number
    terrain: number
  }>
  missing_combinations_by_difficulty: { [difficulty: string]: Array<{ terrain: number }> }
  completed_combinations_details: Array<{
    difficulty: number
    terrain: number
    count: number
  }>
  cache_type_filter?: string
  cache_size_filter?: string
}

/** Résultat de vérification Calendar */
export interface CalendarResult {
  total_days_365: number
  completed_days_365: number
  completion_rate_365: number
  total_days_366: number
  completed_days_366: number
  completion_rate_366: number
  missing_days: string[]
  missing_days_by_month: { [month: string]: string[] }
  completed_days: Array<{
    day: string
    count: number
  }>
  cache_type_filter?: string
  cache_size_filter?: string
}

// Types for GPX import response
export interface ImportResponse {
  summary: Record<string, number | string>
  challenge_stats?: Record<string, number | string>
}
