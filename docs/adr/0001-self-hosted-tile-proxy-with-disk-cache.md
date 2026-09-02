# ADR 0001: Self-hosted tile proxy with disk cache and OSM upstream rotation

**Status:** Accepted
**Date:** 2025-09-15
**Deciders:** Marvin Le Rouge
**Sources:** PR #1 (`infra(tiles): add tiles service with persistent cache volume and startup command`)

## Context

The frontend map views (choropleth, target search, calendar/matrix challenge maps) need raster map tiles. Calling a public OSM tile server directly from the browser on every page load is subject to OSM's usage policy (rate limits, no heavy/automated use, single-host `User-Agent` requirements) and gives no control over caching or availability if a single upstream host is degraded.

## Decision

Run a dedicated `tiles` service (nginx) in front of the OSM tile infrastructure rather than pointing the frontend at a public tile URL directly:

- The frontend requests tiles from `/tiles/{z}/{x}/{y}.png`, routed to the `tiles` container (Traefik in later harmonized routing, see ADR 0004).
- nginx proxies each tile request to the OSM upstream, rotating across multiple OSM subdomains to spread load and reduce the chance of hitting a single host's rate limit.
- Successfully fetched tiles are written to a persistent disk cache volume (`tiles_cache`), so repeat requests for the same tile are served locally instead of re-hitting OSM.
- A `/tiles/_health.png` endpoint backs the container healthcheck.

## Consequences

- Map tile traffic to OSM is bounded by cache hit rate rather than growing linearly with app usage, keeping the project within OSM's acceptable-use expectations.
- Tile availability no longer depends on a single OSM host being reachable at request time.
- The cache volume needs disk space and, longer term, an eviction policy; none was part of this initial change (no TTL or size cap on `tiles_cache` at introduction).
- One more stateful service (`tiles`) to operate and monitor alongside backend/frontend/MongoDB.

## Alternatives considered

Not explicitly recorded in the source PR. Pointing the frontend directly at a public OSM tile endpoint (no self-hosted proxy) was the implicit prior state; it was replaced rather than evaluated side by side in the PR description.
