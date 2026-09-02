[🇫🇷 Version française](frontend_architecture.fr.md) | 🇬🇧 English version

---

# Frontend Architecture - GeoChallenge Tracker

## Overall structure

The frontend architecture follows Vue 3 composition and modularity principles:

```
frontend/src/
├── api/                # API clients and request handling
├── app/                # Main application configuration
├── assets/             # Static assets (images, CSS)
├── components/         # Reusable components
│   ├── map/            # Mapping-related components
│   ├── ui/             # Shared generic UI components
│   └── userChallenges/ # Challenge-related components
├── composables/        # Reusable business logic
├── config/             # Application configuration
├── constants/          # Shared constants
├── pages/              # Application pages
│   ├── auth/           # Authentication pages
│   ├── caches/         # Cache-related pages
│   ├── misc/           # Miscellaneous pages
│   ├── profile/        # User profile pages
│   └── userChallenges/ # User challenge pages
├── router/             # Route configuration
├── store/              # Pinia stores (global state)
├── types/              # TypeScript type definitions
├── utils/              # Generic utilities
├── App.vue             # Root component
├── main.ts             # Entry point
└── style.css           # Global styles
```

## Application layers

### 1. Pages (`/pages`)
- **Responsibility**: top-level components matching routes
- **Structure**: organized by feature

### 2. Composables (`/composables`)
- **Responsibility**: reusable business logic
- **Examples**: `useUserStats.ts`, `useMatrixData.ts`, `useCalendarData.ts`, `useZones.ts`

### 3. Components (`/components`)
- **Responsibility**: reusable components
- **Types**:
  - Generic (UI)
  - Domain-specific (map, challenges)

### 4. Store (`/store`)
- **Responsibility**: global state management
- **Technology**: Pinia
- **Usage**: limited to shared data (e.g. authStore)

### 5. API (`/api`)
- **Responsibility**: communication with the backend
- **Clients**: wrapper around fetch/axios

## Specific features

### Choropleth map — Found by zone (`ZonesMap.vue`)

**Route**: `/caches/zones`

The `pages/caches/ZonesMap.vue` page displays an interactive Leaflet map colored by density of found caches per administrative zone.

**Behavior:**
- Level 0 → loads the region GeoJSON (`/api/geo/FR/regions.geojson`) and its counters (`/api/zones?country=FR&level=1`)
- Clicking a region → `fitBounds` zoom + loads departments (level 2)
- Clicking a department → popover with the total and the first 10 caches
- Type filter → only re-triggers the `/api/zones` calls, not the GeoJSON

**Dedicated composable**: `useZones.ts`
- `fetchZones(country, level, typeCode?)` → `GET /api/zones`
- `fetchZoneDetail(code, typeCode?, level?)` → `GET /api/zones/{code}[?level=N&type=T]`
- `fetchZoneTypeStats(code, level?)` → `GET /api/zones/{code}/type-stats[?level=N]`
- The `level` parameter is essential to disambiguate codes shared across levels (e.g. FR-93 = PACA region *and* Seine-Saint-Denis department)

### Type breakdown map — Types found by zone (`ZoneTypeStatsMap.vue`)

**Route**: `/caches/zone-types`

The `pages/caches/ZoneTypeStatsMap.vue` page displays the same choropleth map as `ZonesMap.vue` (colored by total cache density), but clicking a zone opens a popover listing the number of found caches for each of the 13 types — including types with zero.

**Behavior:**
- Region/department toolbar identical to `ZonesMap.vue` — no type filter (the breakdown always shows every type)
- Clicking a zone → calls `fetchZoneTypeStats(code, level)` → popover with a `[Type name | Count]` table
- Zero-count rows: `bg-red-50` background, italic, `XCircleIcon` prefix
- Counters formatted with `toLocaleString("fr-FR")` (thousands space separator)
- Clicking the map (outside a zone) → closes the popover via `leafletMap.on("click", closePopover)`
- Changing level → closes the popover and reloads the map

**Parameter serialization**:

`api/http.ts` uses a custom `paramsSerializer` so arrays are serialized without bracket notation (`type=a&type=b` instead of `type[]=a`), matching FastAPI's expectations.

## Architectural principles

- **Composition API**: used consistently
- **Strong typing**: TypeScript for safety
- **Separation of concerns**: logic in composables, presentation in components
- **Reusability**: composables for shared logic
- **State management**: Pinia for global data, props/events for local data
