# ADR 0003: Standardize toast notifications on vue-sonner

**Status:** Accepted
**Date:** 2026-03-25
**Deciders:** Marvin Le Rouge
**Sources:** PR #14 (`fix(ui): standardize on vue-sonner, remove BaseToast`)

## Context

Two toast notification systems coexisted in the frontend: `vue-sonner` (already mounted via `<Toaster>` in `AppShell` and used on Register and ImportGpx) and a custom `BaseToast.vue` component wired through Vue's provide/inject, used on Tasks, List, and session-expiry flows. Several pages had no error feedback at all: map searches (`WithinBbox`, `WithinRadius`) failed silently with no toast on either system.

## Decision

Standardize entirely on `vue-sonner` and remove the custom alternative:

- Delete `BaseToast.vue` and the provide/inject mechanism it relied on.
- Delete `toastBus.ts`, made redundant since `toast()` is a plain module-level function under `vue-sonner`, needing no bus.
- Add success/error toasts to every user-facing mutation.
- Add `catch` blocks with error toasts to the previously silent map searches (`WithinBbox`, `WithinRadius`).
- Apply a consistent rule: `toast.success` on success, `toast.error` with a readable description on failure.

## Consequences

- One toast system and one API (`toast.success` / `toast.error`) across the whole frontend, no more provide/inject plumbing to maintain for notifications.
- Previously-silent failure paths (map searches) now surface errors to the user.
- Any future page must follow the success/error toast convention from PR #14 onward rather than introduce a new pattern.

## Alternatives considered

Not explicitly recorded in the source PR beyond the two-system state it replaces (`vue-sonner` on some pages, `BaseToast` via provide/inject on others). No evidence of a documented comparison against a third notification library.
