[🇫🇷 Version française](api_endpoints.fr.md) | 🇬🇧 English version

---

# API Documentation - GeoChallenge Tracker

> Public routes (authenticated or not). Admin-only routes (`/maintenance/*`, `/caches_elevation/*`, `/caches_geocoding/*`) are not documented here.

## Authentication (`/auth`)

### Register
- **URL**: `POST /auth/register`
- **Description**: Creates a new (unverified) user account, sends a verification email (code valid 24h)
- **Body**:
  ```json
  {
    "username": "string",
    "email": "string",
    "password": "string"
  }
  ```
- **Response** (201): public info of the created account (`_id`, `username`, `email`, `role`)

### Login
- **URL**: `POST /auth/login`
- **Description**: Authenticates a user (accepts JSON `{identifier, password}` or an OAuth2 form). The account must be verified.
- **Body**:
  ```json
  {
    "identifier": "string", // email or username
    "password": "string"
  }
  ```
- **Response**: `{ "access_token": "string", "token_type": "bearer" }` (the refresh token is **not** in the JSON response, it is set as an `HttpOnly` cookie: `refresh_token`, scope `/auth`, 7 days)

### Token refresh
- **URL**: `POST /auth/refresh`
- **Description**: Generates a new access token from the refresh token read from the `HttpOnly` cookie (**no body required**, the token is never sent by the client)
- **Response**: `{ "access_token": "string", "token_type": "bearer" }`

### Logout
- **URL**: `POST /auth/logout`
- **Description**: Revokes the refresh token server-side (by its `jti`) and clears the cookie. Idempotent, does not require a valid access token.
- **Response**: `{ "message": "Logged out" }`

### Email verification
- **URL**: `GET /auth/verify-email?code=...` or `POST /auth/verify-email`
- **Description**: Verifies a confirmation code received by email and activates the account. The `GET` variant (query param) is kept for compatibility; the frontend uses the `POST` variant (JSON body) to avoid the code ending up in access logs.
- **Body (POST)**: `{ "code": "string" }`
- **Response**: `{ "message": "Email verified" }`

### Resend verification code
- **URL**: `POST /auth/resend-verification`
- **Description**: Regenerates and resends a verification code if the account exists and is not yet activated (never reveals whether the account actually exists)
- **Body**: `{ "identifier": "string" }` (username or email)
- **Response**: generic message, identical whether the account exists or not

## Cache management (`/caches`)

### GPX import
- **URL**: `POST /caches/upload-gpx`
- **Description**: Imports caches from a GPX or ZIP file (cgeo, Pocket Query), then triggers automatic challenge creation and UserChallenge synchronization
- **Query parameters**:
  - `import_mode`: `all` (every cache) or `found` (my finds), default `all`
  - `source_type`: `auto`, `cgeo`, `pocket_query`, default `auto`
- **Body**: multipart file `file`
- **Response**: `{ "summary": {...}, "challenges_stats": {...}, "sync_stats": {...}, "progress_stats": {...} }` (the last field only if `import_mode=found`)
- **Errors**: `400` invalid file, `413` file too large

### Filtered search
- **URL**: `POST /caches/by-filter`
- **Description**: Searches caches with combinable filters (text, type, size, difficulty/terrain, country/state, placement period, etc.)
- **Body**: filter object
- **Response**: paginated list of caches

### Caches within an area
- **URL**: `GET /caches/within-bbox`
- **Query parameters**: `min_lat`, `min_lon`, `max_lat`, `max_lon` *(required)*, `type_id`, `size_id` *(optional)*, `page`, `page_size` (max 200), `sort` (`-placed_at`, `-favorites`, `difficulty`, `terrain`), `compact` (bool)

- **URL**: `GET /caches/within-radius`
- **Query parameters**: `lat`, `lon` *(required)*, `radius_km` (0.1-100, default 10), `type_id`, `size_id`, `page`, `page_size`, `compact`

### Retrieve a cache
- **URL**: `GET /caches/{gc}`
- **Description**: Returns a cache by its GC code. `404` if not found.

- **URL**: `GET /caches/by-id/{id}`
- **Description**: Returns a cache by its MongoDB identifier (ObjectId).

## Administrative zones (`/zones`, `/geo`)

### List zones with counters

- **URL**: `GET /zones`
- **Description**: Returns administrative zones with the number of caches found by the current user. Only zones where the user has at least one found cache are returned.
- **Query parameters**:
  - `country` *(required)*: ISO country code, e.g. `FR`
  - `level` *(required)*: administrative level — `1` (regions) or `2` (departments)
  - `type` *(optional)*: filter on a cache type, e.g. `traditional`
- **Response**:
  ```json
  {
    "items": [
      { "code": "FR-38", "name": "Isère", "cache_count": 42 },
      { "code": "FR-84", "name": "Vaucluse", "cache_count": 7 }
    ]
  }
  ```

### Zone detail

- **URL**: `GET /zones/{code}`
- **Description**: Returns the zone detail with the total number of found caches and the first 10.
- **Path parameters**:
  - `code`: zone code, e.g. `FR-38`
- **Query parameters**:
  - `level` *(optional)*: `1` or `2` — disambiguates codes shared across levels (e.g. FR-93 = PACA region *and* Seine-Saint-Denis department)
  - `type` *(optional)*: filter on a cache type
- **Response**:
  ```json
  {
    "code": "FR-38",
    "name": "Isère",
    "cache_count": 42,
    "caches": [
      { "GC": "GC00001", "title": "Cache du Vercors", "type_code": "traditional", "difficulty": 2.0, "terrain": 3.0 }
    ]
  }
  ```

### Zone breakdown by type

- **URL**: `GET /zones/{code}/type-stats`
- **Description**: Returns the number of found caches per type for a zone. All cache types are always returned (count=0 for unmatched ones), sorted by the canonical GC.com order (`sort_order` in the `cache_types` collection).
- **Path parameters**:
  - `code`: zone code, e.g. `FR-84`
- **Query parameters**:
  - `level` *(optional)*: `1` or `2` — disambiguates codes shared across levels
- **Response**:
  ```json
  {
    "code": "FR-84",
    "name": "Auvergne-Rhône-Alpes",
    "type_counts": [
      { "type_code": "traditional", "type_name": "Traditional Cache", "count": 42 },
      { "type_code": "mystery",     "type_name": "Mystery Cache",     "count": 7  },
      { "type_code": "letterbox",   "type_name": "Letterbox Hybrid",  "count": 0  }
    ]
  }
  ```
- **Errors**:
  - `404` if the zone code is unknown

### Static GeoJSON

- **URL**: `GET /geo/FR/regions.geojson`
- **Description**: GeoJSON FeatureCollection of French regions. Served by FastAPI StaticFiles.

- **URL**: `GET /geo/FR/departements.geojson`
- **Description**: GeoJSON FeatureCollection of French departments.

## Challenges (`/challenges`)

### (Re)create challenges from caches
- **URL**: `POST /challenges/refresh-from-caches`
- **Description**: Scans caches flagged `challenge` and creates/updates the corresponding challenge documents. Admin only.
- **Body**: `{ "cache_ids": ["string", ...] }` *(optional, scans the whole collection if absent)*

## My challenges (`/my/challenges`)

### List challenges
- **URL**: `GET /my/challenges`
- **Query parameters**: `status` *(optional)*, `page` (default 1), `page_size` (default 50, max 200)
- **Response**: paginated list of UserChallenges

### Sync
- **URL**: `POST /my/challenges/sync`
- **Description**: Creates missing UserChallenges for the current user

### Bulk update
- **URL**: `PATCH /my/challenges`
- **Description**: Updates status/notes/`override_reason` for several UserChallenges at once (non-transactional, best-effort, 200 items max)
- **Body**: array of `{ "uc_id": "string", "status"?: "string", "notes"?: "string", "override_reason"?: "string" }`
- **Response**: per-item result (success/error) plus an update counter

### Challenge detail
- **URL**: `GET /my/challenges/{uc_id}`
- **Response**: `404` if the UserChallenge does not exist or does not belong to the user

### Single update
- **URL**: `PATCH /my/challenges/{uc_id}`
- **Body**: `{ "status"?: "pending"|"accepted"|"dismissed"|"completed", "notes"?: "string", "override_reason"?: "string" }`

### Calendar challenge
- **URL**: `GET /my/challenges/basics/calendar`
- **Description**: Checks completion of the calendar challenge (365 and 366 days) for the current user
- **Query parameters**: `cache_type`, `cache_size` *(optional, name-based filters)*

### D/T Matrix
- **URL**: `GET /my/challenges/basics/matrix`
- **Description**: Checks completion of the difficulty/terrain matrix (9x9) for the current user
- **Query parameters**: `cache_type`, `cache_size` *(optional, name-based filters)*

## Challenge tasks (`/my/challenges/{uc_id}/tasks`)

### List tasks
- **URL**: `GET /my/challenges/{uc_id}/tasks`
- **Response**: ordered list of tasks

### Replace tasks
- **URL**: `PUT /my/challenges/{uc_id}/tasks`
- **Description**: Replaces the entire task list (including order)
- **Body**: full list of tasks to apply

### Validate without persisting
- **URL**: `POST /my/challenges/{uc_id}/tasks/validate`
- **Description**: Validates the consistency of a task list without saving it

## Progress (`/my/challenges`)

### Progress history
- **URL**: `GET /my/challenges/{uc_id}/progress`
- **Response**: latest snapshot and history

### Progress evaluation
- **URL**: `POST /my/challenges/{uc_id}/progress/evaluate`
- **Description**: Evaluates and saves a new progress snapshot

### Bulk first snapshot
- **URL**: `POST /my/challenges/new/progress`
- **Description**: Evaluates a first snapshot for `accepted` UserChallenges with no existing progress
- **Body**: `{ "include_pending"?: bool, "limit"?: int, "since"?: "datetime" }` *(optional)*

## Challenge targets

### Evaluate a challenge's targets
- **URL**: `POST /my/challenges/{uc_id}/targets/evaluate`
- **Query parameters**: `limit_per_task` (default 500), `hard_limit_total` (default 2000), `include_geo_filter` (bool), `lat`, `lon`, `radius_km`, `force` (bool)

### List a challenge's targets
- **URL**: `GET /my/challenges/{uc_id}/targets`
- **Query parameters**: `page`, `page_size` (max 200), `sort` (default `-score`)

### A challenge's nearby targets
- **URL**: `GET /my/challenges/{uc_id}/targets/nearby`
- **Description**: Same as above, but filtered by proximity (`lat`/`lon`, default: user's last saved location)
- **Query parameters**: `radius_km` (default 50), `lat`, `lon`, `page`, `page_size`, `sort` (default `distance`)

### Delete a challenge's targets
- **URL**: `DELETE /my/challenges/{uc_id}/targets`

### List all my targets (every challenge)
- **URL**: `GET /my/targets`
- **Query parameters**: `status_filter` *(optional, e.g. `accepted`)*, `page`, `page_size`, `sort` (default `-score`)

### All my nearby targets
- **URL**: `GET /my/targets/nearby`
- **Query parameters**: `radius_km` (default 50), `lat`, `lon`, `page`, `page_size`, `status_filter`

### Targets freshness status
- **URL**: `GET /my/targets/refresh-status`
- **Description**: Indicates whether unfound caches have been imported since the last targets evaluation (`needs_refresh`)

### Bulk evaluation
- **URL**: `POST /my/targets/evaluate-all`
- **Description**: Evaluates targets for every `accepted` UserChallenge of the user

## User profile (`/my/profile`)

### Get profile
- **URL**: `GET /my/profile`
- **Response**: public profile info (`UserOut`)

> ⚠️ There is no generic `PUT /my/profile` route: updates go through the dedicated sub-routes below (`/location`, `/preferences`).

### Preferences
- **URL**: `PATCH /my/profile/preferences`
- **Description**: Partially updates preferences (only the fields provided are changed)
- **Body**: `{ "language"?: "string", "dark_mode"?: bool }`

### Location
- **URL**: `GET /my/profile/location` (last saved position)
- **URL**: `PUT /my/profile/location` (saves the position, via text `position`, e.g. DM coordinates, **or** numeric `lat`/`lon`)

### Statistics
- **URL**: `GET /my/profile/stats`
- **Response**: basic user statistics

### Found caches sync
- **URL**: `POST /my/profile/found-caches/sync`
- **Description**: Sends a text file containing GC codes, treated as the **complete and authoritative** list of found caches: caches missing from the list are removed, new ones are added, unrecognized codes are reported.
- **Body**: multipart file `file` (plain text)
- **Response**: `{ "nb_provided": int, "nb_deleted": int, "nb_added": int, "nb_unknown_gc": int, "unknown_gc_codes": [...] }`

## Utilities

### Health check
- **URL**: `GET /health`
- **Description**: Checks the availability of the API and its dependencies (database, email). Returns `503` if a service is degraded.
- **Response**: `{ "status": "ok"|"degraded", "timestamp": "...", "version": "...", "checks": { "database": "ok", "email": "ok" } }`

### Version and info
- **URL**: `GET /version`
- **Response**: `{ "version": "...", "environment": "...", "build_date": "..." }`

- **URL**: `GET /info`
- **Response**: API name, version, build date, documentation link, support URL

### Cache types and sizes
- **URL**: `GET /cache_types` or `GET /cache_sizes`
- **Response**: list of available types/sizes
