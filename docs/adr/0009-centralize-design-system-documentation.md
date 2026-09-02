# ADR 0009: Centralize design-system decisions in durable documentation

**Status:** Accepted
**Date:** 2026-08-02
**Deciders:** Marvin Le Rouge
**Sources:** PR #101 (`docs: publish the frontend design system and close the design audit item in README`)

## Context

The frontend design audit (dark mode, stat-tile color roles, card hierarchy, loading indicator) produced real, consistent design decisions across many PRs, but those decisions were documented nowhere durable, only scattered across individual PR descriptions. Anyone needing to know the intended color roles or component conventions had to dig through PR history rather than read a single reference.

## Decision

Publish a committed, public design reference and treat it as the durable record going forward:

- `docs/design-system.md` (public, French): a human-readable design reference covering colors (each with a descriptive name plus its real Tailwind token in parentheses), typography, layout, elevation, shapes, components, and do's/don'ts.
- This file mirrors the content of `DESIGN.md`, the gitignored, skill-consumed format with YAML frontmatter used by local AI tooling, kept out of git like `PRODUCT.md` per the project's convention for AI-tooling working files (see `docs/product-context.md` for the equivalent pattern applied to `PRODUCT.md`).
- `README.md`/`README.fr.md` move the "Frontend design audit" backlog item (6 items) from "Ongoing analysis" to "Recently completed" and link to the new doc.
- No code changes: this is documentation-only, formalizing decisions already shipped.

## Consequences

- Design decisions (color roles, component conventions) now have one authoritative, versioned, public location instead of being reconstructable only from PR archaeology.
- The gitignored `DESIGN.md` (tooling-facing) and the committed `docs/design-system.md` (human-facing) must be kept in sync manually; there is no automated check that they agree.
- Establishes a repeatable pattern (public docs/ narrative mirror of a gitignored tooling file) reused later for `PRODUCT.md` -> `docs/product-context.md`.

## Alternatives considered

Not explicitly recorded in the source PR beyond the "nowhere durable, scattered across PR descriptions" state it replaces. No evidence of a documented comparison against alternatives such as Storybook-style living documentation or inline component comments.
