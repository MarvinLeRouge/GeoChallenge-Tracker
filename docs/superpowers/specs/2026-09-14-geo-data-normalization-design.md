[🇫🇷 Version française](2026-09-14-geo-data-normalization-design.fr.md) | 🇬🇧 English version

---

# Design: multi-country administrative zone normalization (Epic 9.1)

**Created:** 2026-09-14
**Status:** approved by user, pending implementation plan
**Related:** `docs/roadmap.md` Epic 9.1, `docs/superpowers/plans/2026-09-11-zones-explorer-step5.md`

## Context

GeoChallenge-Tracker stores administrative zone boundaries (region/department-equivalent, levels 0/1/2) in the `administrative_zones` collection, used to resolve which zones a cache belongs to. Today only France is populated (114 documents), seeded by a legacy, France-only pipeline (`backend/scripts/seed_zones.py`). A newer, CONTRACT.md-compliant admin upload path already exists (`POST /admin/geo/{country_code}/upload`, `geo_admin_service.py`) but has never been used for a real country and contains a confirmed bug.

Three local data sources are available under `~/projets/geo_data/data/`: `insee` (official French reference tables, no geometry), `geonames` (worldwide admin1/admin2 code tables, some countries' codes are stale, e.g. France's are pre-2016-merger), and `geoboundaries` (worldwide boundary geometries by ISO3/ADM level, zip archives).

This document covers the design for a generic, reusable normalization framework producing ready-to-use administrative zone files for any country, plus the GeoChallenge-Tracker-side changes needed to consume them safely.

## Goals

- Generic, reusable framework for turning raw geoBoundaries/geonames/INSEE data into normalized administrative zone files, not limited to GeoChallenge-Tracker's consumption format.
- Migrate France onto the same generic pipeline (currently seeded through a separate, one-off legacy path), verifying the result matches the current 114-document baseline before replacing anything.
- Fix the confirmed `feature_code`/`code` bug in `geo_admin_service.py::upload_zone_level`, blocking for any real CONTRACT.md-compliant upload.
- No new MongoDB collections needed: `administrative_zones` already accommodates new countries additively, satisfying the constraint that existing collections must not be impacted.
- Concrete VPS action list (the user has no direct SSH access and executes commands themselves) and a test plan, including using the user's own real Italy geocache finds as an end-to-end validation case.

## Current state (findings from exploration)

- **Two incompatible ingestion paths** exist in the backend:
  - Legacy `seed_zones.py` + `backend/config/geo_sources.yml`: France-only, sourced from `france-geojson.gregoiredavid.fr` (**not** `geo_data/insee`, despite files existing there), recomputes `bbox` and `parent_code` via Shapely (geometric containment, with nearest-parent fallback) rather than trusting source values.
  - New `geo_admin_service.py::upload_zone_level` (already wired to `POST /admin/geo/{country_code}/upload`): validates against `CONTRACT.md`'s required properties (`code`, `nom`, `feature_code`, `parent_code` at level 2, `bbox`), trusts the file's own precomputed values. **Bug at line 139**: reads `feature_code = str(props["code"])` instead of `props["feature_code"]`. Per CONTRACT.md, `code` is already the prefixed value (e.g. `FR-84`), so this produces double-prefixed codes (`FR-FR-84`) for any file that actually conforms to the contract. Masked by the current test fixture (`_feature()` in `test_geo_admin_service.py`), which sets the same value for both `code` and `feature_code`.
- **Live DB** (`administrative_zones`, 114 docs): FR only (18 regions + 96 departments), correctly prefixed (`FR-11`, ...), `geojson_file: "FR/regions.geojson"` (legacy naming, not `adm{level}.geojson`).
- **`caches.distinct('zones.country')` returns `['FR']` only**: no Italian cache data exists in the DB today. The user's real "earth" and "tradi" finds in Italy are not yet imported; `get_missing_countries()` cannot surface Italy until they are (separate, pre-existing cache-import feature, out of scope here).
- **`geo_data_dir` (`data/admin`, default) is not a persistent volume in `docker-compose.prod.yml`**, unlike `/backups` and `/app/uploads`. The current FR files exist only because they're committed to git and baked into the Docker image at build time. Any file written via the admin upload endpoint in prod today would be lost on the next redeploy.
- **`geo_data` is a git clone of a third-party upstream package** (`stefangabos/world_countries`, CC-BY-SA 4.0, `origin` points directly at it). All custom additions (`download_geoboundaries.py`, `download_geonames.py`, `data/insee`, `data/geonames`, `data/geoboundaries`) are currently untracked, with no version history. Decision: stop treating this directory as an upstream clone going forward, treat it as an independent project instead (attribution to the original package preserved in documentation), and stop pushing to `origin` (rename to `upstream` for traceability during implementation).
- **`geo_json` (separate dev-only tooling project) is abandoned** in favor of consolidating into `geo_data`. Analysis: `geo_json` contains zero implementation code (a single "Initial commit", no scripts, no tests), only documentation (`CLAUDE.md`, `CONTRACT.md`, `README.md`/`.fr.md`, `SOURCES.md`) and one manually-fetched raw FR sample duplicating data already present in `geo_data/data/geoboundaries/FRA`. Only `CONTRACT.md` and the `SOURCES.md` attribution-tracking concept are worth migrating; the rest is superseded by this design.
- **geoBoundaries `shapeISO` is directly usable for France** (`FR-IDF`, `FR-CVL`, ...), contrary to what the original Epic 9.1 sketch assumed needed a geonames join for every non-`geoboundaries_direct` case. However, to preserve the exact codes already live in the DB (`FR-11`, numeric INSEE-style), France needs a join between geoBoundaries geometry (by name) and INSEE's authoritative codes/hierarchy, not a direct `shapeISO` mapping. geonames is not used for France: its admin1 codes are stale (pre-2016 region merger, e.g. `FR.84 Rhône-Alpes`, `FR.27 Bourgogne`), which also means it cannot be trusted for the parent/hierarchy join.

## Consolidation decision: `geo_data` as the single tooling home

All source data acquisition (existing) and normalization (new) work lives in `~/projets/geo_data`, replacing `geo_json` entirely. Rationale: `geo_data` already holds the actual downloaded raw data for all three sources (world-wide `geoboundaries` coverage confirmed present, e.g. `FRA`, `DEU`, `ESP`, `ITA`, `GBR`), the download scripts already live there, and other future scripts (unrelated to GeoChallenge-Tracker) may reuse the same source data - keeping normalization logic there avoids duplicating or re-fetching data in a second, empty project.

### Directory structure

```
geo_data/
  docs/                                 (existing, upstream package docs, untouched)
  data/
    insee/, geonames/, geoboundaries/    (existing raw sources, untouched)
    normalized/                          (NEW: generic per-country resolved zones, project-agnostic)
  scripts/
    download_geoboundaries.py, download_geonames.py   (moved here, unchanged otherwise)
    README.md                            (overview of all scripts in this directory)
    docs/
      CONTRACT.md                        (migrated from geo_json)
      SOURCES.md                         (migrated and expanded: CC-BY-SA 4.0 world_countries, Licence Ouverte INSEE, CC-BY 4.0 geonames/geoBoundaries)
    normalize/
      common/
        handlers/       geoboundaries_direct.py, geonames_join.py, insee_geoboundaries_join.py, admin2_as_region.py
        countries/       fr.py, it.py, (de.py, es.py, gb.py as needed later)
        pipeline.py
      gctracker/
        export_contract.py
    tests/
```

### Handler interface and orchestration

- `ZoneRecord` (generic dataclass, project-agnostic): `feature_code`, `name`, `geometry` (GeoJSON), `parent_feature_code` (optional, level 2 only).
- `NormalizationHandler`: common interface, `resolve(level, country_config) -> list[ZoneRecord]`. Implementations: `geoboundaries_direct` (uses `shapeISO` directly), `geonames_join` (name-based join against geonames admin codes), `insee_geoboundaries_join` (name-based join between geoBoundaries geometry and INSEE codes/hierarchy, used for France), `admin2_as_region` (uses geoBoundaries ADM2 as the "region" level when ADM1 is too coarse, e.g. United Kingdom).
- `CountryConfig` (one module per country under `countries/`): ISO2 code, ISO3 code (for geoBoundaries paths), handler selection per level, source file paths, optional name-alias table for approximate joins.
- `pipeline.py`: for a given country, for each level, runs the configured handler and resolves `parent_feature_code` **via the source's own join keys** (e.g. INSEE's `DEP.REG` field) rather than geometric centroid-containment, avoiding the legacy pipeline's weakest point. Output: `data/normalized/{cc}/adm{level}.geojson`, generic GeoJSON with minimal properties (`feature_code`, `name`, `parent_feature_code`), reusable outside this project.
- `gctracker/export_contract.py`: consumes the generic normalized files, computes `bbox` (Shapely), prefixes codes (`{cc}-{feature_code}`), renames properties to the exact CONTRACT.md schema (`code`, `nom`, `feature_code`, `parent_code`, `bbox`), producing upload-ready files. This keeps the CONTRACT.md-specific shaping isolated from the reusable join/resolution logic.

### Git handling

`geo_data`'s `origin` currently points at the upstream `stefangabos/world_countries` repository; all custom additions are untracked. Going forward this directory is treated as an independent project (not a tracked fork): rename `origin` to `upstream` (no more pushes to it), commit the custom scripts/tooling locally, and document attribution to the original package (CC-BY-SA 4.0) alongside INSEE (Licence Ouverte), geonames and geoBoundaries (CC-BY 4.0) attributions in `scripts/docs/SOURCES.md`.

## GeoChallenge-Tracker-side changes

- **Bug fix**: `geo_admin_service.py::upload_zone_level` reads `feature_code` from `props["feature_code"]` instead of `props["code"]`. Dedicated regression test using a fixture where `code` and `feature_code` differ (the current fixture masks the bug by setting them identically).
- **Defensive validation**: if the resolved `feature_code` already starts with `{country_code}-`, raise an explicit `ValueError` (double-prefixing detected) instead of silently producing an incorrect code.
- **Persistent volume**: add a bind-mount for `geo_data_dir` (`/app/data/admin` in-container) to `docker-compose.prod.yml`, e.g. `../shared/geo-admin` on the host, mirroring `/backups` and `/app/uploads`. Requires a one-time migration of the 3 existing FR files (currently baked into the image) into this volume before/during the deploy that introduces the mount, to avoid a service gap.
- **France migrated** to the new generic pipeline (INSEE/geoBoundaries name join), with a non-regression check comparing the pipeline's output against the current 114 live documents (same codes, names, equivalent bboxes) before any replacement in the database.

## Test plan

- Unit tests per handler (isolated fixtures), including join-failure cases (name not found in the alias table raises explicitly rather than guessing).
- Unit tests for the bug fix and the double-prefix guard in `geo_admin_service.py`.
- FR non-regression: dedicated script/test comparing the new pipeline's output to the current 114 `administrative_zones` documents, run and validated before replacing any FR data.
- Italy dry-run (zero DB risk): run the full pipeline for Italy, validate the output against `_validate_feature_collection` (schema check only, no write), confirming the generic pipeline produces a contract-compliant result before touching the real database.
- Italy real upload (optional, after the dry-run passes): back up `administrative_zones` first (standing project rule for structural changes), then upload via the local admin endpoint (which targets the same Atlas cluster as prod) - purely additive, no existing FR document touched. Once done, the user can import their real Italian cache finds (earth + tradi) through GeoChallenge-Tracker's existing cache-import feature (out of scope here) to validate `get_missing_countries()` and cache-to-zone resolution end-to-end.

## VPS actions (executed by the user, no direct SSH access for the assistant)

1. Create the host directory for the new persistent volume (e.g. `../shared/geo-admin`) before deploying the updated `docker-compose.prod.yml`.
2. Copy the 3 existing FR files (`backend/data/admin/FR/*.geojson`) into the new volume once, to avoid a service gap between the old baked-in directory (removed) and the new volume (initially empty).
3. Deploy normally (merge, pull, `docker compose up -d`).
4. Back up `administrative_zones` (targeted `mongodump`, as already practiced for `countries_backup_*`) before the first real upload of a new country.
5. Call the admin upload endpoint (`POST /admin/geo/{cc}/upload`) in prod, per level, once the local dry-run has been validated.

Exact commands to be provided in the implementation plan.

## Out of scope

- Actual per-country configs beyond France (migration) and Italy (validation case) - Germany, Spain, United Kingdom remain sketched (Epic 9.1) but not implemented here.
- Importing the user's real Italian cache finds into `caches`/`found_caches` - existing feature, unrelated to this normalization work.
- Any change to `countries`/`states` reference collections.
