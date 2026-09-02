# ADR 0005: Choropleth map of finds by administrative zone

**Status:** Accepted
**Date:** 2026-04-17
**Deciders:** Marvin Le Rouge
**Sources:** PR #57 (`Feat/choropleth map`)

## Context

Users wanted to see their found caches broken down by administrative zone (e.g. French departments) rather than only by radius/bbox search. Building this requires assigning each cache to a zone polygon (GeoJSON) and rendering a choropleth (color-by-count) map, which introduces two correctness risks: popovers rendering off-screen near map edges, and caches near a border being misassigned to the wrong country's zone by a naive nearest-polygon heuristic.

## Decision

Ship a `ZonesMap.vue` page (route `/caches/zones`, "Caches - Trouvées par zones", added to the sidebar) backed by a zone-assignment pipeline with an explicit multi-pass strategy and a foreign-cache guard:

- Zone assignment runs in passes, falling back to nearest-polygon only when direct polygon containment doesn't resolve a cache (3-pass assignment).
- `zone_nominatim._fetch_one` reads `address.country_code` from the Nominatim reverse-geocoding response and sets a `_foreign` flag when a point is confirmed outside the target country.
- `zone_assigner` excludes `_foreign`-flagged points from the nearest-polygon fallback pass, so a cache just outside the country can no longer be pulled into a border zone by proximity alone.
- `assign_zones.py` filters the cache query by `country_id` upfront, so foreign caches are never run against the (e.g. French) zone index at all.
- Popover positioning is clamped to `window.innerHeight - 420` so it stays fully visible when a zone near the bottom of the viewport is clicked.
- A real misassigned cache found during testing (a Spanish cache near the border, GCHVXZ) was corrected directly in the database.

## Consequences

- Choropleth zone counts are protected against cross-border misassignment by construction (country filter + foreign-point exclusion), not just by the one manually-fixed example.
- The zone-assignment pipeline is more complex (three passes plus a country/foreign check) than a single nearest-polygon lookup would be, but that complexity is what prevents the border-bleed bug class.
- Nominatim's `address.country_code` becomes a dependency of zone-assignment correctness, not just of individual point geocoding.

## Alternatives considered

Not explicitly recorded in the source PR beyond the single-pass nearest-polygon approach that produced the GCHVXZ misassignment; the 3-pass approach with an explicit foreign-point exclusion was adopted to fix that bug, not evaluated against other zone-assignment algorithms.
