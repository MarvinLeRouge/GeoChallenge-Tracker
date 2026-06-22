# Traefik Harmonization Plan

**Date:** 2026-06-22
**Scope:** Infra — Docker Compose + Traefik (dev and prod)
**Branch:** `feat/traefik-harmonization`
**Reference project:** Triton (`~/projets/Triton`)

---

## Context

GeoChallenge-Tracker currently has a significant gap between its development and production environments at the infrastructure level:

- **Dev**: Services are exposed via direct port bindings (`5173`, `8000`, `8080`). Traefik is absent.
- **Prod**: Traefik is present, but with two separate subdomains (one for frontend, one for API) and hardcoded domain names in labels.

The Triton project establishes a more consistent and maintainable pattern:
- Single domain for the whole app, path-based routing
- Traefik present in both dev and prod
- Domain driven by a `${DOMAIN}` variable (not hardcoded)
- Consistent label conventions (`traefik.docker.network`, explicit `tls=true`)

The goal is to align GeoChallenge-Tracker with this Triton model.

---

## Current Architecture

### Dev (`docker-compose.yml` at project root)

```
Host:5173  →  frontend container (Vite dev server)
Host:8000  →  backend container (FastAPI)
Host:8080  →  tiles container (nginx)
Host:1080  →  maildev (SMTP UI)
Host:1025  →  maildev (SMTP)
```

No Traefik. Direct port bindings. Accessing the frontend at `localhost:5173` works, but
`VITE_API_URL=/api` (relative) requires a proxy — which doesn't exist in this setup.

### Prod (`ops/deploy/docker-compose.yml` + `~/projets/traefik/gc-tracker.yml`)

```
Internet → Traefik → gc-tracker.marvinlerouge.dev        → frontend nginx (port 80)
                   → api-gc-tracker.marvinlerouge.dev    → backend (port 8000)
```

Frontend nginx (`frontend/nginx.conf`) internally proxies:
- `/api/` → `backend:8000`
- `/tiles/` → `tiles:80`

Issues:
- Two separate subdomains (two DNS entries, two TLS certs)
- Domains hardcoded in Traefik labels (no `${DOMAIN}` variable)
- Missing `traefik.docker.network=traefik-public` label
- Missing explicit `tls=true` label
- The prod compose file exists in two places (`ops/deploy/` and `~/projets/traefik/`) — one is a local copy, but the duplication is a maintenance risk

---

## Target Architecture

### Dev

```
http://gc-tracker.marvinlerouge.local/api/*    → backend:8000  (Traefik strips /api)
http://gc-tracker.marvinlerouge.local/tiles/*  → tiles:80
http://gc-tracker.marvinlerouge.local/*        → frontend:5173 (Vite)
```

- Single local domain, HTTP only (entrypoint `web`)
- No exposed ports for backend/frontend/tiles
- Traefik handles path routing

### Prod

```
https://gc-tracker.marvinlerouge.dev/api/*     → backend:8000  (Traefik strips /api)
https://gc-tracker.marvinlerouge.dev/tiles/*   → tiles:80
https://gc-tracker.marvinlerouge.dev/*         → frontend nginx (static + SPA)
```

- Single domain via `${DOMAIN}` variable
- TLS via Let's Encrypt, entrypoint `websecure`
- Frontend nginx simplified (no more internal proxy blocks for `/api/` and `/tiles/`)

---

## Files to Modify or Create

### 1. `docker-compose.yml` (modify)

- Remove `ports:` from `backend`, `frontend`, `tiles`
- Add `traefik-public` (external) network to `backend`, `frontend`, `tiles`
- Add Traefik labels to `backend`:
  - Router `gctracker-api-dev`: `Host(gc-tracker.marvinlerouge.local) && PathPrefix(/api)`, entrypoint `web`
  - Middleware `gctracker-strip-api-dev`: `stripprefix=/api`
  - Service: port `8000`
- Add Traefik labels to `tiles`:
  - Router `gctracker-tiles-dev`: `Host(gc-tracker.marvinlerouge.local) && PathPrefix(/tiles)`, entrypoint `web`
  - Service: port `80`
- Add Traefik labels to `frontend`:
  - Router `gctracker-frontend-dev`: `Host(gc-tracker.marvinlerouge.local)`, entrypoint `web`
  - Service: port `5173`
- Keep `maildev` ports exposed (debug tool, direct access is fine)
- Declare `traefik-public` as an external network

### 2. `docker-compose.prod.yml` (create at project root)

New file replacing `ops/deploy/docker-compose.yml`, modeled on Triton's `docker-compose.prod.yml`:

- Uses images (`${IMAGE_BACKEND}`, `${IMAGE_FRONTEND}`)
- Domain via `${DOMAIN}` variable (no hardcoded hostnames)
- Entrypoint `websecure` + `tls=true` + `certresolver=letsencrypt`
- `traefik.docker.network=traefik-public` on all exposed services
- Same path routing as dev
- Includes `mailhog` (prod SMTP interceptor, internal only)
- Declares `internal` (bridge) and `traefik-public` (external) networks

### 3. `frontend/nginx.conf` (modify)

Remove the `/api/` and `/tiles/` proxy blocks — Traefik now routes those requests
before they reach nginx. The file becomes a pure static file server with SPA fallback.

Keep:
- Gzip compression
- Security headers
- Static asset caching
- SPA fallback (`try_files`)

Remove:
- `location ^~ /tiles/` proxy block
- `location /api/` proxy block
- The rate limiting zones for `api` and `tiles` (still keep them if they were used elsewhere, otherwise remove)

### 4. `.gitignore` (already modified in this commit)

- Replace `docs/work-in-progress` → `docs/ai/work-in-progress`

### 5. `.env.example` (modify)

- Add `DOMAIN=gc-tracker.marvinlerouge.dev`

### 6. `.env` (modify, not committed)

- Add `DOMAIN=gc-tracker.marvinlerouge.dev`
- Update `CORS_ORIGINS` to include `http://gc-tracker.marvinlerouge.local`

### 7. `ops/deploy/docker-compose.yml` (delete, after confirmation)

Superseded by `docker-compose.prod.yml` at the project root.

---

## What Does NOT Change

| File | Reason |
|------|--------|
| `backend/` | No infra changes |
| `frontend/Dockerfile` | Targets (dev/build/prod) unchanged |
| `ops/nginx/tiles.conf` | Tiles nginx config unchanged |
| `backend/Dockerfile` | Unchanged |
| `traefik/gc-tracker.yml` | Local reference copy, outside repo |

---

## Implementation Order

1. `docker-compose.yml` — dev Traefik integration
2. `docker-compose.prod.yml` — new prod file
3. `frontend/nginx.conf` — simplify (remove proxy blocks)
4. `.env.example` — add DOMAIN
5. Confirm deletion of `ops/deploy/docker-compose.yml`

Each step will be validated before proceeding to the next.

---

## DNS Note (local dev)

For `gc-tracker.marvinlerouge.local` to resolve locally, the host entry must exist:

```
127.0.0.1   gc-tracker.marvinlerouge.local
```

This should be added to `/etc/hosts` on the development machine. It is not managed by this repo.
