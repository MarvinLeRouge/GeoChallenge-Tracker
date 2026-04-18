// src/composables/useZones.ts
// API composable for the /api/zones endpoints (choropleth map).

import { ref } from "vue";
import api from "@/api/http";
import { useApiErrorHandler } from "@/composables/useApiErrorHandler";
import type {
  ZoneListItem,
  ZoneDetail,
  ZoneTypeStatsResponse,
} from "@/types/zones";

export function useZones() {
  const loading = ref(false);
  const error = ref<string | null>(null);
  const { handleApiError } = useApiErrorHandler();

  /**
   * Fetches all zones for a given country/level with their cache counts.
   * @param country - ISO country code, e.g. "FR"
   * @param level - Administrative level: 1 = region, 2 = department
   * @param typeCode - Optional single cache type filter (e.g. "traditional")
   */
  async function fetchZones(
    country: string,
    level: 1 | 2,
    typeCode?: string,
  ): Promise<ZoneListItem[]> {
    loading.value = true;
    error.value = null;
    try {
      const params: Record<string, unknown> = { country, level };
      if (typeCode) params["type"] = typeCode;
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
   * Fetches zone detail with total cache count and top 10 caches.
   * @param code - Zone code, e.g. "FR-84" or "FR-38"
   * @param typeCode - Optional single cache type filter
   * @param level - Administrative level hint to disambiguate codes shared between levels
   */
  async function fetchZoneDetail(
    code: string,
    typeCode?: string,
    level?: 1 | 2,
  ): Promise<ZoneDetail | null> {
    loading.value = true;
    error.value = null;
    try {
      const qs: string[] = [];
      if (level !== undefined) qs.push(`level=${level}`);
      if (typeCode) qs.push(`type=${encodeURIComponent(typeCode)}`);
      const url =
        qs.length > 0 ? `/zones/${code}?${qs.join("&")}` : `/zones/${code}`;

      const { data } = await api.get<ZoneDetail>(url);
      return data;
    } catch (err: unknown) {
      error.value = handleApiError(err).message;
      return null;
    } finally {
      loading.value = false;
    }
  }

  /**
   * Fetches per-type found-cache counts for a zone (all types included, zeros too).
   * @param code - Zone code, e.g. "FR-84" or "FR-38"
   * @param level - Administrative level hint to disambiguate codes shared between levels
   */
  async function fetchZoneTypeStats(
    code: string,
    level?: 1 | 2,
  ): Promise<ZoneTypeStatsResponse | null> {
    loading.value = true;
    error.value = null;
    try {
      const url =
        level !== undefined
          ? `/zones/${code}/type-stats?level=${level}`
          : `/zones/${code}/type-stats`;
      const { data } = await api.get<ZoneTypeStatsResponse>(url);
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
    fetchZoneTypeStats,
  };
}
