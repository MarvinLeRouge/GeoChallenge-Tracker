# Zones Explorer - Step 5 (Unified Drill-Down Page) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the two retired legacy pages (`ZonesMap.vue`, `ZoneTypeStatsMap.vue`, now archived under `docs/work-in-progress/zones-explorer-legacy/`) with a single World -> Country -> Region drill-down page (`ZonesExplorer.vue`), backed by a new `GET /countries` referential endpoint and two admin-only GeoJSON management endpoints, and by a filename normalization of the existing France GeoJSON files.

**Architecture:** Backend stays on the existing `/zones` contract (level 0/1/2, unchanged since Step 3/4) and adds three small, independent pieces: an unauthenticated `GET /countries` referential endpoint, an admin-only `GET /admin/geo/missing-countries` + `POST /admin/geo/{country_code}/upload` pair for managing GeoJSON coverage, and a one-shot migration renaming France's `regions.geojson`/`departements.geojson` to the generic `adm1.geojson`/`adm2.geojson` convention. Frontend replaces the two legacy pages with one `ZonesExplorer.vue` that keeps three sibling views (World list, Country choropleth, Region choropleth) in one component, sharing the zone-detail popup and the multi-select type filter, and using client-side Leaflet zoom (not a new API call) to go from Country to Region.

**Tech Stack:** FastAPI + Motor (MongoDB), Pydantic DTOs, pytest/pytest-asyncio + httpx `ASGITransport` for backend unit tests; Vue 3 `<script setup>` + Leaflet + Vitest/`@vue/test-utils` for frontend.

**Spec:** No standalone spec file exists for this step; the full design was worked out interactively in chat and is restated as the "Global Constraints" below. This plan **is** the spec of record for Step 5.

## Global Constraints

- Keep the `/zones` contract (level 0/1/2, `country`, `type` query params) exactly as shipped in Step 3/4 - do not reopen it. `GET /zones/{code}` never takes a type filter; it always returns the full `type_counts` breakdown regardless of any active map/list type filter.
- Zero-count zones are non-clickable at every level (World, Country, Region), not just excluded from counted lists.
- Region-level drill-down is a client-side Leaflet zoom to the clicked region's bounds, not a new spatially-filtered API call. The same country-level level-2 GeoJSON (already scoped to `country`) is reused.
- The multi-select cache-type filter is implemented as checkboxes inside a dropdown, not a native multi-select `<select>`.
- The normalized GeoJSON filename convention is `adm{level}.geojson` (`adm0`=country, `adm1`=region, `adm2`=department), matching the `geo_json` sibling project's contract (`~/projets/geo_json/CONTRACT.md`).
- `backend/data/admin/**` is gitignored (`.gitignore:95`) - file renames and new country uploads under it are **not** captured by git and must be repeated on every environment that serves `/geo` (local and the VPS). Flag this explicitly at the relevant task; do not assume a `git mv` carries it.
- No dedicated frontend UI for the two admin endpoints - Swagger only, per explicit instruction.
- ADM0 (country boundary) has no current consumer in GeoChallenge-Tracker (World view is list-based) - the upload endpoint accepts and stores it for forward-compatibility but does not seed any DB collection from it.

---

### Task 1: `GET /countries` referential endpoint

**Files:**
- Modify: `backend/app/api/routes/referentials.py`
- Test: `backend/tests/unit/test_referentials_countries.py` (new)
- Test: `backend/tests/integration/test_endpoints_meta_referentials.py:96` (append to `TestReferentialEndpoints`)

**Interfaces:**
- Produces: `GET /countries` -> `list[{"code": str, "name": str}]`, sorted by `name`, only countries with a non-null `code`, `name` prefers `name_fr` falling back to `name`. Consumed by frontend Task 5's `fetchCountries()`.

- [ ] **Step 1: Write the failing unit test**

```python
# backend/tests/unit/test_referentials_countries.py
"""Tests for GET /countries."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import referentials as referentials_module


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(referentials_module.router)
    return app


def _mock_collection(docs: list[dict]) -> MagicMock:
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=docs)
    coll = MagicMock()
    coll.find.return_value = cursor
    return coll


class TestGetCountries:
    @pytest.mark.asyncio
    async def test_returns_sorted_name_and_code(self):
        docs = [
            {"code": "US", "name": "United States of America", "name_fr": None},
            {"code": "FR", "name": "France", "name_fr": "France"},
        ]
        with patch.object(
            referentials_module, "get_collection", AsyncMock(return_value=_mock_collection(docs))
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/countries")

        assert response.status_code == 200
        assert response.json() == [
            {"code": "FR", "name": "France"},
            {"code": "US", "name": "United States of America"},
        ]

    @pytest.mark.asyncio
    async def test_prefers_name_fr_when_set(self):
        docs = [{"code": "DE", "name": "Germany", "name_fr": "Allemagne"}]
        with patch.object(
            referentials_module, "get_collection", AsyncMock(return_value=_mock_collection(docs))
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/countries")

        assert response.json() == [{"code": "DE", "name": "Allemagne"}]

    @pytest.mark.asyncio
    async def test_excludes_countries_without_code(self):
        docs = [{"code": None, "name": "Unknown Territory", "name_fr": None}]
        with patch.object(
            referentials_module, "get_collection", AsyncMock(return_value=_mock_collection(docs))
        ) as mock_get:
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/countries")

        assert response.json() == []
        mock_get.assert_awaited_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `.venv/bin/pytest tests/unit/test_referentials_countries.py -v`
Expected: FAIL - `AttributeError: module 'app.api.routes.referentials' has no attribute 'get_collection'` is not the failure; rather `GET /countries` returns 404 (route doesn't exist yet).

- [ ] **Step 3: Add the route**

```python
# backend/app/api/routes/referentials.py
# add below get_cache_sizes()


# DONE: [ZONES-EXPLORER] Route /countries (GET) - referential list for the World view
@router.get("/countries", summary="Get all countries with a known ISO code")
async def get_countries():
    """Get all countries that have a resolved ISO 3166-1 alpha-2 code.

    Description:
        Countries without a resolved `code` are excluded since they cannot be
        matched to `administrative_zones.country_code` or to `/zones` results.
        Used by the zones explorer's World view, independently of the
        authenticated user's found-cache counts (unlike `GET /zones?level=0`).
    """
    countries_coll = await get_collection("countries")
    docs = await countries_coll.find(
        {"code": {"$ne": None}}, {"_id": 0, "code": 1, "name": 1, "name_fr": 1}
    ).to_list(length=None)
    items = [{"code": d["code"], "name": d.get("name_fr") or d["name"]} for d in docs]
    items.sort(key=lambda c: c["name"])
    return items
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_referentials_countries.py -v`
Expected: PASS (3/3)

- [ ] **Step 5: Add an integration test alongside the existing referentials tests**

```python
# backend/tests/integration/test_endpoints_meta_referentials.py
# inside class TestReferentialEndpoints, after test_cache_sizes_endpoint

    @pytest.mark.asyncio
    async def test_countries_endpoint(self, client):
        """Test que /countries répond."""
        response = await client.get("/countries")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        if data:
            assert set(data[0].keys()) == {"code", "name"}
```

- [ ] **Step 6: Run the full unit suite and lint**

Run: `.venv/bin/pytest tests/unit/ -q && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app`
Expected: all green

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/routes/referentials.py backend/tests/unit/test_referentials_countries.py backend/tests/integration/test_endpoints_meta_referentials.py
git commit -m "feat(backend): add GET /countries referential endpoint

Modified files:
- backend/app/api/routes/referentials.py — add GET /countries
- backend/tests/unit/test_referentials_countries.py — unit tests for the new route
- backend/tests/integration/test_endpoints_meta_referentials.py — integration smoke test"
```

---

### Task 2: Rename France's GeoJSON files to the `adm1`/`adm2` convention

**Files:**
- Rename (filesystem `mv`, **not tracked by git** - see Global Constraints): `backend/data/admin/FR/regions.geojson` -> `backend/data/admin/FR/adm1.geojson`, `backend/data/admin/FR/departements.geojson` -> `backend/data/admin/FR/adm2.geojson`
- Modify: `backend/config/geo_sources.yml`
- Create: `backend/scripts/rename_fr_geojson_files.py`
- Modify: `backend/tests/unit/test_zone_assigner.py:312,317,340,345`
- Modify: `backend/tests/integration/test_endpoints_zones.py:41,51`
- Modify (mechanical `regions.geojson`->`adm1.geojson`, `departements.geojson`->`adm2.geojson` substitution only, do not otherwise touch): `docs/api/api_endpoints.md`, `docs/api/api_endpoints.fr.md`, `docs/architecture/backend_architecture.md`, `docs/architecture/backend_architecture.fr.md`, `docs/architecture/frontend_architecture.md`, `docs/architecture/frontend_architecture.fr.md`, `docs/guides/backend_developer_guide.md`, `docs/guides/backend_developer_guide.fr.md`
- Explicitly **not** touched: `docs/work-in-progress/zones-explorer-legacy/*` (historical snapshot, gitignored, out of scope)

**Interfaces:**
- Consumes: `AdministrativeZone.geojson_file` (`backend/app/domain/models/administrative_zone.py`), `backend/config/geo_sources.yml`'s `dest` field (read by both `backend/scripts/download_geo_data.py` and `backend/scripts/seed_zones.py`, both already read it dynamically - no code changes needed there).
- Produces: `administrative_zones` docs with `country_code: "FR"` now have `geojson_file` equal to `"FR/adm1.geojson"` (level 1) or `"FR/adm2.geojson"` (level 2).

- [ ] **Step 1: Update the source config**

```yaml
# backend/config/geo_sources.yml
sources:
  - dest: "FR/adm1.geojson"
    url: "https://france-geojson.gregoiredavid.fr/repo/regions.geojson"
    country: "FR"
    level: 1

  - dest: "FR/adm2.geojson"
    url: "https://france-geojson.gregoiredavid.fr/repo/departements.geojson"
    country: "FR"
    level: 2
```

- [ ] **Step 2: Update the hardcoded fixture paths in the two test files**

In `backend/tests/unit/test_zone_assigner.py`, replace every occurrence of `"FR/regions.geojson"` with `"FR/adm1.geojson"` (lines 312, 340) and `"FR/departements.geojson"` with `"FR/adm2.geojson"` (lines 317, 345).

In `backend/tests/integration/test_endpoints_zones.py`, replace `"FR/regions.geojson"` with `"FR/adm1.geojson"` (line 41) and `"FR/departements.geojson"` with `"FR/adm2.geojson"` (line 51).

- [ ] **Step 3: Run the affected tests to verify they still pass with the renamed strings**

Run: `.venv/bin/pytest tests/unit/test_zone_assigner.py tests/integration/test_endpoints_zones.py -v`
Expected: PASS (these tests only assert on the string value stored/read, not on a real file, so this is a pure rename with no behavior change)

- [ ] **Step 4: Write the one-shot DB migration script**

Mirrors the existing `backend/scripts/backfill_country_codes.py` pattern (backup-before-write, `--dry-run`, idempotent).

```python
#!/usr/bin/env python
# backend/scripts/rename_fr_geojson_files.py
# One-shot script: renames the `geojson_file` field on France's `administrative_zones`
# documents from the old `regions.geojson`/`departements.geojson` names to the
# generic `adm1.geojson`/`adm2.geojson` convention.
# Safety: copies the `administrative_zones` collection to a timestamped backup
# collection before writing anything.
# Idempotent: only matches documents still holding an old `geojson_file` value.
#
# Prerequisite: the physical files under backend/data/admin/FR/ must already be
# renamed (regions.geojson -> adm1.geojson, departements.geojson -> adm2.geojson)
# on this environment before running this script, otherwise /geo/FR/adm{1,2}.geojson
# will 404 until the rename is done.
#
# Usage (from backend/):
#   python scripts/rename_fr_geojson_files.py [--dry-run]

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.utils import now  # noqa: E402
from app.db.mongodb import get_client, get_collection, get_db  # noqa: E402

RENAMES = {
    "FR/regions.geojson": "FR/adm1.geojson",
    "FR/departements.geojson": "FR/adm2.geojson",
}


async def backup_administrative_zones_collection() -> str:
    """Copies the current `administrative_zones` collection into a timestamped backup.

    Returns:
        str: Name of the backup collection created.
    """
    db = get_db()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_name = f"administrative_zones_backup_{timestamp}"
    docs = await db.administrative_zones.find({}).to_list(length=None)
    if docs:
        await db[backup_name].insert_many(docs)
    print(f"[BACKUP] {len(docs)} document(s) copied to '{backup_name}'")
    return backup_name


async def main(dry_run: bool) -> None:
    """Renames `geojson_file` values for France's administrative zones.

    Args:
        dry_run (bool): If True, prints planned changes without writing.
    """
    if not dry_run:
        await backup_administrative_zones_collection()
    else:
        print("[DRY-RUN] Skipping backup (no write will be performed)")

    col = await get_collection("administrative_zones")
    updated = 0
    for old_value, new_value in RENAMES.items():
        matching = await col.count_documents({"geojson_file": old_value})
        if matching == 0:
            print(f"[SKIP] No document with geojson_file='{old_value}'")
            continue

        action = "Would update" if dry_run else "Updated"
        if not dry_run:
            await col.update_many(
                {"geojson_file": old_value},
                {"$set": {"geojson_file": new_value, "updated_at": now()}},
            )
        print(f"[{'DRY-RUN' if dry_run else 'DONE'}] {action} {matching} doc(s): '{old_value}' -> '{new_value}'")
        updated += matching

    print(f"\n[{'DRY-RUN' if dry_run else 'DONE'}] Total: {updated} document(s) {'would be ' if dry_run else ''}renamed")

    if not dry_run:
        client = get_client()
        client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned changes without writing anything (no backup, no writes).",
    )
    args = parser.parse_args()
    asyncio.run(main(args.dry_run))
```

- [ ] **Step 5: Rename the physical files locally**

```bash
cd backend/data/admin/FR
mv regions.geojson adm1.geojson
mv departements.geojson adm2.geojson
```

- [ ] **Step 6: Run the migration script against the local (= production, per project convention) database**

```bash
cd backend
ENV_FILE=<path-to-env-file> .venv/bin/python scripts/rename_fr_geojson_files.py --dry-run
# review the output, then:
ENV_FILE=<path-to-env-file> .venv/bin/python scripts/rename_fr_geojson_files.py
```

- [ ] **Step 7: Verify the static mount still serves the renamed files**

Run: `curl -sI http://localhost:8000/geo/FR/adm1.geojson` and `curl -sI http://localhost:8000/geo/FR/adm2.geojson` (adjust host/port to the running dev server)
Expected: `200 OK` for both, `404` for the old `/geo/FR/regions.geojson` / `/geo/FR/departements.geojson` URLs.

- [ ] **Step 8: Update the 8 doc files**

For each file below, replace `regions.geojson` -> `adm1.geojson` and `departements.geojson` -> `adm2.geojson` at the listed lines only (these docs have other, pre-existing staleness from earlier steps that is out of scope here - see the not-yet-scheduled Step 6 "README/roadmap doc updates"):

- `docs/api/api_endpoints.md:156,159`
- `docs/api/api_endpoints.fr.md:156,159`
- `docs/architecture/backend_architecture.md:81,107-108`
- `docs/architecture/backend_architecture.fr.md:81,107-108`
- `docs/architecture/frontend_architecture.md:72`
- `docs/architecture/frontend_architecture.fr.md:72`
- `docs/guides/backend_developer_guide.md:151-152`
- `docs/guides/backend_developer_guide.fr.md:151-152`

Example substitution (from `docs/api/api_endpoints.md:156-159`):

```diff
-- **URL**: `GET /geo/FR/regions.geojson`
+- **URL**: `GET /geo/FR/adm1.geojson`
 - **Description**: GeoJSON FeatureCollection French regions. Served by FastAPI StaticFiles.
-- **URL**: `GET /geo/FR/departements.geojson`
+- **URL**: `GET /geo/FR/adm2.geojson`
 - **Description**: GeoJSON FeatureCollection French departments.
```

- [ ] **Step 9: Run the full backend unit suite, lint, and mypy**

Run: `.venv/bin/pytest tests/unit/ -q && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app scripts`
Expected: all green

- [ ] **Step 10: Commit**

```bash
git add backend/config/geo_sources.yml backend/scripts/rename_fr_geojson_files.py backend/tests/unit/test_zone_assigner.py backend/tests/integration/test_endpoints_zones.py docs/api/api_endpoints.md docs/api/api_endpoints.fr.md docs/architecture/backend_architecture.md docs/architecture/backend_architecture.fr.md docs/architecture/frontend_architecture.md docs/architecture/frontend_architecture.fr.md docs/guides/backend_developer_guide.md docs/guides/backend_developer_guide.fr.md
git commit -m "chore(backend): rename FR geojson files to the adm1/adm2 convention

Modified files:
- backend/config/geo_sources.yml — dest paths adm1.geojson/adm2.geojson
- backend/scripts/rename_fr_geojson_files.py — one-shot geojson_file migration
- backend/tests/unit/test_zone_assigner.py, backend/tests/integration/test_endpoints_zones.py — updated fixture paths
- docs/api/api_endpoints.md, .fr.md, docs/architecture/backend_architecture.md, .fr.md, docs/architecture/frontend_architecture.md, .fr.md, docs/guides/backend_developer_guide.md, .fr.md — updated filename references"
```

- [ ] **Step 11: Manual, environment-specific follow-up (flag to the user, do not attempt yourself)**

The physical `backend/data/admin/FR/` files are gitignored. The VPS running production (no SSH access - user runs these commands themselves, per project convention) needs the same two `mv` commands from Step 5 run on its own filesystem before or immediately after this commit is deployed, otherwise `/geo/FR/adm1.geojson` and `/geo/FR/adm2.geojson` will 404 there until it's done. The DB migration (Step 6) only needs to run once since there is a single shared database.

---

### Task 3: `GET /admin/geo/missing-countries`

**Files:**
- Create: `backend/app/services/zones/geo_admin_service.py`
- Create: `backend/app/api/dto/geo_admin.py`
- Create: `backend/app/api/routes/admin_geo.py`
- Modify: `backend/app/api/routes/__init__.py`
- Test: `backend/tests/unit/test_geo_admin_service.py` (new)
- Test: `backend/tests/unit/test_admin_geo_routes.py` (new, missing-countries part; upload part added in Task 4)

**Interfaces:**
- Consumes: `app.api.deps.require_admin` (`backend/app/api/deps.py:17`), `app.db.mongodb.get_collection`, `app.core.settings.get_settings().geo_data_dir` (default `"data/admin"`, resolved relative to CWD like `app/main.py:79`).
- Produces: `async def get_missing_countries() -> list[MissingCountryItem]` in `geo_admin_service.py`, consumed by the route in this task and reusable as-is (no change) once Task 4 adds the sibling upload function to the same service module. `GET /admin/geo/missing-countries` -> `MissingCountriesResponse`.

- [ ] **Step 1: Write the failing service unit test**

```python
# backend/tests/unit/test_geo_admin_service.py
"""Tests for app.services.zones.geo_admin_service."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.zones import geo_admin_service as svc


def _mock_aggregate_collection(docs: list[dict]) -> MagicMock:
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=docs)
    coll = MagicMock()
    coll.aggregate.return_value = cursor
    return coll


class TestGetMissingCountries:
    @pytest.mark.asyncio
    async def test_excludes_countries_with_existing_directory(self, tmp_path: Path):
        (tmp_path / "FR").mkdir()
        docs = [
            {"_id": "FR", "found_count": 100},
            {"_id": "DE", "found_count": 5},
        ]
        with (
            patch.object(
                svc, "get_collection", AsyncMock(return_value=_mock_aggregate_collection(docs))
            ),
            patch.object(svc, "_geo_data_dir", return_value=tmp_path),
        ):
            result = await svc.get_missing_countries()

        assert result == [{"code": "DE", "found_count": 5}]

    @pytest.mark.asyncio
    async def test_sorted_by_found_count_desc(self, tmp_path: Path):
        docs = [
            {"_id": "DE", "found_count": 5},
            {"_id": "ES", "found_count": 42},
        ]
        with (
            patch.object(
                svc, "get_collection", AsyncMock(return_value=_mock_aggregate_collection(docs))
            ),
            patch.object(svc, "_geo_data_dir", return_value=tmp_path),
        ):
            result = await svc.get_missing_countries()

        assert [r["code"] for r in result] == ["ES", "DE"]

    @pytest.mark.asyncio
    async def test_empty_when_no_found_caches(self, tmp_path: Path):
        with (
            patch.object(svc, "get_collection", AsyncMock(return_value=_mock_aggregate_collection([]))),
            patch.object(svc, "_geo_data_dir", return_value=tmp_path),
        ):
            result = await svc.get_missing_countries()

        assert result == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_geo_admin_service.py -v`
Expected: FAIL - `ModuleNotFoundError: No module named 'app.services.zones.geo_admin_service'`

- [ ] **Step 3: Write the service module**

```python
# backend/app/services/zones/geo_admin_service.py
# Admin-only service for managing GeoJSON coverage of administrative zones.
# Powers the /admin/geo endpoints (missing-countries detection, file upload/ingestion).

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.core.settings import get_settings
from app.db.mongodb import get_collection

log = logging.getLogger(__name__)


def _geo_data_dir() -> Path:
    """Resolves the root directory storing GeoJSON files, relative to the process CWD.

    Returns:
        Path: Same directory `app.main`'s `/geo` StaticFiles mount serves from.
    """
    return Path(get_settings().geo_data_dir)


async def get_missing_countries() -> list[dict]:
    """Returns countries with found caches but no GeoJSON directory on disk yet.

    Description:
        Aggregates `found_caches` (all users - deliberately not scoped to one user,
        so that a cache found by many users weighs more than one found by a single
        user) grouped by `cache.zones.country`, then excludes any country code that
        already has a `{geo_data_dir}/{code}/` directory.

    Returns:
        list[dict]: `{"code": str, "found_count": int}`, sorted by `found_count` desc.
    """
    data_dir = _geo_data_dir()
    found_col = await get_collection("found_caches")
    pipeline = [
        {
            "$lookup": {
                "from": "caches",
                "localField": "cache_id",
                "foreignField": "_id",
                "as": "cache",
            }
        },
        {"$unwind": "$cache"},
        {"$match": {"cache.zones.country": {"$ne": None}}},
        {"$group": {"_id": "$cache.zones.country", "found_count": {"$sum": 1}}},
    ]
    raw = await found_col.aggregate(pipeline).to_list(length=None)  # type: ignore[arg-type]

    missing = [
        {"code": doc["_id"], "found_count": doc["found_count"]}
        for doc in raw
        if not (data_dir / doc["_id"]).is_dir()
    ]
    missing.sort(key=lambda m: m["found_count"], reverse=True)
    return missing
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_geo_admin_service.py -v`
Expected: PASS (3/3)

- [ ] **Step 5: Write the DTOs**

```python
# backend/app/api/dto/geo_admin.py
# Input/output DTOs for the /admin/geo endpoints.

from __future__ import annotations

from pydantic import BaseModel


class MissingCountryItem(BaseModel):
    """A country with found caches but no GeoJSON coverage on disk yet.

    Attributes:
        code (str): ISO country code, e.g. "DE".
        found_count (int): Number of found-cache records in this country, across all users.
    """

    code: str
    found_count: int


class MissingCountriesResponse(BaseModel):
    """Response for GET /admin/geo/missing-countries.

    Attributes:
        items (list[MissingCountryItem]): Missing countries, sorted by found_count desc.
    """

    items: list[MissingCountryItem]
```

- [ ] **Step 6: Write the route module and register it**

```python
# backend/app/api/routes/admin_geo.py
# Admin-only endpoints for managing GeoJSON coverage of administrative zones.

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import require_admin
from app.api.dto.geo_admin import MissingCountriesResponse
from app.services.zones.geo_admin_service import get_missing_countries

router = APIRouter(
    prefix="/admin/geo",
    tags=["Admin - Geo"],
    dependencies=[Depends(require_admin)],
)


@router.get(
    "/missing-countries",
    response_model=MissingCountriesResponse,
    summary="List countries with found caches but no GeoJSON coverage",
)
async def list_missing_countries() -> MissingCountriesResponse:
    """Returns countries that need their GeoJSON files uploaded.

    Returns:
        MissingCountriesResponse: Countries with found caches but no `{code}/` directory
            under the GeoJSON data root, sorted by found-cache count descending.
    """
    items = await get_missing_countries()
    return MissingCountriesResponse(items=items)
```

```python
# backend/app/api/routes/__init__.py
from .admin_geo import router as admin_geo_router
# ... (keep existing imports, insert alphabetically between .admin_geo and .auth)

routers = [
    health_router,
    referentials_router,
    auth_router,
    admin_geo_router,
    caches_router,
    caches_elevation_router,
    caches_geocoding_router,
    challenges_router,
    my_challenges_router,
    my_challenge_tasks_router,
    my_challenge_progress_router,
    my_challenge_targets_router,
    my_profile_router,
    maintenance_router,
    zones_router,
]
```

- [ ] **Step 7: Write the route unit test**

```python
# backend/tests/unit/test_admin_geo_routes.py
"""Tests for /admin/geo routes."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import admin_geo as admin_geo_module
from app.core.bson_utils import PyObjectId
from app.core.security import get_current_user
from app.domain.models.user import User


def _make_app(role: str) -> FastAPI:
    app = FastAPI()
    app.include_router(admin_geo_module.router)
    user = User(
        id=PyObjectId(ObjectId()), username="u", email="u@example.com", role=role
    )
    app.dependency_overrides[get_current_user] = lambda: user
    return app


class TestListMissingCountries:
    @pytest.mark.asyncio
    async def test_returns_items_for_admin(self):
        items = [{"code": "DE", "found_count": 5}]
        with patch.object(
            admin_geo_module, "get_missing_countries", AsyncMock(return_value=items)
        ):
            app = _make_app("admin")
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/admin/geo/missing-countries")

        assert response.status_code == 200
        assert response.json() == {"items": items}

    @pytest.mark.asyncio
    async def test_forbidden_for_non_admin(self):
        with patch.object(admin_geo_module, "get_missing_countries", AsyncMock()) as mock_get:
            app = _make_app("user")
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/admin/geo/missing-countries")

        assert response.status_code == 403
        mock_get.assert_not_awaited()
```

- [ ] **Step 8: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_admin_geo_routes.py -v`
Expected: PASS (2/2)

- [ ] **Step 9: Run the full unit suite, lint, and mypy**

Run: `.venv/bin/pytest tests/unit/ -q && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app`
Expected: all green

- [ ] **Step 10: Commit**

```bash
git add backend/app/services/zones/geo_admin_service.py backend/app/api/dto/geo_admin.py backend/app/api/routes/admin_geo.py backend/app/api/routes/__init__.py backend/tests/unit/test_geo_admin_service.py backend/tests/unit/test_admin_geo_routes.py
git commit -m "feat(backend): add GET /admin/geo/missing-countries endpoint

Modified files:
- backend/app/services/zones/geo_admin_service.py — new service, get_missing_countries()
- backend/app/api/dto/geo_admin.py — new DTOs for /admin/geo
- backend/app/api/routes/admin_geo.py — new admin-only router
- backend/app/api/routes/__init__.py — register admin_geo_router
- backend/tests/unit/test_geo_admin_service.py, backend/tests/unit/test_admin_geo_routes.py — unit tests"
```

---

### Task 4: `POST /admin/geo/{country_code}/upload`

**Files:**
- Modify: `backend/app/services/zones/geo_admin_service.py`
- Modify: `backend/app/api/dto/geo_admin.py`
- Modify: `backend/app/api/routes/admin_geo.py`
- Test: `backend/tests/unit/test_geo_admin_service.py`
- Test: `backend/tests/unit/test_admin_geo_routes.py`

**Interfaces:**
- Consumes: `app.core.middleware.read_upload_file_with_limit(file, max_bytes) -> bytes` (`backend/app/core/middleware.py:14`), `app.core.settings.get_settings().max_upload_bytes`, `app.db.mongodb.get_collection`.
- Produces: `async def upload_zone_level(country_code: str, level: int, content: bytes) -> UploadResult` in `geo_admin_service.py`, raising `ValueError` on contract violations (caught by the route and turned into a 422). `POST /admin/geo/{country_code}/upload?level={0,1,2}` (multipart file body) -> `GeoUploadResponse`.

- [ ] **Step 1: Write the failing service unit tests**

```python
# backend/tests/unit/test_geo_admin_service.py
# append to the existing file

import json as jsonlib

from bson import ObjectId


def _mock_upsert_collection() -> MagicMock:
    coll = MagicMock()
    coll.update_one = AsyncMock(return_value=MagicMock(upserted_id=ObjectId()))
    return coll


def _feature(code: str, nom: str, bbox: list[float], parent_code: str | None = None) -> dict:
    props = {"code": code, "nom": nom, "feature_code": code}
    if parent_code is not None:
        props["parent_code"] = parent_code
    return {"type": "Feature", "properties": props, "bbox": bbox, "geometry": {"type": "Point", "coordinates": [0, 0]}}


class TestUploadZoneLevel:
    @pytest.mark.asyncio
    async def test_rejects_invalid_json(self, tmp_path: Path):
        with patch.object(svc, "_geo_data_dir", return_value=tmp_path):
            with pytest.raises(ValueError, match="not valid JSON"):
                await svc.upload_zone_level("FR", 1, b"not json")

    @pytest.mark.asyncio
    async def test_rejects_non_feature_collection(self, tmp_path: Path):
        content = jsonlib.dumps({"type": "Feature"}).encode()
        with patch.object(svc, "_geo_data_dir", return_value=tmp_path):
            with pytest.raises(ValueError, match="FeatureCollection"):
                await svc.upload_zone_level("FR", 1, content)

    @pytest.mark.asyncio
    async def test_rejects_feature_missing_required_property(self, tmp_path: Path):
        fc = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": None}]}
        content = jsonlib.dumps(fc).encode()
        with patch.object(svc, "_geo_data_dir", return_value=tmp_path):
            with pytest.raises(ValueError, match="'code'"):
                await svc.upload_zone_level("FR", 1, content)

    @pytest.mark.asyncio
    async def test_rejects_level_2_feature_missing_parent_code(self, tmp_path: Path):
        fc = {
            "type": "FeatureCollection",
            "features": [_feature("38", "Isère", [0, 0, 1, 1])],
        }
        content = jsonlib.dumps(fc).encode()
        with patch.object(svc, "_geo_data_dir", return_value=tmp_path):
            with pytest.raises(ValueError, match="parent_code"):
                await svc.upload_zone_level("FR", 2, content)

    @pytest.mark.asyncio
    async def test_writes_file_and_upserts_level_1(self, tmp_path: Path):
        fc = {
            "type": "FeatureCollection",
            "features": [_feature("84", "Auvergne-Rhône-Alpes", [4.0, 44.0, 7.0, 46.5])],
        }
        content = jsonlib.dumps(fc).encode()
        col = _mock_upsert_collection()
        with (
            patch.object(svc, "_geo_data_dir", return_value=tmp_path),
            patch.object(svc, "get_collection", AsyncMock(return_value=col)),
        ):
            result = await svc.upload_zone_level("FR", 1, content)

        written = tmp_path / "FR" / "adm1.geojson"
        assert written.exists()
        assert jsonlib.loads(written.read_text()) == fc
        assert result == {"country_code": "FR", "level": 1, "features_count": 1, "inserted": 1, "updated": 0}
        col.update_one.assert_awaited_once_with(
            {"code": "FR-84", "level": 1},
            {
                "$set": {
                    "code": "FR-84",
                    "country_code": "FR",
                    "level": 1,
                    "name": "Auvergne-Rhône-Alpes",
                    "parent_code": None,
                    "geojson_file": "FR/adm1.geojson",
                    "feature_code": "84",
                    "bbox": [4.0, 44.0, 7.0, 46.5],
                }
            },
            upsert=True,
        )

    @pytest.mark.asyncio
    async def test_level_0_writes_file_without_db_upsert(self, tmp_path: Path):
        fc = {"type": "FeatureCollection", "features": [_feature("FR", "France", [-5, 41, 10, 51]) ]}
        content = jsonlib.dumps(fc).encode()
        with (
            patch.object(svc, "_geo_data_dir", return_value=tmp_path),
            patch.object(svc, "get_collection", AsyncMock()) as mock_get_collection,
        ):
            result = await svc.upload_zone_level("FR", 0, content)

        assert (tmp_path / "FR" / "adm0.geojson").exists()
        assert result == {"country_code": "FR", "level": 0, "features_count": 1, "inserted": 0, "updated": 0}
        mock_get_collection.assert_not_awaited()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/unit/test_geo_admin_service.py::TestUploadZoneLevel -v`
Expected: FAIL - `AttributeError: module 'app.services.zones.geo_admin_service' has no attribute 'upload_zone_level'`

- [ ] **Step 3: Extend the service module**

```python
# backend/app/services/zones/geo_admin_service.py
# add near the top

REQUIRED_FEATURE_PROPERTIES = ("code", "nom", "feature_code")


def _validate_feature_collection(payload: dict, level: int) -> list[dict]:
    """Validates the normalized GeoJSON contract and returns its features.

    Args:
        payload (dict): Parsed JSON content.
        level (int): Administrative level being uploaded (0, 1 or 2).

    Returns:
        list[dict]: The FeatureCollection's `features` list.

    Raises:
        ValueError: If the payload does not follow the normalized contract
            (see ~/projets/geo_json/CONTRACT.md).
    """
    if payload.get("type") != "FeatureCollection":
        raise ValueError("Payload is not a GeoJSON FeatureCollection.")

    features = payload.get("features")
    if not isinstance(features, list):
        raise ValueError("FeatureCollection has no 'features' array.")

    for i, feature in enumerate(features):
        props = feature.get("properties", {})
        for field in REQUIRED_FEATURE_PROPERTIES:
            if not props.get(field):
                raise ValueError(f"Feature {i} is missing required property '{field}'.")
        if level == 2 and not props.get("parent_code"):
            raise ValueError(f"Feature {i} is missing required property 'parent_code' (level 2).")
        if "bbox" not in feature:
            raise ValueError(f"Feature {i} is missing the GeoJSON 'bbox' member.")

    return features


async def upload_zone_level(country_code: str, level: int, content: bytes) -> dict:
    """Validates, stores, and (for level 1/2) ingests a normalized GeoJSON file.

    Description:
        Writes the raw file to `{geo_data_dir}/{country_code}/adm{level}.geojson`.
        For level 1/2, also upserts one `administrative_zones` document per feature,
        trusting the file's own precomputed `parent_code`/`bbox` (unlike
        `scripts/seed_zones.py`, which recomputes them via Shapely for the older,
        non-normalized source files). Level 0 is stored for forward-compatibility
        only - no collection is seeded from it (see Global Constraints).

    Args:
        country_code (str): ISO 3166-1 alpha-2 code, e.g. "FR".
        level (int): Administrative level - 0, 1 or 2.
        content (bytes): Raw uploaded file content.

    Returns:
        dict: `{country_code, level, features_count, inserted, updated}`.

    Raises:
        ValueError: If the content is not valid JSON or violates the normalized contract.
    """
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("Uploaded file is not valid JSON.") from exc

    features = _validate_feature_collection(payload, level)

    dest_rel = f"{country_code}/adm{level}.geojson"
    dest_path = _geo_data_dir() / dest_rel
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(content)

    inserted = updated = 0
    if level in (1, 2):
        collection = await get_collection("administrative_zones")
        for feature in features:
            props = feature["properties"]
            feature_code = str(props["code"])
            zone_doc = {
                "code": f"{country_code}-{feature_code}",
                "country_code": country_code,
                "level": level,
                "name": props["nom"],
                "parent_code": props.get("parent_code"),
                "geojson_file": dest_rel,
                "feature_code": feature_code,
                "bbox": feature["bbox"],
            }
            result = await collection.update_one(
                {"code": zone_doc["code"], "level": level},
                {"$set": zone_doc},
                upsert=True,
            )
            if result.upserted_id:
                inserted += 1
            else:
                updated += 1

    return {
        "country_code": country_code,
        "level": level,
        "features_count": len(features),
        "inserted": inserted,
        "updated": updated,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_geo_admin_service.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Extend the DTOs**

```python
# backend/app/api/dto/geo_admin.py
# append

class GeoUploadResponse(BaseModel):
    """Response for POST /admin/geo/{country_code}/upload.

    Attributes:
        country_code (str): ISO country code the file was uploaded for.
        level (int): Administrative level (0, 1 or 2).
        features_count (int): Number of features in the uploaded FeatureCollection.
        inserted (int): Number of new administrative_zones documents created (0 at level 0).
        updated (int): Number of existing administrative_zones documents updated (0 at level 0).
    """

    country_code: str
    level: int
    features_count: int
    inserted: int
    updated: int
```

- [ ] **Step 6: Add the route**

```python
# backend/app/api/routes/admin_geo.py
# replace the two-line import block and add the new route

import re

from fastapi import APIRouter, Depends, File, HTTPException, Path, Query, UploadFile, status

from app.api.deps import require_admin
from app.api.dto.geo_admin import GeoUploadResponse, MissingCountriesResponse
from app.core.middleware import read_upload_file_with_limit
from app.core.settings import get_settings
from app.services.zones.geo_admin_service import get_missing_countries, upload_zone_level

_COUNTRY_CODE_RE = re.compile(r"^[A-Z]{2}$")

# ... router + list_missing_countries unchanged, then:


@router.post(
    "/{country_code}/upload",
    response_model=GeoUploadResponse,
    summary="Upload a normalized GeoJSON file for one administrative level",
)
async def upload_geo_file(
    country_code: Annotated[str, Path(description="ISO 3166-1 alpha-2 code, e.g. 'FR'.")],
    level: Annotated[int, Query(ge=0, le=2, description="Administrative level: 0, 1 or 2.")],
    file: Annotated[UploadFile, File(..., description="Normalized adm{level}.geojson file.")],
) -> GeoUploadResponse:
    """Uploads and ingests a normalized GeoJSON file for one country/level.

    Description:
        See ~/projets/geo_json/CONTRACT.md for the expected feature schema
        (`code`, `nom`, `feature_code`, `parent_code` for level 2, `bbox`).

    Args:
        country_code (str): ISO 3166-1 alpha-2 code, uppercase.
        level (int): Administrative level - 0, 1 or 2.
        file (UploadFile): The normalized GeoJSON FeatureCollection.

    Returns:
        GeoUploadResponse: Ingestion summary.

    Raises:
        422: If country_code is not a 2-letter uppercase code, or the file violates the contract.
        413: If the file exceeds the configured upload size limit.
    """
    if not _COUNTRY_CODE_RE.match(country_code):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="country_code must be a 2-letter uppercase ISO code, e.g. 'FR'.",
        )

    settings = get_settings()
    content = await read_upload_file_with_limit(file, settings.max_upload_bytes)

    try:
        result = await upload_zone_level(country_code, level, content)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    return GeoUploadResponse(**result)
```

Also add `from typing import Annotated` to the top of `admin_geo.py` if not already present.

- [ ] **Step 7: Write the route unit tests**

```python
# backend/tests/unit/test_admin_geo_routes.py
# append

class TestUploadGeoFile:
    @pytest.mark.asyncio
    async def test_uploads_for_admin(self):
        result = {"country_code": "FR", "level": 1, "features_count": 1, "inserted": 1, "updated": 0}
        with patch.object(admin_geo_module, "upload_zone_level", AsyncMock(return_value=result)):
            app = _make_app("admin")
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/admin/geo/FR/upload",
                    params={"level": 1},
                    files={"file": ("adm1.geojson", b'{"type":"FeatureCollection","features":[]}', "application/json")},
                )

        assert response.status_code == 200
        assert response.json() == result

    @pytest.mark.asyncio
    async def test_rejects_invalid_country_code(self):
        with patch.object(admin_geo_module, "upload_zone_level", AsyncMock()) as mock_upload:
            app = _make_app("admin")
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/admin/geo/fra/upload",
                    params={"level": 1},
                    files={"file": ("x.geojson", b"{}", "application/json")},
                )

        assert response.status_code == 422
        mock_upload.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_returns_422_on_contract_violation(self):
        with patch.object(
            admin_geo_module, "upload_zone_level", AsyncMock(side_effect=ValueError("bad contract"))
        ):
            app = _make_app("admin")
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/admin/geo/FR/upload",
                    params={"level": 1},
                    files={"file": ("x.geojson", b'{"type":"FeatureCollection","features":[]}', "application/json")},
                )

        assert response.status_code == 422
        assert response.json()["detail"] == "bad contract"

    @pytest.mark.asyncio
    async def test_forbidden_for_non_admin(self):
        with patch.object(admin_geo_module, "upload_zone_level", AsyncMock()) as mock_upload:
            app = _make_app("user")
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/admin/geo/FR/upload",
                    params={"level": 1},
                    files={"file": ("x.geojson", b"{}", "application/json")},
                )

        assert response.status_code == 403
        mock_upload.assert_not_awaited()
```

- [ ] **Step 8: Run test to verify it passes**

Run: `.venv/bin/pytest tests/unit/test_admin_geo_routes.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 9: Run the full unit suite with coverage, lint, and mypy**

Run: `.venv/bin/pytest tests/unit/ --cov=app --cov-report=term-missing -q && .venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy app`
Expected: all green; `app/services/zones/geo_admin_service.py` and `app/api/routes/admin_geo.py` at or near 100% (check the term-missing report; per `codecov.yml` this patch must stay >= 95%, add any missed branch's test before moving on)

- [ ] **Step 10: Commit**

```bash
git add backend/app/services/zones/geo_admin_service.py backend/app/api/dto/geo_admin.py backend/app/api/routes/admin_geo.py backend/tests/unit/test_geo_admin_service.py backend/tests/unit/test_admin_geo_routes.py
git commit -m "feat(backend): add POST /admin/geo/{country_code}/upload endpoint

Modified files:
- backend/app/services/zones/geo_admin_service.py — add upload_zone_level()
- backend/app/api/dto/geo_admin.py — add GeoUploadResponse
- backend/app/api/routes/admin_geo.py — add the upload route
- backend/tests/unit/test_geo_admin_service.py, backend/tests/unit/test_admin_geo_routes.py — unit tests"
```

---

### Task 5: Frontend `Country` type and `fetchCountries()`

**Files:**
- Modify: `frontend/src/types/zones.ts`
- Modify: `frontend/src/composables/useZones.ts`
- Test: `frontend/tests/unit/use-zones.spec.ts`

**Interfaces:**
- Produces: `interface Country { code: string; name: string }` and `fetchCountries(): Promise<Country[]>` on `useZones()`'s return object. Consumed by Task 7 (World view).

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/tests/unit/use-zones.spec.ts
// append at the end of the file, before the final closing (keep existing describes untouched)

describe("fetchCountries", () => {
  it("calls GET /countries", async () => {
    mockGet.mockResolvedValueOnce({ data: [] });
    const { fetchCountries } = useZones();

    await fetchCountries();

    expect(mockGet).toHaveBeenCalledWith("/countries");
  });

  it("returns the country list on success", async () => {
    const countries = [
      { code: "FR", name: "France" },
      { code: "DE", name: "Allemagne" },
    ];
    mockGet.mockResolvedValueOnce({ data: countries });
    const { fetchCountries } = useZones();

    const result = await fetchCountries();

    expect(result).toEqual(countries);
  });

  it("returns an empty array on error", async () => {
    mockGet.mockRejectedValueOnce(new Error("network"));
    const { fetchCountries } = useZones();

    const result = await fetchCountries();

    expect(result).toEqual([]);
  });
});
```

Also update the import line at the top of the spec file:

```typescript
import type { ZoneListItem, ZoneDetail, Country } from "@/types/zones";
```

(Note: `Country` import is added for type-checking parity even though this spec doesn't construct `Country` fixtures directly - `ZoneListItem`/`ZoneDetail` stay as-is.)

- [ ] **Step 2: Run test to verify it fails**

Run (from `frontend/`): `npx vitest run tests/unit/use-zones.spec.ts`
Expected: FAIL - `fetchCountries is not a function`

- [ ] **Step 3: Add the `Country` type**

```typescript
// frontend/src/types/zones.ts
// append

/** Referential country entry, independent of the current user's found caches. */
export interface Country {
  code: string;
  name: string;
}
```

- [ ] **Step 4: Add `fetchCountries()` to the composable**

```typescript
// frontend/src/composables/useZones.ts
// update the type import at the top:
import type { ZoneListItem, ZoneDetail, Country } from "@/types/zones";

// add a new function, alongside fetchZones/fetchZoneDetail, before the return statement:

  /**
   * Fetches the full referential list of countries (independent of the
   * current user's found caches).
   */
  async function fetchCountries(): Promise<Country[]> {
    loading.value = true;
    error.value = null;
    try {
      const { data } = await api.get<Country[]>("/countries");
      return data;
    } catch (err: unknown) {
      error.value = handleApiError(err).message;
      return [];
    } finally {
      loading.value = false;
    }
  }

// update the return statement:
  return {
    loading,
    error,
    fetchZones,
    fetchZoneDetail,
    fetchCountries,
  };
```

- [ ] **Step 5: Run test to verify it passes**

Run: `npx vitest run tests/unit/use-zones.spec.ts`
Expected: PASS (all tests in the file)

- [ ] **Step 6: Run the full frontend checks**

Run: `npx vue-tsc --noEmit && npx eslint . && npx vitest run`
Expected: all green

- [ ] **Step 7: Commit**

```bash
git add frontend/src/types/zones.ts frontend/src/composables/useZones.ts frontend/tests/unit/use-zones.spec.ts
git commit -m "feat(frontend): add Country type and fetchCountries()

Modified files:
- frontend/src/types/zones.ts — add Country interface
- frontend/src/composables/useZones.ts — add fetchCountries()
- frontend/tests/unit/use-zones.spec.ts — tests for fetchCountries"
```

---

### Task 6: `TypeFilterDropdown.vue` (checkboxes-in-dropdown multi-select)

**Files:**
- Create: `frontend/src/components/zones/TypeFilterDropdown.vue`
- Test: `frontend/tests/unit/type-filter-dropdown.spec.ts`

**Interfaces:**
- Produces: `<TypeFilterDropdown :options="{code,name}[]" v-model="selectedCodes: string[]" />`, emitting `update:modelValue` on every toggle. Consumed by Tasks 8/9 (`ZonesExplorer.vue`).

- [ ] **Step 1: Write the failing test**

```typescript
// frontend/tests/unit/type-filter-dropdown.spec.ts
import { describe, it, expect } from "vitest";
import { mount } from "@vue/test-utils";
import TypeFilterDropdown from "@/components/zones/TypeFilterDropdown.vue";

const options = [
  { code: "traditional", name: "Traditional" },
  { code: "mystery", name: "Mystery" },
];

describe("TypeFilterDropdown", () => {
  it("is closed by default", () => {
    const wrapper = mount(TypeFilterDropdown, {
      props: { options, modelValue: [] },
    });
    expect(wrapper.find('[data-testid="dropdown-panel"]').exists()).toBe(
      false,
    );
  });

  it("opens the panel on toggle button click", async () => {
    const wrapper = mount(TypeFilterDropdown, {
      props: { options, modelValue: [] },
    });
    await wrapper.find('[data-testid="dropdown-toggle"]').trigger("click");
    expect(wrapper.find('[data-testid="dropdown-panel"]').exists()).toBe(
      true,
    );
  });

  it("renders one checkbox per option", async () => {
    const wrapper = mount(TypeFilterDropdown, {
      props: { options, modelValue: [] },
    });
    await wrapper.find('[data-testid="dropdown-toggle"]').trigger("click");
    const checkboxes = wrapper.findAll('input[type="checkbox"]');
    expect(checkboxes).toHaveLength(2);
  });

  it("reflects modelValue as checked state", async () => {
    const wrapper = mount(TypeFilterDropdown, {
      props: { options, modelValue: ["mystery"] },
    });
    await wrapper.find('[data-testid="dropdown-toggle"]').trigger("click");
    const checkboxes = wrapper.findAll('input[type="checkbox"]');
    expect((checkboxes[0]!.element as HTMLInputElement).checked).toBe(false);
    expect((checkboxes[1]!.element as HTMLInputElement).checked).toBe(true);
  });

  it("emits update:modelValue with the code added when checked", async () => {
    const wrapper = mount(TypeFilterDropdown, {
      props: { options, modelValue: [] },
    });
    await wrapper.find('[data-testid="dropdown-toggle"]').trigger("click");
    await wrapper.findAll('input[type="checkbox"]')[0]!.setValue(true);
    expect(wrapper.emitted("update:modelValue")).toEqual([[["traditional"]]]);
  });

  it("emits update:modelValue with the code removed when unchecked", async () => {
    const wrapper = mount(TypeFilterDropdown, {
      props: { options, modelValue: ["traditional", "mystery"] },
    });
    await wrapper.find('[data-testid="dropdown-toggle"]').trigger("click");
    await wrapper.findAll('input[type="checkbox"]')[0]!.setValue(false);
    expect(wrapper.emitted("update:modelValue")).toEqual([[["mystery"]]]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/unit/type-filter-dropdown.spec.ts`
Expected: FAIL - `Failed to resolve component: TypeFilterDropdown` (file doesn't exist)

- [ ] **Step 3: Write the component**

```vue
<!-- frontend/src/components/zones/TypeFilterDropdown.vue -->
<template>
  <div class="relative inline-block text-left">
    <button
      data-testid="dropdown-toggle"
      type="button"
      class="border border-gray-200 rounded px-2 py-1 text-xs text-gray-700 bg-white dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300"
      @click="open = !open"
    >
      {{ label }}
    </button>
    <div
      v-if="open"
      data-testid="dropdown-panel"
      class="absolute z-30 mt-1 w-48 bg-white rounded-lg shadow-lg border border-gray-200 p-2 dark:bg-gray-900 dark:border-gray-700"
    >
      <label
        v-for="opt in options"
        :key="opt.code"
        class="flex items-center gap-2 px-1 py-1 text-xs text-gray-700 dark:text-gray-300"
      >
        <input
          type="checkbox"
          :checked="modelValue.includes(opt.code)"
          @change="toggle(opt.code, ($event.target as HTMLInputElement).checked)"
        />
        <span>{{ opt.name }}</span>
      </label>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";

interface TypeOption {
  code: string;
  name: string;
}

const props = defineProps<{
  options: TypeOption[];
  modelValue: string[];
}>();

const emit = defineEmits<{
  (e: "update:modelValue", value: string[]): void;
}>();

const open = ref(false);

const label = computed(() =>
  props.modelValue.length > 0
    ? `Types (${props.modelValue.length})`
    : "Tous les types",
);

function toggle(code: string, checked: boolean) {
  const next = checked
    ? [...props.modelValue, code]
    : props.modelValue.filter((c) => c !== code);
  emit("update:modelValue", next);
}
</script>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run tests/unit/type-filter-dropdown.spec.ts`
Expected: PASS (6/6)

- [ ] **Step 5: Run the full frontend checks**

Run: `npx vue-tsc --noEmit && npx eslint . && npx vitest run`
Expected: all green

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/zones/TypeFilterDropdown.vue frontend/tests/unit/type-filter-dropdown.spec.ts
git commit -m "feat(frontend): add TypeFilterDropdown checkbox multi-select

Modified files:
- frontend/src/components/zones/TypeFilterDropdown.vue — new reusable component
- frontend/tests/unit/type-filter-dropdown.spec.ts — unit tests"
```

---

### Task 7: `ZonesExplorer.vue` - World view (level 0)

**Files:**
- Create: `frontend/src/pages/caches/ZonesExplorer.vue`
- Test: `frontend/tests/unit/zones-explorer.spec.ts`

**Interfaces:**
- Consumes: `useZones().fetchCountries()`, `useZones().fetchZones(0)` (Task 5), `Country`/`ZoneListItem` types.
- Produces: internal reactive `level` (`ref<0 | 1 | 2>`), `selectedCountry` (`ref<string | null>`), and a `drillToCountry(code: string)` function - both consumed unchanged by Tasks 8/9, which extend this same file.

- [ ] **Step 1: Write the failing test (World view only)**

```typescript
// frontend/tests/unit/zones-explorer.spec.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";

const mockFetchCountries = vi.hoisted(() => vi.fn().mockResolvedValue([]));
const mockFetchZones = vi.hoisted(() => vi.fn().mockResolvedValue([]));
const mockFetchZoneDetail = vi.hoisted(() => vi.fn().mockResolvedValue(null));
const mockLoading = vi.hoisted(() => ({ value: false }));
const mockGet = vi.hoisted(() => vi.fn().mockResolvedValue({ data: {} }));

vi.mock("@/composables/useZones", () => ({
  useZones: () => ({
    loading: mockLoading,
    error: { value: null },
    fetchCountries: mockFetchCountries,
    fetchZones: mockFetchZones,
    fetchZoneDetail: mockFetchZoneDetail,
  }),
}));

vi.mock("@/api/http", () => ({ default: { get: mockGet } }));

vi.mock("@/components/map/MapBase.vue", () => ({
  default: {
    name: "MapBase",
    template: '<div data-testid="map-base" />',
    expose: ["getMap"],
    emits: ["ready"],
  },
}));

vi.mock("leaflet", () => ({
  default: { geoJSON: vi.fn(), map: vi.fn() },
}));

import ZonesExplorer from "@/pages/caches/ZonesExplorer.vue";

beforeEach(() => vi.clearAllMocks());

describe("ZonesExplorer - World view", () => {
  it("fetches countries and level-0 zones on mount", async () => {
    mockFetchCountries.mockResolvedValueOnce([{ code: "FR", name: "France" }]);
    mockFetchZones.mockResolvedValueOnce([
      { code: "FR", name: "France", cache_count: 12 },
    ]);

    mount(ZonesExplorer);
    await flushPromises();

    expect(mockFetchCountries).toHaveBeenCalled();
    expect(mockFetchZones).toHaveBeenCalledWith(0);
  });

  it("lists countries with finds as clickable, in the found group", async () => {
    mockFetchCountries.mockResolvedValueOnce([
      { code: "FR", name: "France" },
      { code: "DE", name: "Allemagne" },
    ]);
    mockFetchZones.mockResolvedValueOnce([
      { code: "FR", name: "France", cache_count: 12 },
    ]);

    const wrapper = mount(ZonesExplorer);
    await flushPromises();

    const found = wrapper.find('[data-testid="world-found-group"]');
    expect(found.text()).toContain("France");
    expect(found.text()).not.toContain("Allemagne");
  });

  it("lists countries without finds in the non-clickable group", async () => {
    mockFetchCountries.mockResolvedValueOnce([
      { code: "FR", name: "France" },
      { code: "DE", name: "Allemagne" },
    ]);
    mockFetchZones.mockResolvedValueOnce([
      { code: "FR", name: "France", cache_count: 12 },
    ]);

    const wrapper = mount(ZonesExplorer);
    await flushPromises();

    const empty = wrapper.find('[data-testid="world-empty-group"]');
    expect(empty.text()).toContain("Allemagne");
    const disabledItem = empty.find("li");
    expect(disabledItem.find("button").exists()).toBe(false);
  });

  it("drills into a country on click", async () => {
    mockFetchCountries.mockResolvedValueOnce([{ code: "FR", name: "France" }]);
    mockFetchZones.mockResolvedValueOnce([
      { code: "FR", name: "France", cache_count: 12 },
    ]);
    mockFetchZones.mockResolvedValueOnce([]); // level-1 call after drilling in

    const wrapper = mount(ZonesExplorer);
    await flushPromises();

    await wrapper
      .find('[data-testid="world-found-group"] button')
      .trigger("click");
    await flushPromises();

    expect(wrapper.find('[data-testid="map-base"]').exists()).toBe(true);
    expect(mockFetchZones).toHaveBeenCalledWith(1, "FR", []);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/unit/zones-explorer.spec.ts`
Expected: FAIL - `Failed to resolve import "@/pages/caches/ZonesExplorer.vue"`

- [ ] **Step 3: Write the component (World view + drill-in shell; Country/Region rendering added in Tasks 8-9)**

```vue
<!-- frontend/src/pages/caches/ZonesExplorer.vue -->
<template>
  <div class="absolute inset-0 flex flex-col">
    <div v-if="level === 0" class="p-4 max-w-2xl mx-auto overflow-y-auto w-full">
      <h1 class="text-lg font-semibold mb-4 dark:text-gray-100">
        Zones administratives
      </h1>
      <div v-if="loading">
        <LoadingIndicator label="Chargement…" />
      </div>
      <template v-else>
        <section v-if="foundCountries.length" class="mb-4">
          <h2
            class="text-xs font-semibold text-gray-500 uppercase mb-2 dark:text-gray-400"
          >
            Pays avec trouvailles
          </h2>
          <ul data-testid="world-found-group" class="space-y-1">
            <li v-for="c in foundCountries" :key="c.code">
              <button
                type="button"
                class="w-full text-left px-3 py-2 rounded hover:bg-gray-100 dark:hover:bg-gray-800 dark:text-gray-200"
                @click="drillToCountry(c.code)"
              >
                <span>{{ c.name }}</span>
                <span class="text-gray-400 text-xs ml-2">{{
                  c.cache_count
                }}</span>
              </button>
            </li>
          </ul>
        </section>
        <section v-if="emptyCountries.length">
          <h2
            class="text-xs font-semibold text-gray-400 uppercase mb-2 dark:text-gray-500"
          >
            Autres pays
          </h2>
          <ul data-testid="world-empty-group" class="space-y-1">
            <li
              v-for="c in emptyCountries"
              :key="c.code"
              class="px-3 py-2 text-gray-400 cursor-not-allowed dark:text-gray-600"
            >
              {{ c.name }}
            </li>
          </ul>
        </section>
      </template>
    </div>

    <template v-else>
      <MapBase ref="mapRef" :zoom="6" @ready="onMapReady" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import MapBase from "@/components/map/MapBase.vue";
import LoadingIndicator from "@/components/ui/LoadingIndicator.vue";
import { useZones } from "@/composables/useZones";
import type { Country, ZoneListItem } from "@/types/zones";

// ── State ────────────────────────────────────────────────────────────────────

const mapRef = ref<InstanceType<typeof MapBase> | null>(null);
const { loading, fetchCountries, fetchZones } = useZones();

const level = ref<0 | 1 | 2>(0);
const selectedCountry = ref<string | null>(null);

const allCountries = ref<Country[]>([]);
const zonesLevel0 = ref<ZoneListItem[]>([]);

// ── World view derived lists ────────────────────────────────────────────────

const foundCountries = computed(() =>
  [...zonesLevel0.value].sort((a, b) => a.name.localeCompare(b.name)),
);

const emptyCountries = computed(() => {
  const foundCodes = new Set(zonesLevel0.value.map((z) => z.code));
  return allCountries.value
    .filter((c) => !foundCodes.has(c.code))
    .sort((a, b) => a.name.localeCompare(b.name));
});

// ── Loading ──────────────────────────────────────────────────────────────────

async function loadWorld() {
  const [countries, zones] = await Promise.all([
    fetchCountries(),
    fetchZones(0),
  ]);
  allCountries.value = countries;
  zonesLevel0.value = zones;
}

onMounted(loadWorld);

// ── Drill-down (Country/Region rendering completed in Tasks 8-9) ───────────

function drillToCountry(code: string) {
  selectedCountry.value = code;
  level.value = 1;
}

async function onMapReady() {
  // Populated in Task 8 with the level-1 choropleth render.
  await fetchZones(1, selectedCountry.value ?? undefined, []);
}
</script>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run tests/unit/zones-explorer.spec.ts`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Run the full frontend checks**

Run: `npx vue-tsc --noEmit && npx eslint . && npx vitest run`
Expected: all green

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/caches/ZonesExplorer.vue frontend/tests/unit/zones-explorer.spec.ts
git commit -m "feat(frontend): add ZonesExplorer World view

Modified files:
- frontend/src/pages/caches/ZonesExplorer.vue — new page, World (level 0) view
- frontend/tests/unit/zones-explorer.spec.ts — unit tests for the World view"
```

---

### Task 8: `ZonesExplorer.vue` - Country view (level 1 choropleth)

**Files:**
- Modify: `frontend/src/pages/caches/ZonesExplorer.vue`
- Modify: `frontend/tests/unit/zones-explorer.spec.ts`

**Interfaces:**
- Consumes: `TypeFilterDropdown.vue` (Task 6), `/geo/{country}/adm1.geojson` (static, per Task 2's rename), the same `level`/`selectedCountry`/`drillToCountry` state introduced in Task 7.
- Produces: `renderChoropleth(level: 1 | 2, country: string)` and `selectedTypes: Ref<string[]>`, both reused unchanged by Task 9 for level 2.

- [ ] **Step 1: Write the failing tests**

```typescript
// frontend/tests/unit/zones-explorer.spec.ts
// add to the leaflet mock (replace the existing trivial one):

vi.mock("leaflet", () => ({
  default: {
    geoJSON: vi.fn((geoData, options) => {
      if (Array.isArray(geoData?.features)) {
        for (const feature of geoData.features) {
          if (options?.style) options.style(feature);
          if (options?.onEachFeature) {
            const mockLayer = {
              bindTooltip: vi.fn(),
              bringToFront: vi.fn(),
              setStyle: vi.fn(),
              getBounds: vi.fn().mockReturnValue("mock-bounds"),
              on: vi.fn(),
            };
            options.onEachFeature(feature, mockLayer);
          }
        }
      }
      return { addTo: vi.fn().mockReturnThis(), resetStyle: vi.fn() };
    }),
    map: vi.fn(),
  },
}));

// add a new describe block at the end of the file:

describe("ZonesExplorer - Country view", () => {
  const geoData = {
    type: "FeatureCollection",
    features: [
      { type: "Feature", properties: { code: "84", nom: "Auvergne-Rhône-Alpes" }, geometry: null },
    ],
  };

  it("fetches the country-level geojson and level-1 zone counts when drilling in", async () => {
    mockFetchCountries.mockResolvedValueOnce([{ code: "FR", name: "France" }]);
    mockFetchZones.mockResolvedValueOnce([
      { code: "FR", name: "France", cache_count: 12 },
    ]);
    mockGet.mockResolvedValueOnce({ data: geoData });
    mockFetchZones.mockResolvedValueOnce([
      { code: "FR-84", name: "Auvergne-Rhône-Alpes", cache_count: 3 },
    ]);

    const wrapper = mount(ZonesExplorer);
    await flushPromises();
    await wrapper
      .find('[data-testid="world-found-group"] button')
      .trigger("click");
    await flushPromises();

    expect(mockGet).toHaveBeenCalledWith("/geo/FR/adm1.geojson");
    expect(mockFetchZones).toHaveBeenCalledWith(1, "FR", []);
  });

  it("shows a not-available message when the geojson 404s", async () => {
    mockFetchCountries.mockResolvedValueOnce([{ code: "FR", name: "France" }]);
    mockFetchZones.mockResolvedValueOnce([
      { code: "FR", name: "France", cache_count: 12 },
    ]);
    mockGet.mockRejectedValueOnce(new Error("404"));
    mockFetchZones.mockResolvedValueOnce([]);

    const wrapper = mount(ZonesExplorer);
    await flushPromises();
    await wrapper
      .find('[data-testid="world-found-group"] button')
      .trigger("click");
    await flushPromises();

    expect(wrapper.find('[data-testid="geo-unavailable"]').exists()).toBe(
      true,
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/unit/zones-explorer.spec.ts`
Expected: FAIL - `expected "spy" to be called with [ '/geo/FR/adm1.geojson' ]` (component doesn't fetch geojson yet)

- [ ] **Step 3: Extend the component with the choropleth renderer**

```vue
<!-- frontend/src/pages/caches/ZonesExplorer.vue -->
<!-- replace the `<template v-else>` block with: -->

    <template v-else>
      <div
        class="absolute top-3 left-1/2 -translate-x-1/2 z-20 flex items-center gap-3 bg-white rounded-lg shadow-md px-3 py-2 text-sm dark:bg-gray-900"
      >
        <button
          type="button"
          class="text-xs text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200"
          @click="goBack"
        >
          ← Retour
        </button>
        <div class="h-4 w-px bg-gray-200 dark:bg-gray-700" />
        <TypeFilterDropdown v-model="selectedTypes" :options="cacheTypes" />
      </div>

      <div
        v-if="geoUnavailable"
        data-testid="geo-unavailable"
        class="absolute inset-0 z-10 flex items-center justify-center text-gray-500 dark:text-gray-400"
      >
        Données GeoJSON pas encore disponibles pour ce pays.
      </div>

      <MapBase ref="mapRef" :zoom="6" @ready="onMapReady" />
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from "vue";
import L from "leaflet";
import type { GeoJsonObject } from "geojson";
import MapBase from "@/components/map/MapBase.vue";
import LoadingIndicator from "@/components/ui/LoadingIndicator.vue";
import TypeFilterDropdown from "@/components/zones/TypeFilterDropdown.vue";
import { useZones } from "@/composables/useZones";
import api from "@/api/http";
import type { Country, ZoneListItem } from "@/types/zones";

// ── Constants ───────────────────────────────────────────────────────────────

const COLOR_LOW = "#edf8fb";
const COLOR_HIGH = "#006d2c";
const COLOR_HOVER = "#fbbf24";
const COLOR_ZERO = "#fca5a5";

// ── State ────────────────────────────────────────────────────────────────────

const mapRef = ref<InstanceType<typeof MapBase> | null>(null);
const { loading, fetchCountries, fetchZones } = useZones();

const level = ref<0 | 1 | 2>(0);
const selectedCountry = ref<string | null>(null);
const selectedTypes = ref<string[]>([]);
const geoUnavailable = ref(false);

const allCountries = ref<Country[]>([]);
const zonesLevel0 = ref<ZoneListItem[]>([]);

interface CacheTypeOption {
  code: string;
  name: string;
}
const cacheTypes = ref<CacheTypeOption[]>([]);

let leafletMap: L.Map | null = null;
let choroplethLayer: L.GeoJSON | null = null;

// ── World view derived lists ────────────────────────────────────────────────

const foundCountries = computed(() =>
  [...zonesLevel0.value].sort((a, b) => a.name.localeCompare(b.name)),
);

const emptyCountries = computed(() => {
  const foundCodes = new Set(zonesLevel0.value.map((z) => z.code));
  return allCountries.value
    .filter((c) => !foundCodes.has(c.code))
    .sort((a, b) => a.name.localeCompare(b.name));
});

// ── World loading ────────────────────────────────────────────────────────────

async function loadWorld() {
  const [countries, zones] = await Promise.all([
    fetchCountries(),
    fetchZones(0),
  ]);
  allCountries.value = countries;
  zonesLevel0.value = zones;
}

async function loadCacheTypes() {
  try {
    const { data } = await api.get<{ code: string; name: string }[]>(
      "/cache_types",
    );
    cacheTypes.value = data.map((t) => ({ code: t.code, name: t.name }));
  } catch {
    // non-blocking
  }
}

onMounted(() => {
  loadWorld();
  loadCacheTypes();
});

// ── Choropleth helpers ───────────────────────────────────────────────────────

function interpolateColor(t: number): string {
  const low = [0xed, 0xf8, 0xfb];
  const high = [0x00, 0x6d, 0x2c];
  const r = Math.round(low[0] + t * (high[0] - low[0]));
  const g = Math.round(low[1] + t * (high[1] - low[1]));
  const b = Math.round(low[2] + t * (high[2] - low[2]));
  return `rgb(${r},${g},${b})`;
}

function buildCountMap(items: ZoneListItem[]): Map<string, number> {
  return new Map(items.map((z) => [z.code, z.cache_count]));
}

function maxCount(items: ZoneListItem[]): number {
  return items.reduce((m, z) => Math.max(m, z.cache_count), 1);
}

async function fetchGeoJson(path: string): Promise<GeoJsonObject | null> {
  try {
    const { data } = await api.get<GeoJsonObject>(path);
    return data;
  } catch {
    return null;
  }
}

function removeChoropleth() {
  if (choroplethLayer && leafletMap) {
    leafletMap.removeLayer(choroplethLayer);
    choroplethLayer = null;
  }
}

async function renderChoropleth(zoomLevel: 1 | 2, country: string) {
  if (!leafletMap) return;

  const geoPath = `/geo/${country}/adm${zoomLevel}.geojson`;
  const [geoData, zoneItems] = await Promise.all([
    fetchGeoJson(geoPath),
    fetchZones(zoomLevel, country, selectedTypes.value),
  ]);

  if (!geoData) {
    geoUnavailable.value = true;
    removeChoropleth();
    return;
  }
  geoUnavailable.value = false;

  const countMap = buildCountMap(zoneItems);
  const max = maxCount(zoneItems);

  removeChoropleth();

  choroplethLayer = L.geoJSON(geoData, {
    style(feature) {
      const featureCode = feature?.properties?.code as string | undefined;
      const zoneCode = featureCode ? `${country}-${featureCode}` : null;
      const count = zoneCode ? (countMap.get(zoneCode) ?? 0) : 0;
      const t = count > 0 ? Math.sqrt(count / max) : 0;
      return {
        fillColor: count > 0 ? interpolateColor(t) : COLOR_ZERO,
        fillOpacity: 0.75,
        color: "#6b7280",
        weight: 1,
      };
    },
    onEachFeature(feature, layer) {
      const featureCode = feature?.properties?.code as string | undefined;
      const zoneCode = featureCode ? `${country}-${featureCode}` : null;
      const zoneName = feature?.properties?.nom as string | undefined;
      const count = zoneCode ? (countMap.get(zoneCode) ?? 0) : 0;

      layer.bindTooltip(
        `<strong>${zoneName ?? zoneCode ?? "?"}</strong><br/>${count.toLocaleString("fr-FR")} cache${count > 1 ? "s" : ""}`,
        { sticky: true, opacity: 0.9 },
      );

      layer.on({
        mouseover(e) {
          const l = e.target as L.Path;
          l.setStyle({ weight: 2, color: COLOR_HOVER });
          l.bringToFront();
        },
        mouseout(e) {
          choroplethLayer?.resetStyle(e.target as L.Path);
        },
        click(e) {
          if (!zoneCode || count === 0) return;
          onZoneClick(zoneCode, zoomLevel, layer as L.Polygon, e);
        },
      });
    },
  });

  choroplethLayer.addTo(leafletMap);
}

// ── Zone click (level-1 drills to Region in Task 9, level-2 opens popup) ────

function onZoneClick(
  code: string,
  zoomLevel: 1 | 2,
  layer: L.Polygon,
  event: L.LeafletMouseEvent,
) {
  // Extended in Task 9.
  void code;
  void zoomLevel;
  void layer;
  void event;
}

// ── World -> Country drill-down ─────────────────────────────────────────────

function drillToCountry(code: string) {
  selectedCountry.value = code;
  level.value = 1;
}

function goBack() {
  if (level.value === 1) {
    level.value = 0;
    selectedCountry.value = null;
    removeChoropleth();
    leafletMap = null;
  }
  // Region -> Country handled in Task 9.
}

async function onMapReady(map: L.Map) {
  leafletMap = map;
  if (level.value === 1 && selectedCountry.value) {
    await renderChoropleth(1, selectedCountry.value);
  }
}

onUnmounted(() => {
  removeChoropleth();
  leafletMap = null;
});
</script>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run tests/unit/zones-explorer.spec.ts`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Run the full frontend checks**

Run: `npx vue-tsc --noEmit && npx eslint . && npx vitest run`
Expected: all green

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/caches/ZonesExplorer.vue frontend/tests/unit/zones-explorer.spec.ts
git commit -m "feat(frontend): add ZonesExplorer Country choropleth view

Modified files:
- frontend/src/pages/caches/ZonesExplorer.vue — Country (level 1) choropleth, type filter, back navigation
- frontend/tests/unit/zones-explorer.spec.ts — unit tests for the Country view"
```

---

### Task 9: `ZonesExplorer.vue` - Region view (zoom drill-down) + shared zone-detail popup

**Files:**
- Modify: `frontend/src/pages/caches/ZonesExplorer.vue`
- Modify: `frontend/tests/unit/zones-explorer.spec.ts`

**Interfaces:**
- Consumes: `fetchZoneDetail(code, level)` (unchanged since Step 3/4, no type filter parameter), `renderChoropleth`/`onZoneClick`/`goBack` from Task 8.
- Produces: final, complete `ZonesExplorer.vue` behavior for all three levels.

- [ ] **Step 1: Write the failing tests**

```typescript
// frontend/tests/unit/zones-explorer.spec.ts
// add a new describe block at the end of the file:

describe("ZonesExplorer - Region view and popup", () => {
  const regionGeoData = {
    type: "FeatureCollection",
    features: [
      { type: "Feature", properties: { code: "84", nom: "Auvergne-Rhône-Alpes" }, geometry: null },
    ],
  };
  const departementGeoData = {
    type: "FeatureCollection",
    features: [
      { type: "Feature", properties: { code: "38", nom: "Isère" }, geometry: null },
    ],
  };

  async function drillToRegion(wrapper: ReturnType<typeof mount>) {
    await wrapper
      .find('[data-testid="world-found-group"] button')
      .trigger("click");
    await flushPromises();
  }

  it("zooms to the clicked region's bounds instead of calling a new geojson endpoint", async () => {
    mockFetchCountries.mockResolvedValueOnce([{ code: "FR", name: "France" }]);
    mockFetchZones.mockResolvedValueOnce([
      { code: "FR", name: "France", cache_count: 12 },
    ]);
    mockGet.mockResolvedValueOnce({ data: regionGeoData });
    mockFetchZones.mockResolvedValueOnce([
      { code: "FR-84", name: "Auvergne-Rhône-Alpes", cache_count: 3 },
    ]);
    mockGet.mockResolvedValueOnce({ data: departementGeoData });
    mockFetchZones.mockResolvedValueOnce([
      { code: "FR-38", name: "Isère", cache_count: 3 },
    ]);

    const wrapper = mount(ZonesExplorer);
    await flushPromises();
    await drillToRegion(wrapper);

    expect(mockGet).toHaveBeenCalledWith("/geo/FR/adm1.geojson");
    const callsToLevel1 = mockGet.mock.calls.filter(
      (c) => c[0] === "/geo/FR/adm1.geojson",
    );
    expect(callsToLevel1).toHaveLength(1);
  });

  it("opens the zone-detail popup with the full type breakdown, ignoring the active type filter", async () => {
    mockFetchCountries.mockResolvedValueOnce([{ code: "FR", name: "France" }]);
    mockFetchZones.mockResolvedValueOnce([
      { code: "FR", name: "France", cache_count: 12 },
    ]);
    mockGet.mockResolvedValueOnce({ data: regionGeoData });
    mockFetchZones.mockResolvedValueOnce([
      { code: "FR-84", name: "Auvergne-Rhône-Alpes", cache_count: 3 },
    ]);
    mockFetchZoneDetail.mockResolvedValueOnce({
      code: "FR-84",
      name: "Auvergne-Rhône-Alpes",
      cache_count: 3,
      type_counts: [
        { type_code: "traditional", type_name: "Traditional", count: 3 },
      ],
    });

    const wrapper = mount(ZonesExplorer);
    await flushPromises();
    await drillToRegion(wrapper);

    expect(mockFetchZoneDetail).toHaveBeenCalledWith("FR-84", 1);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run tests/unit/zones-explorer.spec.ts`
Expected: FAIL - `mockFetchZoneDetail` not called (popup not wired yet), region zoom not implemented

- [ ] **Step 3: Complete the component**

```vue
<!-- frontend/src/pages/caches/ZonesExplorer.vue -->
<!-- add the popup markup right before the final closing </div> of the root, after <MapBase ... /> -->

      <div
        v-if="popoverVisible && popoverDetail"
        class="absolute z-30 bg-white rounded-lg shadow-xl border border-gray-200 w-72 text-sm dark:bg-gray-900 dark:border-gray-700"
        :style="{ top: popoverPos.y + 'px', left: popoverPos.x + 'px' }"
      >
        <div class="flex items-start justify-between p-3 pb-1">
          <div class="font-semibold text-gray-900 dark:text-gray-100">
            {{ popoverDetail.name }}
          </div>
          <button
            type="button"
            class="text-gray-400 hover:text-gray-600 ml-2 shrink-0 dark:text-gray-500 dark:hover:text-gray-300"
            @click="closePopover"
          >
            ✕
          </button>
        </div>
        <div class="px-3 pb-1 text-gray-500 text-xs dark:text-gray-400">
          {{ popoverDetail.cache_count.toLocaleString("fr-FR") }} cache{{
            popoverDetail.cache_count > 1 ? "s" : ""
          }}
        </div>
        <hr class="my-1 border-gray-100 dark:border-gray-800" />
        <ul class="px-3 pb-2 space-y-1">
          <li
            v-for="t in popoverDetail.type_counts"
            :key="t.type_code"
            class="flex items-center justify-between text-gray-700 dark:text-gray-300"
          >
            <span>{{ t.type_name }}</span>
            <span class="text-gray-400">{{ t.count }}</span>
          </li>
        </ul>
      </div>
```

```typescript
// frontend/src/pages/caches/ZonesExplorer.vue <script setup>
// update the type import:
import type { Country, ZoneDetail, ZoneListItem } from "@/types/zones";

// destructure fetchZoneDetail too:
const { loading, fetchCountries, fetchZones, fetchZoneDetail } = useZones();

// add new state, near the other refs:
const selectedRegion = ref<string | null>(null);
const popoverVisible = ref(false);
const popoverDetail = ref<ZoneDetail | null>(null);
const popoverPos = ref({ x: 16, y: 60 });

// replace the onZoneClick stub with:
async function onZoneClick(
  code: string,
  zoomLevel: 1 | 2,
  layer: L.Polygon,
  event: L.LeafletMouseEvent,
) {
  if (zoomLevel === 1) {
    selectedRegion.value = code;
    level.value = 2;
    if (leafletMap) leafletMap.fitBounds(layer.getBounds());
    await renderChoropleth(2, selectedCountry.value!);
    return;
  }
  await openPopover(code, event, zoomLevel);
}

async function openPopover(
  code: string,
  event: L.LeafletMouseEvent,
  zoomLevel: 1 | 2,
) {
  popoverVisible.value = false;

  const containerPoint = leafletMap?.latLngToContainerPoint(event.latlng);
  if (containerPoint) {
    popoverPos.value = {
      x: Math.min(containerPoint.x + 12, window.innerWidth - 300),
      y: Math.min(
        Math.max(containerPoint.y - 20, 60),
        window.innerHeight - 420,
      ),
    };
  }

  const detail = await fetchZoneDetail(code, zoomLevel);
  if (detail) {
    popoverDetail.value = detail;
    popoverVisible.value = true;
  }
}

function closePopover() {
  popoverVisible.value = false;
  popoverDetail.value = null;
}

// update goBack to handle Region -> Country:
function goBack() {
  closePopover();
  if (level.value === 2) {
    level.value = 1;
    selectedRegion.value = null;
    if (selectedCountry.value) renderChoropleth(1, selectedCountry.value);
    return;
  }
  if (level.value === 1) {
    level.value = 0;
    selectedCountry.value = null;
    removeChoropleth();
    leafletMap = null;
  }
}
```

Also wire the type filter to reload the current level's choropleth on change, by adding a `watch`:

```typescript
import { ref, computed, onMounted, onUnmounted, watch } from "vue";

watch(selectedTypes, async () => {
  if (level.value === 1 && selectedCountry.value) {
    await renderChoropleth(1, selectedCountry.value);
  } else if (level.value === 2 && selectedCountry.value) {
    await renderChoropleth(2, selectedCountry.value);
  }
});
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run tests/unit/zones-explorer.spec.ts`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Run the full frontend checks**

Run: `npx vue-tsc --noEmit && npx eslint . && npx vitest run`
Expected: all green

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/caches/ZonesExplorer.vue frontend/tests/unit/zones-explorer.spec.ts
git commit -m "feat(frontend): add ZonesExplorer Region view and zone-detail popup

Modified files:
- frontend/src/pages/caches/ZonesExplorer.vue — Region (level 2) zoom drill-down, shared popup, type-filter reload
- frontend/tests/unit/zones-explorer.spec.ts — unit tests for Region view and popup"
```

---

### Task 10: Router + nav wiring, final verification

**Files:**
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/app/AppShell.vue`

**Interfaces:**
- Consumes: `ZonesExplorer.vue` (Task 9's final state).
- Produces: route `caches/zones-explorer` at `/caches/zones-explorer`, reachable from the "Caches" nav section.

- [ ] **Step 1: Add the route**

```typescript
// frontend/src/router/index.ts
// inside cachesRoutes, after the /caches/map-demo entry:

  {
    path: "/caches/zones-explorer",
    name: "caches/zones-explorer",
    component: () => import("@/pages/caches/ZonesExplorer.vue"),
    meta: { dense: true, noFabPadding: true, title: "Zones administratives" },
  },
```

- [ ] **Step 2: Add the nav entry**

```vue
<!-- frontend/src/app/AppShell.vue -->
<!-- inside the "Caches" <ul v-show="openSections.caches">, after the /caches/within-radius <li>, before the closing </ul> -->

                <li>
                  <RouterLink
                    class="flex items-center gap-2 px-3 py-3 rounded hover:bg-gray-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-gray-300 dark:hover:bg-gray-800 dark:focus-visible:outline-gray-600"
                    to="/caches/zones-explorer"
                  >
                    <GlobeEuropeAfricaIcon
                      class="w-5 h-5 shrink-0 text-gray-700 dark:text-gray-300"
                      aria-hidden="true"
                    />
                    <span>Zones administratives</span>
                  </RouterLink>
                </li>
```

```typescript
// frontend/src/app/AppShell.vue <script setup>
// re-add GlobeEuropeAfricaIcon to the heroicons import block:
import {
  Bars3Icon,
  XMarkIcon,
  UserCircleIcon,
  ArrowLeftOnRectangleIcon,
  MapPinIcon,
  DocumentArrowUpIcon,
  AdjustmentsHorizontalIcon,
  RectangleGroupIcon,
  RssIcon,
  QuestionMarkCircleIcon,
  DocumentTextIcon,
  ChartBarIcon,
  GlobeEuropeAfricaIcon,
} from "@heroicons/vue/24/outline";
```

- [ ] **Step 3: Run the full frontend checks**

Run: `npx vue-tsc --noEmit && npx eslint . && npx prettier --check . && npx vitest run`
Expected: all green

- [ ] **Step 4: Manual smoke test**

Start the dev server, log in, open the "Caches" nav section, click "Zones administratives", confirm: World list renders with France (or whichever countries have found caches) in the "avec trouvailles" group; clicking France renders the region choropleth; clicking a region zooms in and renders the department choropleth; clicking a department opens the popup with the full type breakdown; the type-filter dropdown recolors the map; "Retour" navigates back up one level at a time.

- [ ] **Step 5: Run the full backend + frontend suites one more time**

Run (from `backend/`): `.venv/bin/pytest tests/unit/ --cov=app --cov-report=term-missing -q`
Run (from `frontend/`): `npx vitest run`
Expected: all green, patch/project coverage within `codecov.yml`'s 95%/90% thresholds for everything touched in this plan.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/router/index.ts frontend/src/app/AppShell.vue
git commit -m "feat(frontend): wire ZonesExplorer into the router and nav

Modified files:
- frontend/src/router/index.ts — add /caches/zones-explorer route
- frontend/src/app/AppShell.vue — add nav entry, restore GlobeEuropeAfricaIcon import"
```

---

## Self-Review

**Spec coverage:**
- `GET /countries` referential endpoint: Task 1.
- FR `regions.geojson`/`departements.geojson` -> `adm1.geojson`/`adm2.geojson` rename, including the config, migration script, fixtures, docs, and the gitignored-file/VPS caveat: Task 2.
- `/zones` contract untouched, `GET /zones/{code}` never gains a type filter: enforced as a Global Constraint, verified by Task 9's "ignoring the active type filter" test.
- `GET /admin/geo/missing-countries` (found_caches-weighted, not raw cache count, excludes countries with an existing directory): Task 3.
- `POST /admin/geo/{country_code}/upload` (normalized contract validation, disk write, `administrative_zones` upsert, ADM0 stored but not seeded): Task 4.
- World view with two groups (has finds / no finds), only "has finds" clickable: Task 7.
- Country view: generalized choropleth (no hardcoded "FR"), zero-count zones non-clickable: Task 8 (`onZoneClick` early-returns when `count === 0`).
- Region view via client-side zoom (no new spatially-filtered endpoint), reusing the country-wide level-2 GeoJSON: Task 9.
- Merged zone-detail popup, always full `type_counts`, checkboxes-in-dropdown multi-select type filter: Tasks 6 and 9.
- Graceful "not available yet" state on GeoJSON 404: Task 8 (`geoUnavailable`).
- No dedicated admin frontend UI for the two admin endpoints: honored (Tasks 3/4 have no frontend counterpart; Task 10 only wires the explorer page).
- Router + nav wiring: Task 10.

**Placeholder scan:** no "TBD"/"similar to Task N" remain; every step carries either real, runnable code or a fully-specified shell command. The doc-file substitutions in Task 2 Step 8 are a mechanical, unambiguous find-replace across exactly-grepped lines (not a hand-wave), with one worked example given verbatim.

**Type/signature consistency:**
- `fetchCountries(): Promise<Country[]>` (Task 5) matches its use in Task 7/8's `loadWorld()`.
- `renderChoropleth(zoomLevel: 1 | 2, country: string)` introduced in Task 8 is called identically in Task 9 (`renderChoropleth(1, ...)` / `renderChoropleth(2, ...)`) and in the `selectedTypes` watcher.
- `onZoneClick(code, zoomLevel, layer, event)` signature declared as a stub in Task 8 is reused with the exact same parameter list when implemented in Task 9.
- Backend `upload_zone_level(country_code: str, level: int, content: bytes) -> dict` (Task 4) matches the route's call site and the DTO field names (`country_code`, `level`, `features_count`, `inserted`, `updated`) match `GeoUploadResponse`.
- `get_missing_countries() -> list[dict]` (Task 3) return shape (`{"code", "found_count"}`) matches `MissingCountryItem`'s fields.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-11-zones-explorer-step5.md`. Two execution options:

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
