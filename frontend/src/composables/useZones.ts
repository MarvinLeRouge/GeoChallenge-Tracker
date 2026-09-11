// src/composables/useZones.ts
// API composable for the /api/zones endpoints (choropleth map).

import { ref } from "vue";
import api from "@/api/http";
import { useApiErrorHandler } from "@/composables/useApiErrorHandler";
import type { ZoneListItem, ZoneDetail } from "@/types/zones";

export function useZones() {
  const loading = ref(false);
  const error = ref<string | null>(null);
  const { handleApiError } = useApiErrorHandler();

  /**
   * Fetches zones for a given level with their cache counts.
   * @param level - Administrative level: 0 = country, 1 = region, 2 = department
   * @param country - ISO country code, e.g. "FR". Required for level 1/2, ignored at level 0.
   * @param typeCodes - Optional cache type filter (one or more type codes)
   */
  async function fetchZones(
    level: 0 | 1 | 2,
    country?: string,
    typeCodes?: string[],
  ): Promise<ZoneListItem[]> {
    loading.value = true;
    error.value = null;
    try {
      const params: Record<string, unknown> = { level };
      if (country) params["country"] = country;
      if (typeCodes && typeCodes.length > 0) params["type"] = typeCodes;
      const { data } = await api.get<{ items: ZoneListItem[] }>("/zones", {
        params,
      });
      return data.items;
    } catch (err: unknown) {
      error.value = handleApiError(err).message;
      return [];
    } finally {
      loading.value = false;
    }
  }

  /**
   * Fetches zone detail with total found-cache count and per-type breakdown.
   * @param code - Zone code, e.g. "FR-84" or "FR-38"
   * @param level - Administrative level hint to disambiguate codes shared between levels
   */
  async function fetchZoneDetail(
    code: string,
    level?: 1 | 2,
  ): Promise<ZoneDetail | null> {
    loading.value = true;
    error.value = null;
    try {
      const params: Record<string, unknown> = {};
      if (level !== undefined) params["level"] = level;
      const { data } = await api.get<ZoneDetail>(`/zones/${code}`, {
        params,
      });
      return data;
    } catch (err: unknown) {
      error.value = handleApiError(err).message;
      return null;
    } finally {
      loading.value = false;
    }
  }

  return {
    loading,
    error,
    fetchZones,
    fetchZoneDetail,
  };
}
