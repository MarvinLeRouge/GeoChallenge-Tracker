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
  completion_rate_365: number
  completion_rate_366: number
  completed_days: Array<{
    month: number
    day: number
    count: number
  }>
  missing_days_by_month: { [month: number]: number[] }
  filters: {
    cache_type_name?: string
    cache_size_name?: string
  }
}
