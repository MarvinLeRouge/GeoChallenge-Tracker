# ADR 0004: Traefik as reverse proxy, with harmonized dev/prod routing

**Status:** Accepted
**Date:** 2026-03-30 (initial adoption); 2026-06-24 (harmonization)
**Deciders:** Marvin Le Rouge
**Sources:** PR #25 (`infra/traefik-deploy`), PR #61 (`feat/traefik-harmonization`)

## Context

The production deployment originally ran each service (backend, frontend, tiles) with directly exposed Docker ports, with nginx in the frontend container handling `/api/*` and `/tiles/*` proxying to the other containers. This setup was specific to this project and diverged from the local dev environment, which had its own port layout.

A first migration (PR #25, December 2025) introduced Traefik v3 as the production reverse proxy, replacing exposed ports with Traefik labels and TLS termination via Let's Encrypt (Cloudflare DNS challenge), routed on a dedicated subdomain (`gc-tracker.marvinlerouge.dev`). This solved production TLS/routing but left dev on its own, unrelated setup, and did not address the broader goal of a consistent deployment model across the project portfolio (the Triton project already used a single-domain, path-based Traefik pattern in both dev and prod).

## Decision

Harmonize on Traefik in both dev and prod, using path-based routing on a single domain rather than per-service subdomains or exposed ports, mirroring the Triton project's reference model:

- **Dev** (`docker-compose.yml`): domain `gc-tracker.marvinlerouge.local`, HTTP on the `web` entrypoint, no host ports exposed for backend/frontend/tiles. Traefik labels route `/api/*` to the backend, `/tiles/*` to the tile server, and everything else to the Vite frontend.
- **Prod** (`docker-compose.prod.yml`, at the project root, replacing `ops/deploy/docker-compose.yml`): the same path-based routing, on the `websecure` entrypoint with TLS via Let's Encrypt, domain supplied through a `${DOMAIN}` variable rather than hardcoded.
- Frontend nginx config drops the `/api/` and `/tiles/` proxy blocks it used to own; Traefik now intercepts those paths upstream, and nginx only serves static files and the SPA fallback.
- Vite dev server config adds the local domain to `allowedHosts` and routes HMR through Traefik on port 80, so dev traffic flows through the same path Traefik uses in prod.

## Consequences

- Dev now mirrors prod's routing topology; a routing bug is reproducible locally instead of only surfacing after deploy.
- No service other than Traefik itself exposes a host port in either environment, shrinking the local attack surface and matching prod's constraints during dev testing.
- The path-based, single-domain model lines up with the Triton project, making GeoChallenge-Tracker the reference implementation used when harmonizing other projects in the portfolio (HiveMind, MarvinLeRouge, Summit-Stats).
- Frontend nginx has one less responsibility (no more upstream proxying), simplifying `frontend/nginx.conf`.
- The original subdomain-based prod setup from PR #25 (`gc-tracker.marvinlerouge.dev`, TLS via Cloudflare DNS challenge) is superseded by this path-based model; the DNS/TLS mechanics it introduced (Let's Encrypt, Cloudflare challenge) carry over, only the routing shape changes.

## Alternatives considered

Not explicitly recorded in the source PRs beyond the initial exposed-ports/nginx-proxy setup that predated Traefik entirely (PR #25's "before" state). No evidence of a documented comparison between subdomain-based and path-based routing at decision time; the switch to path-based routing tracks the cross-project convention rather than a fresh evaluation for this project alone.
