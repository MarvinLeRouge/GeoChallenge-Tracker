// src/types/challenges.ts

/** Snapshot de progression d'un UserChallenge */
export interface UserChallengeProgress {
  percent: number | null;
  tasks_done: number | null;
  tasks_total: number | null;
  checked_at: string | null;
}

/** Élément de liste UC (GET /my/challenges) */
export interface UserChallengeListItem {
  id: string;
  status: "pending" | "accepted" | "dismissed" | "completed";
  computed_status: string | null;
  effective_status: "pending" | "accepted" | "dismissed" | "completed";
  progress: UserChallengeProgress | null;
  updated_at: string | null;
  challenge: { id: string; name: string };
  cache: {
    id: string;
    GC: string;
    difficulty?: number | null;
    terrain?: number | null;
  };
}

/** Détail complet UC (GET /my/challenges/:id) */
export interface UserChallengeDetail extends UserChallengeListItem {
  created_at: string | null;
  manual_override: boolean | null;
  override_reason: string | null;
  overridden_at: string | null;
  notes: string | null;
  challenge: { id: string; name: string; description?: string | null };
}

/** Statistiques renvoyées par /my/challenges/sync */
export type ChallengeSyncStats = Record<string, number>;

/** Types et tailles de cache pour les filtres */
export interface CacheType {
  _id: string;
  code: string;
  name: string;
}

export interface CacheSize {
  _id: string;
  code: string;
  name: string;
}

/** Résultat de vérification Matrix D/T */
export interface MatrixResult {
  total_combinations: number;
  completed_combinations_count: number;
  completion_rate: number;
  matrix_tours: number;
  next_round_completed_count: number;
  next_round_completion_rate: number;
  missing_combinations: Array<{
    difficulty: number;
    terrain: number;
  }>;
  missing_combinations_by_difficulty: {
    [difficulty: string]: Array<{ terrain: number }>;
  };
  completed_combinations_details: Array<{
    difficulty: number;
    terrain: number;
    count: number;
  }>;
  cache_type_filter?: string;
  cache_size_filter?: string;
}

/** Résultat de vérification Calendar */
export interface CalendarResult {
  total_days_365: number;
  completed_days_365: number;
  completion_rate_365: number;
  total_days_366: number;
  completed_days_366: number;
  completion_rate_366: number;
  missing_days: string[];
  missing_days_by_month: { [month: string]: string[] };
  completed_days: Array<{
    day: string;
    count: number;
  }>;
  cache_type_filter?: string;
  cache_size_filter?: string;
}

// Types for GPX import response
export interface ImportResponse {
  summary: Record<string, number | string>;
  challenges_stats?: Record<string, number | string>;
  sync_stats?: Record<string, number | string>;
}
