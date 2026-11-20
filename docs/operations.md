[🇫🇷 Version française](operations.fr.md) | 🇬🇧 English version

---

# Operations Guide: GeoChallenge Tracker

**Creation date:** 2026-09-02
**Type:** Operational reference, kept accurate as the deploy/maintenance surface evolves
**Scope:** Deployment (dev and prod), backup and restore, routine maintenance, incident response

> This document covers *how to run the system*, not *why it's built this way* (see [`docs/adr/`](adr/) for the "why" behind Traefik, rate limiting, etc.) and not *how to set up a local dev environment from scratch* (see the root [`README.md`](../README.md) "Installation & Launch" section and [`docs/guides/`](guides/) for that).

---

## Deployment

### Dev

Covered by the root [`README.md`](../README.md): `docker compose up --build`, backend on `:8000`, frontend on `:5173`. Not duplicated here.

### Prod: pipeline

Production deploys are fully automated via GitHub Actions, in two chained workflows:

1. **CI** (`.github/workflows/ci.yml`) runs on every PR and push to `main`, path-filtered per part: backend lint, type checks, unit tests, integration tests on a disposable MongoDB and `pip-audit`; frontend lint, type checks, build, unit tests, Playwright e2e tests and `npm audit`. The `CI status` job aggregates them and is the required check on `main`.
2. **Build, Push & Deploy** (`.github/workflows/build-push-deploy.yml`) runs automatically once CI succeeds on `main` (`workflow_run` trigger), or can be triggered manually (`workflow_dispatch`), which bypasses the CI gate for hotfixes, rollbacks, or redeploys.
   - **Build & push**: backend and frontend Docker images are built and pushed to GHCR, each tagged both `sha-<7-char-commit-sha>` and `latest` (`ghcr.io/marvinlerouge/geochallenge-tracker/{backend,frontend}`).
   - **Deploy**: an SSH step on the production host fetches `docker-compose.prod.yml` and the tiles nginx config directly from `raw.githubusercontent.com`, pinned to the exact commit SHA being deployed, then runs `docker compose pull` followed by `docker compose up -d --remove-orphans`.

### Prod: topology

Routing is path-based on a single domain via Traefik (TLS through Let's Encrypt): `gc-tracker.marvinlerouge.dev/api/*` to the backend (prefix stripped before it reaches FastAPI), `gc-tracker.marvinlerouge.dev/tiles/*` to the tiles nginx service, everything else to the frontend. See [ADR 0004](adr/0004-traefik-reverse-proxy-with-harmonized-dev-prod-routing.md) for why this shape was chosen.

### Prod: server layout

On the deploy host, two directories under `/home/mlr/marvinlerouge.dev/gc-tracker/` (paths taken directly from `build-push-deploy.yml`):

- `compose/`: holds only the deployed `docker-compose.yml` (fetched fresh from `docker-compose.prod.yml` on every deploy, not hand-edited).
- `shared/`: holds everything that must survive a redeploy: `env/app.env` and `env/secrets.env` (not in the repo, see below), `backups/` (bind-mounted into the backend container at `/backups`), `uploads/` (bind-mounted at `/app/uploads`), and `ops/nginx/` (tiles config, fetched fresh like the compose file).

### Prod: env files

Containers get their configuration only through `env_file` in `docker-compose.prod.yml`; the compose file interpolates nothing from a file (the domain is written in the Traefik rules, `IMAGE_BACKEND` / `IMAGE_FRONTEND` are set by the deploy workflow, and default to the `:latest` images so manual `docker compose` commands in `compose/` work without them). Local development keeps the single root `.env`.

| File on the VPS | Loaded by | Holds | Template |
|---|---|---|---|
| `shared/env/app.env` | backend, frontend | non-secret settings (app identity, CORS, frontend URL, mail sender, backups, upload limits, elevation, `SENTRY_ENVIRONMENT`) | [`docker/env/app.env.example`](../docker/env/app.env.example) |
| `shared/env/secrets.env` | backend, loaded last so it wins | every topic holding a secret, kept whole: `MONGODB_*`, `JWT_*`, `ADMIN_*`, `SMTP_*`, Sentry DSNs | [`docker/env/secrets.env.example`](../docker/env/secrets.env.example) |

Both files are `chmod 600`, never committed. The deploy workflow creates `shared/env/` if missing, but does not write either file.

### Prod: rollback

Since `build-push-deploy.yml` tags every image with both `sha-<7-char-sha>` and `latest`, and GHCR doesn't prune old tags, the direct rollback path is to redeploy a specific older image on the host, from `compose/`: `IMAGE_BACKEND=ghcr.io/marvinlerouge/geochallenge-tracker/backend:sha-xxxxxxx IMAGE_FRONTEND=ghcr.io/marvinlerouge/geochallenge-tracker/frontend:sha-xxxxxxx docker compose up -d`. Re-running the deploy workflow manually (`workflow_dispatch`) against an older ref is the pipeline-driven equivalent.

---

## Backup and restore

All backup/restore routes live under `/maintenance` and require an admin account (the whole router is gated by `require_admin`).

- **`POST /maintenance/db_full_backup`**: dumps every collection to a single timestamped, zipped JSON file under `/backups/full_backup`, which is bind-mounted to the host's `shared/backups/`, so it survives redeploys and container recreation.
- **`GET /maintenance/db_backups`**: lists all backup files, both cleanup and full backups.
- **`GET /maintenance/backups/{filepath}`**: downloads a specific backup file.
- **`POST /maintenance/db_full_restore/{filename}`**: restores from a backup file. Two flags control blast radius:
  - `dry_run` (default `True`): previews the restore (counts what would be inserted) without writing anything.
  - `drop_existing` (default `False`): clears a collection before restoring into it.
  - A genuinely destructive call (`dry_run=False` **and** `drop_existing=True`) cannot run in one request: the first call (no `key`) only validates the backup file and returns a `confirmation_key` valid for 10 minutes; the restore only executes once that same key is resubmitted via `?key=...`. Any non-destructive combination runs immediately, no key needed.

**Practical incident use:** always call `db_full_restore` with `dry_run=True` first to confirm the backup file is the one you expect (collection names, document counts) before considering a destructive restore.

---

## Routine maintenance

Also under `/maintenance`, admin-only:

- **`GET /maintenance/db_cleanup`**: scans all collections (in dependency order, most-referenced first) for orphaned documents (dangling references to deleted parents) and returns a report plus a `confirmation_key` valid 10 minutes. Read-only, changes nothing.
- **`DELETE /maintenance/db_cleanup?key=...`**: executes the cleanup found by the matching `GET` call, backing up every deleted document to a timestamped zip under `/backups/db_cleanup` first.
- **`DELETE /maintenance/expired-verifications`**: removes expired email verification codes.

### Logs

The backend writes every log line to stderr (`docker logs`) as one JSON object per line, through `structlog` (`configure_logging()` in `backend/app/core/observability.py`): `timestamp` (UTC), `level`, `logger`, `event`, plus the fields of the call and the traceback in `exception`. Existing `logging.getLogger(...)` loggers go through the same output. `LOG_FORMAT=console` gives readable lines instead (default when stderr is a terminal), `LOG_LEVEL` sets the level (default `info`).

Each request gets one `request_handled` line (`method`, `path`, `status`, `duration_ms`; ERROR level for a 5xx), written by `backend/app/core/request_logging.py`. The query string, headers and body are never logged, which is why uvicorn's access log is disabled: it kept query strings, such as the email verification code.

The files below are still written alongside. Three loggers write daily-rotated files, auto-purged after 30 days: `generic.log` (INFO+, `geocaching.generic`), `errors.log` (ERROR+, `geocaching.errors`), `security.log` (INFO+, `geocaching.security`, security-relevant events such as failed logins).

**Caveat:** these files are written to a relative `logs/` directory inside the backend container (`backend/app/core/logging_config.py`), which is **not** bind-mounted to the host in `docker-compose.prod.yml` (unlike `/backups` and `/app/uploads`). In practice, log history does not survive a container recreation or redeploy today; only backups and uploads are currently persisted that way.

### Error tracking (Sentry)

Unhandled errors (backend 500s, frontend Vue and JavaScript errors) are reported to Sentry, EU region, one project per side (`geochallenge-backend`, `geochallenge-frontend`). Client errors (401, 404, 422, 429) are not reported. Only stack traces are sent: no request body, header, cookie, query string, user data, component prop, breadcrumb or local variable (`dataCollection` plus a `beforeSend` / `before_send` scrubber; page URLs keep their path only). Each 500 is also logged with its traceback (`log.exception` in `general_exception_handler`).

Tracking is off when the DSNs are empty.

| Variable | Read by | Local | Production |
|---|---|---|---|
| `SENTRY_BACKEND_DSN` | backend, at startup (`app/core/observability.py`) | `.env` | server `secrets.env` |
| `SENTRY_FRONTEND_DSN` | backend, at startup (relay allow-list) | `.env` | server `secrets.env` |
| `SENTRY_ENVIRONMENT` | backend (default `development`) | `.env` | server `app.env` (`production`) |
| `VITE_SENTRY_DSN` | frontend, at build time (`src/observability.ts`) | from `SENTRY_FRONTEND_DSN` in `docker-compose.yml` | GitHub secret, build arg in `build-push-deploy.yml` |
| `VITE_SENTRY_ENVIRONMENT` | frontend, at build time (default `development`) | from `SENTRY_ENVIRONMENT` in `docker-compose.yml` | `production`, set by `build-push-deploy.yml` |

The backend reads these from the process environment, not from the app settings: outside Docker, export them.

**Relay.** Ad-blockers (uBlock Origin, Firefox tracking protection) drop browser requests to `*.sentry.io`. The browser therefore posts its events to its own origin, at `/api/<hash of its DSN>`, and the backend forwards them to Sentry (`app/api/routes/sentry_tunnel.py`). The CSP stays `connect-src 'self'`.

- The path is a hash of the frontend DSN, computed the same way on both sides. The GitHub secret `VITE_SENTRY_DSN` and the server `SENTRY_FRONTEND_DSN` must match exactly: one character off and every frontend event ends in 404, silently. The backend logs a warning at startup when only one of `SENTRY_BACKEND_DSN` / `SENTRY_FRONTEND_DSN` is set.
- Only envelopes for `SENTRY_FRONTEND_DSN` are forwarded (others get 403, malformed bodies 400, an unreachable Sentry 502). Cookies, `Referer` and the client IP are not forwarded.
- The route has no rate limit of its own: abuse can only spend the Sentry project quota, which Sentry rate-limits.

**Setup, once:** in each Sentry project, *Settings*, *Security & Privacy*: enable *Data Scrubber* and *Use Default Scrubbers*, and *Prevent Storing of IP Addresses*. Then redeploy.

**Checking production:** from a browser **without** extensions, run `setTimeout(() => { throw new Error('sentry check') }, 0)` in the console and check the issue under `environment: production`. Then again with uBlock / tracking protection on, to validate the relay (a POST to `/api/<hash>` answering 200, nothing to `sentry.io`).

---

## Incident response

- **A service looks down:** `docker compose ps` on the deploy host to check container health status; the backend's healthcheck hits `GET /health`, the tiles service's hits `GET /tiles/_health.png`. `docker compose logs <service>` for recent output (subject to the logs caveat above: only what's currently in the running container, nothing from before the last recreation).
- **A deploy broke something:** see Rollback above, redeploy the previous `sha-<7-char-sha>` image tag.
- **Data needs restoring:** see Backup and restore above; always dry-run first.
