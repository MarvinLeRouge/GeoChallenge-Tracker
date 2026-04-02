import { ref, computed } from "vue";
import api from "@/api/http";
import { useApiErrorHandler } from "@/composables/useApiErrorHandler";
import type { UserStatsOut } from "@/types/index";

export function useUserStats() {
  const stats = ref<UserStatsOut | null>(null);
  const loading = ref(false);
  const error = ref<string | null>(null);
  const { handleApiError } = useApiErrorHandler();

  const loadStats = async () => {
    loading.value = true;
    error.value = null;

    try {
      const response = await api.get("/my/profile/stats");
      stats.value = response.data;
    } catch (err: unknown) {
      error.value = handleApiError(err).message;
    } finally {
      loading.value = false;
    }
  };

  // Computed properties pour les métriques dérivées
  const completionRate = computed(() => {
    if (!stats.value || stats.value.total_challenges === 0) return 0;
    return Math.round(
      (stats.value.completed_challenges / stats.value.total_challenges) * 100,
    );
  });

  const daysSinceLastCache = computed(() => {
    if (!stats.value?.last_cache_found_at) return null;
    const lastCache = new Date(stats.value.last_cache_found_at);
    const today = new Date();
    const diffTime = Math.abs(today.getTime() - lastCache.getTime());
    return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
  });

  const cachesPerActiveChallenge = computed(() => {
    if (!stats.value || stats.value.active_challenges === 0) return 0;
    return Math.round(
      stats.value.total_caches_found / stats.value.active_challenges,
    );
  });

  return {
    stats,
    loading,
    error,
    loadStats,
    completionRate,
    daysSinceLastCache,
    cachesPerActiveChallenge,
  };
}
