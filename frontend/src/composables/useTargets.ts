// src/composables/useTargets.ts
import { ref } from 'vue'
import api from '@/api/http'
import { toast } from 'vue-sonner'

export interface TargetItem {
  id: string
  cache_id: string
  cache_GC: string | null
  cache_title?: string | null
  cache_difficulty?: number | null
  cache_terrain?: number | null
  cache_type_code?: string | null
  loc?: { lat: number; lng: number } | null
  primary_task_id?: string | null
  matched_tasks_count: number
  score: number
  score_details?: Record<string, number> | null
  distance_m?: number | null
}

export interface TargetsRefreshStatus {
  needs_refresh: boolean
  last_not_found_import_at: string | null
  last_targets_evaluated_at: string | null
}

export interface EvaluateAllResult {
  ok: boolean
  evaluated: number
  total_inserted: number
  total_updated: number
  last_targets_evaluated_at: string
}

export function useTargets() {
  const targets = ref<TargetItem[]>([])
  const nbItems = ref(0)
  const loading = ref(false)
  const evaluating = ref(false)
  const refreshStatus = ref<TargetsRefreshStatus | null>(null)

  async function fetchRefreshStatus(): Promise<TargetsRefreshStatus> {
    const { data } = await api.get<TargetsRefreshStatus>('/my/targets/refresh-status')
    refreshStatus.value = data
    return data
  }

  async function evaluateAll(force = false): Promise<EvaluateAllResult> {
    evaluating.value = true
    try {
      const { data } = await api.post<EvaluateAllResult>('/my/targets/evaluate-all', null, {
        params: { force },
      })
      return data
    } finally {
      evaluating.value = false
    }
  }

  async function fetchTargets(statusFilter: string | null = 'accepted'): Promise<void> {
    loading.value = true
    try {
      const params: Record<string, unknown> = { page: 1, page_size: 200, sort: '-score' }
      if (statusFilter) params.status_filter = statusFilter
      const { data } = await api.get<{ items: TargetItem[]; nb_items: number }>('/my/targets', {
        params,
      })
      targets.value = data.items ?? []
      nbItems.value = data.nb_items ?? 0
    } finally {
      loading.value = false
    }
  }

  async function fetchTargetsNearby(
    lat: number,
    lon: number,
    radiusKm: number,
    statusFilter: string | null = 'accepted',
  ): Promise<void> {
    loading.value = true
    try {
      const params: Record<string, unknown> = {
        lat,
        lon,
        radius_km: radiusKm,
        page: 1,
        page_size: 200,
        sort: 'distance',
      }
      if (statusFilter) params.status_filter = statusFilter
      const { data } = await api.get<{ items: TargetItem[]; nb_items: number }>(
        '/my/targets/nearby',
        { params },
      )
      targets.value = data.items ?? []
      nbItems.value = data.nb_items ?? 0
    } finally {
      loading.value = false
    }
  }

  /**
   * Main entry point: check refresh status, evaluate if stale, then load targets.
   */
  async function init(): Promise<void> {
    try {
      const status = await fetchRefreshStatus()
      if (status.needs_refresh) {
        await evaluateAll()
        await fetchRefreshStatus()
      }
      await fetchTargets()
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      toast.error('Erreur lors du chargement des targets', { description: msg })
    }
  }

  return {
    targets,
    nbItems,
    loading,
    evaluating,
    refreshStatus,
    init,
    fetchTargets,
    fetchTargetsNearby,
    evaluateAll,
  }
}
