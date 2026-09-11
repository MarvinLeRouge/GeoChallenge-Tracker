// src/types/zones.ts
// TypeScript types mirroring the /api/zones endpoint DTOs.

/** Summary of an administrative zone with its cache count. */
export interface ZoneListItem {
  code: string;
  name: string;
  cache_count: number;
}

/** Response for GET /api/zones. */
export interface ZoneListResponse {
  items: ZoneListItem[];
}

/** Count of found caches for a single cache type within a zone. */
export interface ZoneTypeStatItem {
  type_code: string;
  type_name: string;
  count: number;
}

/** Detail of an administrative zone with its per-type cache breakdown. */
export interface ZoneDetail {
  code: string;
  name: string;
  cache_count: number;
  type_counts: ZoneTypeStatItem[];
}
