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

1. **CI** (`.github/workflows/ci.yml`) runs on every push/PR to `main`: backend tests, frontend tests, lint, type checks.
2. **Build, Push & Deploy** (`.github/workflows/build-push.yml`) runs automatically once CI succeeds on `main` (`workflow_run` trigger), or can be triggered manually (`workflow_dispatch`), which bypasses the CI gate for hotfixes, rollbacks, or redeploys.
   - **Build & push**: backend and frontend Docker images are built and pushed to GHCR, each tagged both `sha-<7-char-commit-sha>` and `latest` (`ghcr.io/marvinlerouge/geochallenge-tracker/{backend,frontend}`).
   - **Deploy**: an SSH step on the production host fetches `docker-compose.prod.yml` and the tiles nginx config directly from `raw.githubusercontent.com`, pinned to the exact commit SHA being deployed, then runs `docker compose pull` followed by `docker compose up -d --remove-orphans`.

### Prod: topology

Routing is path-based on a single domain via Traefik (TLS through Let's Encrypt): `${DOMAIN}/api/*` to the backend (prefix stripped before it reaches FastAPI), `${DOMAIN}/tiles/*` to the tiles nginx service, everything else to the frontend. See [ADR 0004](adr/0004-traefik-reverse-proxy-with-harmonized-dev-prod-routing.md) for why this shape was chosen.

### Prod: server layout

On the deploy host, two directories (paths taken directly from `build-push.yml`):

- `.../gc-tracker/compose/`: holds the deployed `docker-compose.yml` (fetched fresh from `docker-compose.prod.yml` on every deploy, not hand-edited).
- `.../gc-tracker/shared/`: holds everything that must survive a redeploy: `env/app.env` and `env/secrets.env` (not in the repo), `backups/` (bind-mounted into the backend container at `/backups`), `uploads/` (bind-mounted at `/app/uploads`), and `ops/nginx/` (tiles config, fetched fresh like the compose file).

### Prod: rollback

Since `build-push.yml` tags every image with both `sha-<7-char-sha>` and `latest`, and GHCR doesn't prune old tags, the direct rollback path is to redeploy a specific older image on the host: set `IMAGE_TAG=sha-xxxxxxx` and re-run `docker compose --env-file ../shared/env/app.env up -d` with that tag. Re-running the deploy workflow manually (`workflow_dispatch`) against an older ref is the pipeline-driven equivalent.

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

Three loggers write daily-rotated files, auto-purged after 30 days: `generic.log` (INFO+, `geocaching.generic`), `errors.log` (ERROR+, `geocaching.errors`), `security.log` (INFO+, `geocaching.security`, security-relevant events such as failed logins).

**Caveat:** these files are written to a relative `logs/` directory inside the backend container (`backend/app/core/logging_config.py`), which is **not** bind-mounted to the host in `docker-compose.prod.yml` (unlike `/backups` and `/app/uploads`). In practice, log history does not survive a container recreation or redeploy today; only backups and uploads are currently persisted that way.

---

## Incident response

- **A service looks down:** `docker compose ps` on the deploy host to check container health status; the backend's healthcheck hits `GET /health`, the tiles service's hits `GET /tiles/_health.png`. `docker compose logs <service>` for recent output (subject to the logs caveat above: only what's currently in the running container, nothing from before the last recreation).
- **A deploy broke something:** see Rollback above, redeploy the previous `sha-<7-char-sha>` image tag.
- **Data needs restoring:** see Backup and restore above; always dry-run first.
