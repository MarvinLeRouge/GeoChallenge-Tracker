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
  completed_combinations: number
  matrix: { [difficulty: string]: { [terrain: string]: number } }
  filters: {
    cache_type_name?: string
    cache_size_name?: string
  }
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
