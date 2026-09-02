[🇫🇷 Version française](design-system.fr.md) | 🇬🇧 English version

---

# Design System — GeoChallenge Tracker

**Creation date:** 2026-08-03
**Type:** Design reference — visual conventions established in the code
**Scope:** Frontend (Vue 3 + Tailwind CSS 3), from the frontend design audit (dark mode, color consistency, visual hierarchy, loading feedback)

> This document is the public, versioned record of the project's design choices. A companion file, `DESIGN.md` at the repo root, is gitignored and serves as the machine-readable entry point for the design skill used during development; its narrative content is reproduced here.

---

## Overview

**"The Treasure-Hunt Dashboard"**

GeoChallenge Tracker replaces spreadsheet-driven challenge tracking with automatic detection and computed progress. Most of the time the user is at a desk or on a couch planning and reviewing, not out in the field — the exception being the "Targets" map, used while moving to find the next cache. The visual system therefore follows Operate-mode priorities: scanability, consistency, and low cognitive load beat decoration. Color is never used for atmosphere; it is a functional signal that always keeps the same meaning wherever it appears. The one genuinely "brand" color — a gold scale anchored on `#FFD700`, already present in `tailwind.config.ts` — is used sparingly, as a symbolic reward marker (the trophy icon on a completed challenge), not as a dominant visual accent.

**Key characteristics:**
- Flat surfaces (a border, not a shadow, defines a card)
- One role per color, reused identically across every page
- Icon = what the number is about; color = what kind of number it is
- Dark mode is a first-class parallel palette, not an afterthought
- French-first, geocaching-native vocabulary (GC code, D/T, FTF, matrix, calendar challenge)

## Colors

Every non-neutral color carries a fixed **role**, established and checked for WCAG AA contrast during the frontend design audit (August 2026). The same color always keeps the same role across every page — a color is never picked page by page for visual variety.

### Primary
- **Primary blue** (`blue-600` / `#2563eb`, hover `blue-700` / `#1d4ed8`): the default action color — primary buttons ("Save", "Log in"), the main completion-rate tile, active-state highlights (radio/checkbox accent, selected filter).

### Secondary
- **Success green** (`green-600` / `#16a34a` for the icon; label text in light mode is bumped to `green-700` / `#15803d` to meet AA contrast on `green-50` background; `green-800` / `#166534` for the big number): marks a success/completion counter — "days completed", "combinations completed", "Done". Never used for an in-progress or neutral state.
- **Secondary purple** (`purple-600` / `#9333ea`, deep `purple-800` / `#6b21a8`): a secondary view or variant of a rate that already has a primary-blue equivalent in the same tile row — e.g. the 366-day completion rate (leap year) next to the 365-day one, or "next round" next to the current rate.
- **Meta indigo** (`indigo-600` / `#4f46e5`, deep `indigo-800` / `#3730a3`): a recurring meta counter that isn't a plain total — completed "matrix rounds". Also used for the secondary/sync action button (found caches sync) and the "on" state of toggles (dark mode).

### Tertiary
- **Warning amber** (`yellow-600`/`700`/`800`): something the user should notice without it being an error — "no location configured", unrecognized GC codes after a sync.
- **Danger red** (`red-600` for buttons/errors, `red-700`/`800` for banner text): destructive actions ("Delete") and error states.

### Neutral
- **Neutral ink** (`gray-900` text in light mode / `gray-100` in dark mode): headings and primary text.
- **Neutral label** (`gray-500`/`600` in light mode / `gray-400` in dark mode): secondary text, form labels, helper text, and any stat tile whose number has no good/bad polarity (a plain activity counter, a total).
- **Neutral surface** (`white` / `gray-800` for card background, `gray-100` / `gray-900` for the lightest tinted tile background, `gray-200` in light mode / `gray-700` in dark mode for borders and separators): the structural neutral palette every card, form field, or separator is built from.

### Named rules
**The single-role rule.** A color never appears "because it looks nice next to the others". Before adding a color to a tile row, name the role it plays (success / primary rate / secondary rate / meta counter / neutral); if the role already has a color elsewhere in the app, reuse it.

**The icon+color rule.** A colored stat tile always pairs its role color with an icon that names the precise subject (`CheckCircleIcon` for a completion counter, `CalendarIcon` for a day-based rate, `Squares2X2Icon` for a grid/combination rate, `TrophyIcon` for a meta counter). Color alone never carries the full meaning.

**The rare-gold rule.** `gold-600` (`#E6C200`) is reserved for the completed-challenge trophy motif. It never appears on a button, a link, or a background — its rarity is what keeps it symbolic.

**The verified-contrast rule.** Every new text/background or icon/background pairing is checked against WCAG AA (4.5:1 for text, 3:1 for icons/non-text UI) using the project's actual Tailwind hex values, never by eye. This caught a real failure during the audit: `green-600` label text on `green-50` background measured 3.15:1 and had to move to `green-700` (4.79:1).

## Typography

**Typeface:** Tailwind's default system font stack (`ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, ...`) — no custom web font is committed to the project.

**Character:** deliberately plain and native; the product leans on layout, color roles, and icons for hierarchy rather than typographic effects.

### Hierarchy
- **Title** (`font-bold`, `text-2xl`): page `<h1>` headings ("My Profile", "Calendar Challenge").
- **Header** (`font-medium`, `text-lg`): card/section `<h3>` headings, usually paired with a small icon.
- **Body** (`text-sm`, normal weight): form labels, running text, button text, table cells.
- **Label** (`text-xs`, `text-gray-500`/`400`): helper text, field sub-text, secondary metadata (e.g. a GC code, a timestamp).

## Layout

Content pages are centered and width-constrained (`max-w-3xl` to `max-w-4xl`, `mx-auto`), with `p-4`-`p-6` outer padding and vertical rhythm via `space-y-4`/`space-y-6` between sections — no grid system beyond Tailwind's responsive `grid-cols-*` for tile rows and card grids. Map pages deliberately break this pattern: they render full-frame (`absolute inset-0`) since the map itself is the content, with floating panels (toolbar, legend, results) positioned in the corners rather than stacked in a scrolling column.

## Elevation & Depth

The system is flat by default. A card is defined by a 1px border (`border border-gray-200` / dark `border-gray-700`) and a background change, not a shadow. `shadow-sm` appears lightly on a few bordered cards; `shadow-md`/`shadow-xl` are reserved for elements that must visually detach from the content behind them — floating panels on maps (toolbar, legend, results), popovers, and the navigation FAB. No pronounced/"lifted" shadow appears anywhere in the system.

### Named rule
**The border-not-shadow rule.** Default surface separation is a border, not a shadow. Reserve `shadow-md` and above for elements that float above other content (map panels, popovers, FAB) and genuinely need to read as "above", not just "distinct".

## Shapes

`rounded-lg` (8px) is the dominant radius for cards, buttons, and form fields. `rounded-full` is reserved for circular/pill elements: the FAB, filter icon buttons, toggles, status badges. Small inline elements (legend swatches, table cells) use the base `rounded` (4px, Tailwind's default). No sharp-cornered surface (`rounded-none`) is used in the app.

## Components

### Buttons
- **Shape:** `rounded-md` (6px), `px-4 py-2`, `text-sm font-medium`.
- **Primary:** `bg-blue-600` / hover `bg-blue-700`, white text — the default action (save, submit, log in).
- **Secondary/neutral:** `bg-gray-600` / hover `bg-gray-700`, white text — a non-primary action next to a primary one (e.g. "My current location" next to "Save").
- **Sync/indigo:** `bg-indigo-600` / hover `bg-indigo-700` — specifically the found-caches sync action; reuses the meta-indigo role.
- **Destructive:** `bg-red-600` / hover `bg-red-700`, white text — irreversible actions ("Delete").
- **Disabled:** `disabled:opacity-50 disabled:cursor-not-allowed` on every variant.

### Stat Tiles
- **Shape:** `rounded-lg`, `p-3`, background tinted at the `-50` step (dark: `-950`).
- **Content:** a role-colored icon (`h-6 w-6`) next to a two-line stack — the number (`text-2xl font-bold`) above its label (`text-sm`).
- **Color:** always the role color matching the metric type (see Colors); never decorative.

### Cards / Containers
- **Corner style:** `rounded-lg`.
- **Background:** `bg-white` / dark `bg-gray-800`.
- **Border:** `border border-gray-200` / dark `border-gray-700`.
- **Shadow strategy:** none by default (see Elevation).
- **Inner padding:** `p-6` for a full card, `p-4` for a denser one.
- **Weight variants:** a page's primary, actionable sections (e.g. "My Location", "Sync") get the full card treatment above. Secondary, read-only sections (e.g. a read-only "Personal Information" block) drop background/border/padding entirely for a light "eyebrow" heading (`text-sm font-semibold uppercase tracking-wide`) — a card's visual weight should follow its section's actual complexity, not be uniform by default.

### Alert / Info Banners
- **Style:** `bg-{role}-50` / dark `bg-{role}-950`, `border border-{role}-200` / dark `border-{role}-900`, `rounded-lg`, `p-4`.
- **Content:** a leading role icon (`InformationCircleIcon` blue, `ExclamationTriangleIcon` amber/red, `CheckCircleIcon` green) followed by the message text in the matching `-700`/`800` (light) or `-300`/`400` (dark) shade.

### Loading Indicator
- **Shared component** (`components/ui/LoadingIndicator.vue`): a spinning `ArrowPathIcon` (`w-4 h-4 animate-spin`) next to a `text-sm text-gray-500`/dark `gray-400` label. A single visual style reused everywhere a page or panel is waiting on data; each page keeps its own outer container (full block, compact inline row, or a floating panel on a map) since that legitimately varies with layout, but the icon+label content itself never varies.

### Navigation (FAB + Drawer)
- **FAB:** a fixed circular menu trigger (`rounded-full`, `h-14 w-14`) in the bottom-right corner, `bg-white`/dark `bg-gray-800`, `border`, `shadow-lg`. Always shown above map content: every Leaflet map container carries CSS `isolation: isolate` so the library's internal z-indexes (up to 1000, for its zoom/attribution controls) can never appear above the app's chrome.
- **Drawer:** a full-screen panel (`fixed inset-0`) sharing the FAB's `z-50`, opaque `bg-white`/dark `bg-gray-900` background, opened/closed from the FAB.

### Form Inputs
- **Style:** `border border-gray-300` / dark `border-gray-600`, `rounded-md`, `bg-white` / dark `bg-gray-900`.
- **Focus:** `focus:ring-2 focus:ring-blue-500` (primary blue), no border color change.
- **Error:** border switches to `border-red-300`, a `text-sm text-red-600`/dark `red-400` message appears below the field.

## Do's and Don'ts

### Do:
- Give every color a named role (success / primary rate / secondary rate / meta counter / neutral / warning / danger) before using it — never assign a color to a tile "for variety".
- Pair a role color with a subject-specific icon on stat tiles; color alone never carries the full meaning.
- Run a real WCAG AA contrast check (4.5:1 text, 3:1 icons) on any new color pairing, using the project's actual Tailwind hex values, before shipping.
- Add `isolate` to any new Leaflet map container so its internal chrome can never render above the app's FAB/menu.
- Make information reachable by click/tap and keyboard focus, not just hover via a `title` attribute — a real accessibility gap found and fixed on the calendar day detail.
- Match a card's visual weight to its section's actual complexity; a 2-field read-only block and a multi-step form shouldn't look alike.

### Don't:
- Invent a new accent color for a single page — reuse an existing role, or explicitly name a new role if none fits.
- Use `gold` outside the completed-challenge trophy motif.
- Mix ellipsis styles ("..." vs "…") in UI text — the project standardized on "…" during the loading-feedback audit.
- Add a drop shadow to a resting card; prefer a border, a shadow only when the element must float above other content.
