[🇫🇷 Version française](product-context.fr.md) | 🇬🇧 English version

---

# Product Context: GeoChallenge Tracker

**Creation date:** 2026-09-02
**Type:** Product reference, durable product context maintained alongside the codebase
**Scope:** Whole product (audience, positioning, capabilities, brand and accessibility commitments)

> This document is the public, versioned mirror of the project's product context. A companion file, `PRODUCT.md` at the repo root, is gitignored and serves as the machine-readable entry point for the design/product skill used during development; its content is reproduced here.

---

## Platform

Web.

## Stack

Existing codebase, not greenfield: Vue 3 + TypeScript + Vite, Tailwind CSS 3 (with the Flowbite plugin and `flowbite-vue` components), Pinia for state, `vue-router`, Leaflet (+ `leaflet-draw`, `leaflet.markercluster`) for maps, Heroicons and Lucide for icons, `vue-sonner` for toasts. Backend is FastAPI + MongoDB, consumed over REST via axios.

## Users

Primary user: a passionate, self-directed geocacher who defines and tracks custom challenges (e.g. a 9x9 D/T matrix, a 365-day calendar challenge) and wants to replace scattered spreadsheets and notes with a single tool. Solo usage, the product is not currently aimed at clubs or group coordination.

## Product Purpose

Lets geocachers import their finds and known caches from GPX exports, automatically detect challenge-type caches among them, define the rules of a challenge in a dedicated task language, and track completion progress (including projections and target-cache suggestions) instead of manually maintaining spreadsheets.

## Positioning

Automatic challenge detection from imported GPX data, combined with a dedicated language for describing challenge rules/tasks and automatic progress tracking, is the core differentiator versus generic alternatives (plain spreadsheets, Project-GC, GSAK).

## Operating Context

- Solo use, desktop and mobile web.
- Source data: GPX files exported from Geocaching.com (finds, and caches within an area).
- Classic challenge types already supported: D/T matrix (9x9), calendar challenge (365 days), plus custom challenges via the task-description language.
- Map-based workflows: search caches by radius/bbox, visualize zones, identify target caches that best advance a challenge.
- Primary audience is the francophone geocaching community (France + other French-speaking countries); UI copy is in French. No international/English expansion planned in the near term.

## Capabilities and Constraints

- Auth: register/login/refresh, email verification by code.
- Caches: synchronous GPX/ZIP import, search by bbox/radius/advanced filters, lookup by GC code or Mongo id.
- Challenges: created from caches; user-challenges support listing, per-item patch, D/T matrix and calendar verification.
- Targets: evaluation, listing, proximity search.
- Stats: completion projections.
- Dark mode: the `dark_mode` user preference (backend user model) is fully implemented in the frontend via `dark:` Tailwind variants across all pages, with persistence handled by a dedicated `theme` store (`frontend/src/store/theme.ts`).

## Brand Commitments

- Product name: "GeoChallenge Tracker".
- A `gold` color scale is already committed in `tailwind.config.ts` (50-900, anchored around `#FFD700`), a deliberate, geocaching/treasure-appropriate brand color to preserve and build on, not replace.

## Evidence on Hand

Real product screenshots exist under `docs/screenshots/` (cache search by radius and bbox, D/T matrix filtered/unfiltered, calendar challenge filtered/unfiltered) and are embedded in the README. No customer testimonials, case studies, or press exist, do not fabricate any.

## Product Principles

1. Replace spreadsheet-driven challenge tracking with automatic detection and progress computation, the tool should always do the counting, never the user.
2. French-first, geocaching-literate voice: use the community's own vocabulary (GC code, D/T, FTF, matrix, calendar challenge) rather than generic SaaS phrasing.
3. Map and data views must stay legible under real outdoor/mobile conditions, not just at a desk.
4. Preserve the existing gold/treasure-hunt visual identity; extend it deliberately rather than genericizing it away.
5. Solo-first workflows: no design decision should assume a team or shared-editing context unless explicitly scoped later.

## Accessibility & Inclusion

No formally confirmed accessibility standard yet. Known gap flagged in the existing product backlog: calendar challenge day details are only exposed via a hover `title` attribute, which is invisible on touch devices and weak for screen readers, a real constraint future calendar work must address, not yet a broader documented requirement.
