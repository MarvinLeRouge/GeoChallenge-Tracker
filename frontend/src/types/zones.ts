// src/types/zones.ts
// TypeScript types mirroring the /api/zones endpoint DTOs.

/** Compact cache entry returned inside a zone detail popover. */
export interface CacheInZone {
  GC: string;
  title: string;
  type_code: string | null;
  difficulty: number | null;
  terrain: number | null;
}

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

/** Detail of an administrative zone with top caches. */
export interface ZoneDetail {
  code: string;
  name: string;
  cache_count: number;
  caches: CacheInZone[];
}
