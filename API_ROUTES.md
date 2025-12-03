# 🧭 GeoChallenge Tracker - API Routes Documentation

## Authentication Routes (`/auth`)

- **`POST /auth/register`** - Register a new user
- **`POST /auth/login`** - Login user and generate JWT tokens
- **`POST /auth/refresh`** - Refresh access token using refresh token
- **`GET /auth/verify-email`** - Verify email via code
- **`POST /auth/verify-email`** - Verify email via POST method
- **`POST /auth/resend-verification`** - Resend verification email

## Base Routes (`/`)

- **`GET /cache_types`** - Get all available cache types
- **`GET /cache_sizes`** - Get all available cache sizes
- **`GET /ping`** - Health check endpoint

## Cache Routes (`/caches`)

- **`POST /caches/upload-gpx`** - Import caches from GPX/ZIP file with optional find marking
- **`POST /caches/by-filter`** - Search caches with multiple filters (text, type, size, location, difficulty, terrain, attributes, bounding box)
- **`GET /caches/within-bbox`** - Get caches within a bounding box
- **`GET /caches/within-radius`** - Get caches within a radius around a point
- **`GET /caches/{gc}`** - Get a cache by its GC code
- **`GET /caches/by-id/{id}`** - Get a cache by its MongoDB ObjectId

## Challenge Routes (`/challenges`)

- **`POST /challenges/refresh-from-caches`** - Recreate challenges from cache data (admin only)

## User Challenges Routes (`/my/challenges`)

- **`POST /my/challenges/sync`** - Sync missing UserChallenges for current user
- **`GET /my/challenges`** - List user challenges with optional filtering and pagination
- **`PATCH /my/challenges`** - Batch update multiple UserChallenges
- **`GET /my/challenges/{uc_id}`** - Get details of a specific UserChallenge
- **`PATCH /my/challenges/{uc_id}`** - Update a specific UserChallenge
- **`GET /my/challenges/basics/calendar`** - Verify user's calendar challenge completion
- **`GET /my/challenges/basics/matrix`** - Verify user's D/T matrix challenge completion

## User Profile Routes (`/my/profile`)

- **`PUT /my/profile/location`** - Set or update user location (coordinates or text)
- **`GET /my/profile/location`** - Get user's current location
- **`GET /my/profile`** - Get user profile

## User Challenge Tasks Routes (`/my/challenges/{uc_id}/tasks`)

- **`GET /my/challenges/{uc_id}/tasks`** - List tasks for a UserChallenge
- **`PUT /my/challenges/{uc_id}/tasks`** - Replace all tasks for a UserChallenge
- **`POST /my/challenges/{uc_id}/tasks/validate`** - Validate a list of tasks without persistence

## User Challenge Progress Routes (`/my/challenges`)

- **`GET /my/challenges/{uc_id}/progress`** - Get latest progress snapshot and history for a UserChallenge
- **`POST /my/challenges/{uc_id}/progress/evaluate`** - Evaluate and save immediate progress snapshot
- **`POST /my/challenges/new/progress`** - Evaluate first progress for challenges without existing progress

## User Challenge Targets Routes (`/my`)

- **`POST /my/challenges/{uc_id}/targets/evaluate`** - Evaluate and persist targets for a UserChallenge
- **`GET /my/challenges/{uc_id}/targets`** - List targets for a UserChallenge with pagination
- **`GET /my/challenges/{uc_id}/targets/nearby`** - List nearby targets for a UserChallenge
- **`GET /my/targets`** - List all user's targets across all challenges
- **`GET /my/targets/nearby`** - List nearby targets across all challenges
- **`DELETE /my/challenges/{uc_id}/targets`** - Delete all targets for a UserChallenge

## Cache Elevation Routes (`/caches_elevation`)

- **`POST /caches_elevation/caches/elevation/backfill`** - Backfill missing elevations for caches (admin only)

## Maintenance Routes (`/maintenance`)

- **`GET /maintenance`** - Basic maintenance endpoint
- **`POST /maintenance`** - Basic maintenance endpoint
- **`GET /maintenance/db_cleanup`** - Analyze database for orphaned records
- **`DELETE /maintenance/db_cleanup`** - Execute cleanup of orphaned records
- **`GET /maintenance/db_cleanup/backups`** - List cleanup backup files
- **`GET /maintenance/backups/{filepath:path}`** - Download backup files
- **`POST /maintenance/db_full_backup`** - Create full database backup
- **`POST /maintenance/db_full_restore/{filename}`** - Restore from full backup
- **`GET /maintenance/db_backups`** - List all backup files