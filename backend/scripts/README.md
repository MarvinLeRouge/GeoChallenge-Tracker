[🇫🇷 Version française](README.fr.md) | 🇬🇧 English version

---

# Geographic data scripts

## Overview

This directory contains the one-shot setup scripts for the choropleth map.

> The test database management scripts (`duplicate_db_for_tests.py`, `copy_db_structure.py`) are documented separately in [`backend/tests/utils/README.md`](../tests/utils/README.md), where they actually live.

---

## Geographic data scripts (choropleth map)

These three scripts should be run **once** after initial setup, in the order shown.
They are all idempotent: safe to re-run if needed.

### `download_geo_data.py`

**Downloads GeoJSON files into `data/admin/`.**

- Skips files already present
- Sources configured in `config/geo_sources.yml`
- Currently: French regions and departments (france-geojson.gregoiredavid.fr)

```bash
cd backend
python scripts/download_geo_data.py
```

### `seed_zones.py`

**Populates the MongoDB `administrative_zones` collection from the downloaded GeoJSON files.**

- Upsert by `code`: safe to re-run
- Computes each zone's bbox via Shapely
- Extracts the `feature_code` (INSEE code) from each feature

```bash
cd backend
python scripts/seed_zones.py
```

### `assign_zones.py`

**Assigns administrative zones to existing caches in MongoDB.**

- Skips caches whose `zones` field is already set (unless `--force`)
- Filters by country (`--country FR` by default) to skip caches outside France
- Uses the same 3-pass algorithm as the GPX import pipeline:
  1. Shapely point-in-polygon (exact)
  2. Nominatim reverse geocoding (batch, 1 req/s)
  3. Nearest polygon (fallback < 0.1 degrees)
- Processed in batches of 500 (bulk write)

```bash
cd backend
python scripts/assign_zones.py           # France only
python scripts/assign_zones.py --force   # Reassign even already-processed caches
```

### Full workflow

```bash
cd backend
python scripts/download_geo_data.py
python scripts/seed_zones.py
python scripts/assign_zones.py
```
