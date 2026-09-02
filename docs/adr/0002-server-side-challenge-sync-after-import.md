# ADR 0002: Server-side challenge sync triggered after GPX import

**Status:** Accepted
**Date:** 2026-03-22
**Deciders:** Marvin Le Rouge
**Sources:** PR #3 (`fix(import): move user challenge sync from frontend to backend`)

## Context

After a GPX upload, newly imported caches can complete or advance a user's challenges. Challenge sync (evaluating user-challenges against the caches just imported) was originally triggered by the frontend issuing a separate `POST /my/challenges/sync` call after the upload request finished. This made the sync step depend on the frontend staying alive and making a second round trip: an interruption (closed tab, network failure, navigation away) between the two requests left the import done but the sync never run, with no automatic retry.

## Decision

Move the sync trigger into the backend so it happens as part of the same import operation:

- `caches.py`'s import route calls `sync_user_challenges(user_id)` immediately after `create_new_challenges_from_caches()`, in the same request/response cycle as the upload.
- The import response includes `sync_stats`, so the frontend still gets sync results to display, but no longer has to initiate the sync itself.
- `ImportGpx.vue` drops its manual `POST /my/challenges/sync` call and reads `sync_stats` from the upload response instead.
- A related naming fix ships in the same PR: `challenge_stats` is renamed to `challenges_stats` in both the response type and the frontend usage.

## Consequences

- Import and sync become one atomic server-side operation from the client's point of view: if the upload succeeds, sync has already run, regardless of what the frontend does afterward.
- One fewer HTTP round trip for the same user-visible outcome.
- The frontend can no longer trigger a sync independently of an import; if that capability is needed later (e.g. a manual "resync" action), it would need its own explicit route.

## Alternatives considered

Not explicitly recorded in the source PR beyond the two-request frontend-triggered flow that predated this change, which is the state the PR replaces.
