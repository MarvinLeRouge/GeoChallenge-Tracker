[🇫🇷 Version française](roadmap.fr.md) | 🇬🇧 English version

---

# Product Roadmap: GeoChallenge Tracker

**Created:** 2026-03-20
**Last updated:** 2026-09-02 (factual verification against the code: SMTP health check, marker clustering, full-text search)
**Type:** Functional roadmap, what remains to be built
**Sources:** README, existing code

> This document lists missing, incomplete, or planned features.
> It does not cover bug fixes or technical debt, see [`roadmap-corrections.md`](roadmap-corrections.md).

---

## Table of contents

- [Legend](#legend)
- [Current project state](#current-project-state)
- [Epic 1: Authentication & user accounts](#epic-1-authentication--user-accounts)
- [Epic 2: Cache import & management](#epic-2-cache-import--management)
- [Epic 3: Challenges & progress](#epic-3-challenges--progress)
- [Epic 4: Visualization & map](#epic-4-visualization--map)
- [Epic 5: Notifications & communication](#epic-5-notifications--communication)
- [Epic 6: Statistics & exports](#epic-6-statistics--exports)
- [Epic 7: Quality, tests & observability](#epic-7-quality-tests--observability)
- [Epic 8: Infrastructure & deployment](#epic-8-infrastructure--deployment)
- [Priority synthesis](#priority-synthesis)

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Implemented and functional |
| 🔧 | Partially implemented / to complete |
| ❌ | Not implemented |
| 🔴 | Critical priority |
| 🟠 | High priority |
| 🟡 | Normal priority |
| 🟢 | Nice-to-have |

**Complexity:** `S` (< 1 day) · `M` (1-3 days) · `L` (3-7 days) · `XL` (> 1 week)

---

## Current project state

### What works today

| Domain | Feature | State |
|--------|---------|-------|
| Auth | Register, Login, Refresh token | ✅ |
| Auth | Email verification by code | ✅ |
| Auth | Resend verification code | ✅ |
| Caches | Synchronous GPX / ZIP import | ✅ |
| Caches | Search by bbox, radius, advanced filters | ✅ |
| Caches | Retrieval by GC code or MongoDB ID | ✅ |
| Challenges | Create challenges from caches | ✅ |
| My challenges | Paginated listing, detail, single patch | ✅ |
| My challenges | Calendar challenge (365-day check) | ✅ |
| My challenges | D/T matrix (9x9 check) | ✅ |
| Targets | Evaluation, listing, nearby search, deletion (API) | ✅ |
| Targets | Global `/my/targets` page (frontend) | ✅ |
| Progress | Evaluation, history, first snapshot | ✅ |
| Tasks | Listing, replacement, validation without persistence | ✅ |
| Profile | Read/write profile + location | ✅ |
| Stats | Basic user statistics | ✅ |
| Maintenance | Orphan analysis, DB backup / restore | ✅ |
| Meta | `/health`, `/version`, `/info` (with real SMTP check) | ✅ |
| Map | Cache visualization (MapDemo) | ✅ |
| Map | Marker clustering (WithinBbox, WithinRadius, Targets) | ✅ |
| Caches | Full-text search (`$text` via `POST /caches/by-filter`) | ✅ |

### What is started but incomplete

| Domain | Feature | State | Reference |
|--------|---------|-------|-----------|
| My challenges | Sync UserChallenges | 🔧 BACKLOG | `my_challenges.py:46` |
| My challenges | Batch PATCH challenges | 🔧 BACKLOG | `my_challenges.py:109` |
| Auth | Reset password | ❌ Route missing | - |
| Cache search | Search by filter (frontend) | ❌ `_NotImplemented` | `router/index.ts` |
| Progress | Progress page (frontend) | ❌ `_NotImplemented` | `router/index.ts` |
| Targets | Per-challenge targets page (frontend) | ❌ `_NotImplemented` | `router/index.ts` |

---

## Epic 1: Authentication & user accounts

### 1.1 Password reset ❌ 🔴 `M`

**Context:** Email verification is in place, but no password reset route exists. A user who forgets their password cannot recover their account.

**To build:**

| Step | Backend | Frontend |
|------|---------|----------|
| Reset request | `POST /auth/forgot-password`: generates a token, sends an email | Form with an email field |
| Confirmation | `POST /auth/reset-password`: verifies the token, hashes the new password | Form with token + new password |
| Invalidation | The token is single-use, TTL 1h | - |

**Dependencies:** working email service (`aiosmtplib` already in place), `users.reset_token` + `users.reset_token_expires_at` to add to the `User` model.

---

### 1.2 Complete UserChallenges synchronization 🔧 🟠 `M`

**Context:** The `POST /my/challenges/sync` route is marked `TODO: [BACKLOG]` in the code. Synchronization creates missing `UserChallenge` entries for a user, but its exact behavior (full sync vs. delta) is not finalized.

**To validate / build:**
- Define the sync logic: full (recreates everything) or delta (adds only missing entries)
- Finalize the route and mark it `DONE`
- Add integration tests covering the "first sync" and "incremental sync" cases

---

### 1.3 Batch PATCH challenges 🔧 🟡 `S`

**Context:** `PATCH /my/challenges` (bulk update) is declared but not verified. Used by the frontend to change the status of several challenges at once.

**To validate:** behavior with nonexistent IDs, returned result (list of updated vs. errors), tests.

---

### 1.4 Logout with server-side invalidation ✅ 🟡 `M`

**Done (2026-08-01):** `POST /auth/logout` revokes the refresh token via its `jti` (MongoDB collection `revoked_refresh_tokens`, TTL index for automatic cleanup). `/auth/refresh` rejects revoked tokens. The frontend calls the route before clearing storage, on a best-effort basis. `refresh_token` cookie widened from `path=/auth/refresh` to `path=/auth` to reach the new endpoint.

---

## Epic 2: Cache import & management

### 2.1 Asynchronous GPX import (background task) ❌ 🔴 `XL`

**Context:** GPX/ZIP import is currently synchronous. For a Pocket Query file (typically 500-1000 caches), the request can exceed 30 seconds and time out. Celery files are already present in the project (`DETAIL_celery_gpx.md`), the architecture decision has been made.

**To build:**

| Component | Description |
|-----------|-------------|
| Celery worker | Separate Docker service, consumes a Redis queue |
| `import_gpx` task | Moves the current import logic into a Celery task |
| Upload route | `POST /caches/upload-gpx` returns a `job_id` immediately (HTTP 202) |
| Status route | `GET /caches/import-jobs/{job_id}` returns `pending / processing / done / failed` + stats |
| Frontend | Progress tracking component (polling or SSE) on the `ImportGpx.vue` page |

**Dependencies:** Redis (new Docker service), Celery (`celery[redis]` to add to dependencies).

---

### 2.2 GPX validation before full processing ❌ 🟠 `S`

**Context:** The GPX parser currently reads the entire file into memory before detecting a possible invalid format. On a corrupted 50 MB file, this needlessly consumes RAM.

**To build:**
- Read only the first 4 KB of the file to validate the XML header / `<gpx>` tag
- Return HTTP 400 immediately if invalid, without full processing
- Test with invalid files (JSON, binary, truncated GPX)

---

### 2.3 "Search by filter" page (frontend) ❌ 🟠 `L`

**Context:** The frontend route `/caches/by-filter` points to `_NotImplemented.vue`. The API route `POST /caches/by-filter` is functional.

**To build:**
- Filter form (type, size, difficulty, terrain, attributes, placement/found dates)
- Paginated results table
- Link to a cache's detail page
- Dedicated `useCacheFilter` composable

---

### 2.4 Streaming support for large GPX files 🟡 `M`

**Context:** Even with asynchronous processing (2.1), handling a GPX file with several thousand caches as a single list can saturate RAM. Chunked processing avoids this problem.

**To build:** iterative parser (SAX/iterparse) instead of loading everything into memory in the GPX import service.

---

## Epic 3: Challenges & progress

### 3.1 "Progress" page (frontend) ❌ 🔴 `L`

**Context:** The `/my/challenges/:id/progress` route points to `_NotImplemented.vue`. The progress API routes (`GET`, `POST /evaluate`, `POST /new/progress`) are functional.

**To build:**
- Chart of completion rate over time (% over time)
- Latest snapshot with detail (how many cells filled, how many missing)
- "Evaluate now" button -> calls `POST /evaluate`
- Dedicated `useProgress` composable

---

### 3.2 "Targets" page (frontend) 🔧 🔴 `L`

**Global view (done):** `/my/targets` (`Targets.vue`) is fully functional: Leaflet map, "nearby" mode with center selection, "Search nearby" button, target evaluation and display.

**Per-challenge view (remaining):** `/my/challenges/:id/targets` still points to `_NotImplemented.vue`. The targets API routes are complete (`GET /targets/nearby`, `DELETE /my/challenges/{uc_id}/targets`, etc.).

**To build (per-challenge view):**
- Paginated list of target caches for this specific challenge (sortable by score, distance, difficulty...)
- Reuse the existing map component from `Targets.vue`
- "Delete targets" button -> calls `DELETE /my/challenges/{uc_id}/targets`

---

### 3.3 Automatic progress evaluation 🟡 `M`

**Context:** Progress evaluation is currently triggered manually. In a natural flow, it should be recalculated automatically after each GPX import.

**To build:** trigger `POST /my/challenges/{uc_id}/progress/evaluate` (or a batch version) automatically at the end of a successful GPX import, for all of the user's active challenges.

---

### 3.4 Achievable challenge suggestions 🟢 `L`

**Context:** Feature described in the README ("Get completion projections") but absent from the code.

**To build:**
- Endpoint `GET /my/challenges/suggestions`: analyzes found and not-found caches, computes the potential completion % for each not-yet-active challenge
- Suggestion criterion: challenges achievable at >= 70% with the user's current caches
- Frontend display as "Recommended challenges" cards

---

## Epic 4: Visualization & map

### 4.1 Marker clustering on the map 🔧 🟡 `M`

**Done:** `Leaflet.markercluster` is integrated client-side in `WithinBbox.vue`, `WithinRadius.vue`, and `Targets.vue` (`L.markerClusterGroup`), with progressive ungrouping on zoom.

**Remaining:**
- Integrate clustering into `MapDemo.vue`, which still displays every cache as an individual marker
- Adapt the API: add an optional `cluster=true` parameter to `GET /caches/within-bbox` to return server-side cluster centroids (MongoDB `$geoNear` + `$group`), useful for very large volumes where client-side clustering alone is no longer enough

---

### 4.2 Finds heatmap 🟢 `M`

**Context:** Feature mentioned in the README ("Visualize progress on maps").

**To build:**
- Integrate `Leaflet.heat` in the frontend
- Endpoint `GET /my/found-caches/heatmap` -> returns a list of `[lat, lng, intensity]`
- Intensity = number of caches found in an area (MongoDB aggregation)
- Dedicated page or tab in the stats view

---

### 4.3 Map of a challenge's targets 🟡 `S`

**Context:** The Targets page (3.2) will list targets in a table, but a complementary map view would be useful for planning a geographic route.

**To build:** "Map" tab on the Targets page, reusing the existing map component with targets as the data source.

---

## Epic 5: Notifications & communication

### 5.1 Password reset email ❌ 🔴 `S`

Depends on [1.1](#11-password-reset--🔴-m). Email template to create in the existing email service.

---

### 5.2 "Challenge completed" notification email ❌ 🟠 `S`

**Context:** Not implemented. When a progress evaluation reaches 100%, no email is sent.

**To build:**
- Detect reaching 100% in `POST /my/challenges/{uc_id}/progress/evaluate`
- Send a congratulations email via `aiosmtplib`
- HTML notification template (use the existing email template system)

---

### 5.3 In-app notification system ❌ 🟢 `L`

**Context:** Planned feature, not started.

**To build:**
- `notifications` MongoDB collection (`user_id`, `type`, `payload`, `read_at`, `created_at`)
- `GET /my/notifications` (paginated, with `unread_only` filter)
- `PATCH /my/notifications/{id}/read`
- Bell icon in the frontend header with a counter badge
- Optional: WebSocket for real-time notifications

---

### 5.4 Email health check (real SMTP) ✅ 🟡 `S`

**Done (2026-03-21):** `check_email()` in `core/meta.py` opens a real SMTP connection (with STARTTLS if the port is 587) and sends a `NOOP` to verify the server responds, without sending an email. Returns `"ok"` or the error message.

---

## Epic 6: Statistics & exports

### 6.1 GPX export of a challenge ❌ 🟠 `M`

**Context:** A geocacher wants to load a challenge's targets into their GPS application. Feature mentioned in `TODO_GC_TRACKER.md`.

**To build:**
- Route `GET /my/challenges/{uc_id}/export-gpx`
- Generate a valid GPX file containing the challenge's target caches
- Use `gpxpy` for generation (standard library for this domain)
- Frontend: "Export GPX" button on the Targets page / challenge detail

---

### 6.2 Advanced user statistics 🔧 🟡 `L`

**Context:** The `/user-stats` route exists and returns basic statistics. The README mentions completion projections, evolution charts, and heatmaps.

**To complete:**

| Metric | State | Notes |
|--------|-------|-------|
| Total caches found | ✅ | |
| Breakdown by type/size | ✅ probable | To verify |
| Evolution over time (chart) | ❌ | Aggregation by month/week |
| D/T matrix completion % | ✅ via matrix challenge | |
| Projection "how many caches from the next milestone" | ❌ | Backend calculation |
| Countries/regions visited | ❌ | Aggregation on `caches.country` |

**Frontend:** `MyStats.vue` page exists, to be enriched with charts (Chart.js or D3).

---

### 6.3 Full-text search on caches 🔧 🟡 `S`

**Done:** the text index declared in `seed_indexes.py` (`title` + `description`) is used via the `q` parameter of `POST /caches/by-filter`, which uses the MongoDB `$text` operator.

**Remaining:**
- Relevance scoring with `$meta: "textScore"` (the current sort does not prioritize the most relevant results)
- Frontend: text search field in the filter form (2.3)

---

## Epic 7: Quality, tests & observability

### 7.1 Backend API tests ✅ 🔴 `L`

**Done (2026-08-03):** routes are tested via the API, with integration tests (`backend/tests/integration/`, e.g. `test_authenticated.py`) and unit tests that spin up the real FastAPI routes with mocked dependencies (`backend/tests/unit/test_maintenance_*.py`, etc.), `pytest` + `httpx.AsyncClient` stack. 1291 backend tests in total (`pytest tests/unit -q`).

---

### 7.2 Coverage >= 60% ✅ `M`

**Done and largely exceeded (2026-08-03):** Codecov integrated into CI (backend + frontend, `codecov.yml`), with real blocking thresholds (`project target: 90%`, `patch target: 95%`, `informational: false`), well beyond the initial 60% goal. Badge in the README.

---

### 7.3 Challenge integration tests 🟡 `M`

Cover full flows:
- Sync -> evaluation -> progress
- Target evaluation -> listing -> GPX export
- Calendar / Matrix: "completed" and "not completed" cases

---

### 7.4 Structured logging ❌ 🔴 `M`

**Context:** Current logging uses `print()` in several files. There are no correlation IDs, no JSON format, no HTTP request logging middleware.

**To build:**
- Replace all `print()` calls with `logging.getLogger(__name__)` or adopt `structlog`
- FastAPI middleware that logs each request with: method, path, status code, duration, user_id
- JSON format in production, readable format in development
- Correlation ID (`X-Request-ID`) propagated through all logs of a request

---

### 7.5 Rate limiting on sensitive routes ✅ 🟠 `S`

**Done (2026-08-01):** `slowapi` integrated. `POST /auth/login` (10/min), `POST /auth/register` (5/min), `POST /auth/resend-verification` (3/min). HTTP 429 with a `Retry-After` header.

---

### 7.6 Prometheus metrics ❌ 🟢 `S`

**Context:** No instrumentation metrics are exposed.

**To build:**
- Integrate `prometheus_fastapi_instrumentator`
- Expose `/metrics` (Prometheus endpoint)
- Metrics: response time per route, error rate, request count

---

### 7.7 Frontend tests (Vitest + Playwright) 🔧 🟠 `L`

**Vitest (done, 2026-08-03):** 419 unit/component tests (`npx vitest run frontend/tests/unit`, composables like `useCalendarData`/`useMatrixData`, components like the `Calendar.vue`/`Matrix.vue`/`List.vue` pages), running in CI with coverage upload to Codecov.

**Playwright (started, not yet automated):** two e2e specs exist (`frontend/tests/e2e/login-map-center.spec.ts`, `smoke.spec.ts`) but do not run in CI (no Playwright step in `.github/workflows/ci.yml`).

**Remaining:**
- Integrate Playwright execution into GitHub Actions CI
- Expand the e2e specs (login -> GPX import -> challenge display flow)

---

## Epic 8: Infrastructure & deployment

### 8.1 Dev / prod config separation ❌ 🔴 `M`

**Context:** A single `.env` file is used for both environments. Debug settings, CORS, and log level must differ between dev and prod.

**To build:**
- `.env.dev`: debug enabled, permissive CORS (`*`), verbose logs, MailDev
- `.env.prod`: debug disabled, restrictive CORS (specific domain), JSON logs, real SMTP
- `docker-compose.override.yml` for development overrides
- Documentation in `.env.example` for each variable

---

### 8.2 Docker Compose healthchecks 🔧 `M`

**Prod (done):** `docker-compose.prod.yml` has a healthcheck on `backend` (`curl -f http://localhost:8000/health`) and on `tiles`.

**Dev (partial):** `docker-compose.yml` has a healthcheck on `tiles` only; `backend` does not have one yet in dev.

**To build (dev):**
```yaml
# docker-compose.yml
backend:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 10s
```
MongoDB being external (Atlas) in both environments, no local `mongo` service to add: the backend `/health` already checks the Atlas connection (see Epic 5.4).

---

### 8.3 CI/CD: automated tests before merge ✅ 🟠 `M`

**Done (2026-08-03):** CI (`.github/workflows/ci.yml`) runs `pytest tests/unit/ --cov=app` (backend) and `npm run test:unit` (frontend), both with coverage upload to Codecov, whose thresholds (`project: 90%`, `patch: 95%`) are blocking (`informational: false`).

---

### 8.4 HTTPS in production 🔴 `M`

**Context:** The Nginx configuration exists in `ops/nginx/` but the HTTP -> HTTPS redirect and SSL certificates are not documented / verified.

**To build / verify:**
- Nginx configuration with `return 301 https://$host$request_uri;` on port 80
- Let's Encrypt (Certbot) integration or manual certificate
- HSTS header
- Document the certificate renewal process

---

### 8.5 HTTP security headers ✅ 🟡 `S`

**Done (2026-08-01):** `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`, `Referrer-Policy`, `Strict-Transport-Security`, `Permissions-Policy` headers added via a shared Nginx snippet (`include`d in each `location`, to work around the fact that a `location` block with its own `add_header` does not inherit those of the parent `server`). Verified under real conditions (headers observed on responses).

---

### 8.6 Automate `build_date` via GitHub Actions 🟡 `S`

**Context:** The README documents a `TODO (Phase 4)`: automate the `BUILD_DATE` update in CI on a production deployment.

**To build:**
- Step in `build-push.yml` that injects `BUILD_DATE=$(git log -1 --format=%cI)` as a Docker `build-arg`
- Remove the manual `build.sh` script, or keep it for local dev only

---

### 8.7 Centralized production logs ❌ 🟢 `L`

**To build:**
- Configure the Docker log driver to send to Loki or a centralized file
- Loki + Grafana stack (lightweight, self-hostable) or a cloud equivalent
- Dashboards: error rate, response time, ongoing GPX imports

---

## Priority synthesis

### 🔴 Critical, to address first

| # | Feature | Epic | Size |
|---|---------|------|------|
| 1 | Password reset | 1.1 | M |
| 2 | Asynchronous GPX import | 2.1 | XL |
| 3 | Progress page (frontend) | 3.1 | L |
| 4 | Targets page (frontend) (🔧 global view done, per-challenge view remaining) | 3.2 | L |
| 5 | ~~Backend API tests~~ ✅ done | 7.1 | L |
| 6 | Structured logging | 7.4 | M |
| 7 | Dev/prod config separation | 8.1 | M |
| 8 | HTTPS in production | 8.4 | M |

### 🟠 High, next sprint

| # | Feature | Epic | Size |
|---|---------|------|------|
| 9 | GPX validation before processing | 2.2 | S |
| 10 | Search by filter page (frontend) | 2.3 | L |
| 11 | Challenge completed notification email | 5.2 | S |
| 12 | GPX export of a challenge | 6.1 | M |
| 13 | ~~Coverage >= 60%~~ ✅ done (90%/95% in CI) | 7.2 | M |
| 14 | ~~Auth rate limiting~~ ✅ done | 7.5 | S |
| 15 | Frontend tests (Vitest + Playwright) (🔧 Vitest done, Playwright not in CI) | 7.7 | L |
| 16 | Docker Compose healthchecks (🔧 prod done, dev partial) | 8.2 | M |
| 17 | ~~CI/CD: tests before merge~~ ✅ done | 8.3 | M |

### 🟡 Normal, mid-term backlog

| # | Feature | Epic | Size |
|---|---------|------|------|
| 18 | Sync UserChallenges (finalize) | 1.2 | M |
| 19 | Batch PATCH challenges (validate) | 1.3 | S |
| 20 | GPX streaming support | 2.4 | M |
| 21 | Auto evaluation after import | 3.3 | M |
| 22 | Map clustering (🔧 client done, MapDemo + server clustering remaining) | 4.1 | M |
| 23 | Targets map | 4.3 | S |
| 24 | ~~Real SMTP health check~~ ✅ done | 5.4 | S |
| 25 | Advanced statistics | 6.2 | L |
| 26 | Full-text cache search (🔧 search functional, relevance scoring remaining) | 6.3 | S |
| 27 | Challenge integration tests | 7.3 | M |
| 28 | ~~HTTP security headers~~ ✅ done | 8.5 | S |
| 29 | Automate build_date in CI | 8.6 | S |

### 🟢 Nice-to-have, long-term

| # | Feature | Epic | Size |
|---|---------|------|------|
| 30 | ~~Logout with server-side invalidation~~ ✅ done | 1.4 | M |
| 31 | Challenge suggestions | 3.4 | L |
| 32 | Finds heatmap | 4.2 | M |
| 33 | In-app notifications | 5.3 | L |
| 34 | Prometheus metrics | 7.6 | S |
| 35 | Centralized production logs | 8.7 | L |
