[🇫🇷 Version française](frontend_developer_guide.fr.md) | 🇬🇧 English version

---

# Frontend Developer Guide - GeoChallenge Tracker

## Technologies

- **Framework**: Vue.js 3
- **Language**: TypeScript
- **Styling**: Tailwind CSS + Flowbite
- **Mapping**: Leaflet
- **Build**: Vite
- **Tests**: Vitest + Playwright

## Page structure

Pages are organized by feature in `frontend/src/pages/`:

- `auth/`: authentication pages
- `caches/`: cache-related pages (GPX import, search, choropleth map)
- `userChallenges/`: user challenge pages (matrix, calendar, etc.)
- `profile/`: user profile page
- `misc/`: miscellaneous pages

### Notable cache pages

| File | Route | Description |
|------|-------|-------------|
| `ImportGpx.vue` | `/caches/import` | GPX/ZIP file import |
| `ZonesMap.vue` | `/caches/zones` | Choropleth map, caches found by zone |
| `ZoneTypeStatsMap.vue` | `/caches/zone-types` | Choropleth map, breakdown by type per zone |
| `WithinBbox.vue` | `/caches/bbox` | Search within a rectangular area |
| `WithinRadius.vue` | `/caches/radius` | Search within a radius |

## Composables

Business logic is extracted from components into reusable composables:

- `useUserStats.ts`: user statistics management
- `useMatrixData.ts`: D/T matrix logic
- `useCalendarData.ts`: calendar logic
- `useUserProfile.ts`: user profile management
- `useZones.ts`: API calls for administrative zones (`fetchZones`, `fetchZoneDetail`, `fetchZoneTypeStats`)

## Types

All objects are typed with TypeScript in `frontend/src/types/`:

- **Domain**: types matching backend models
- **Components**: component-specific types
- **API**: types for API requests/responses

## Backend communication

- **API client**: in `frontend/src/api/http.ts`
- **Parameter serialization**: custom `paramsSerializer`, arrays are encoded without brackets (`type=a&type=b`), matching FastAPI which does not accept `type[]=a`
- **Refresh token**: response interceptor, 401s trigger a silent refresh then a retry of the original request

## Components

- **Reusable**: in `frontend/src/components/`
- **Specific**: tied directly to the pages that use them
- **Mapping**: Leaflet components in `frontend/src/components/map/`

## Routing

- **Vue Router**: configured in `frontend/src/router/index.ts`
- **Navigation**: based on route names for maintainability

## State management

- **Pinia**: for global data (e.g. authStore)
- **Props/Events**: for parent/child component communication
- **Composables**: for shared business logic

## Best practices

### Composition API
- Consistent use of `<script setup>`
- Explicit props and emits declarations

### Typing
- TypeScript for all components
- Strict types for props and function return values

### Naming
- PascalCase for Vue components
- camelCase for variables/functions
- Prefixes for composables (use*, get*, etc.)

### Structure
- Composables for business logic
- Components for presentation
- Pages for orchestration

## Development

### Running
```bash
npm install
npm run dev
```

### Linting
```bash
npm run lint
```

### Tests
```bash
# Unit tests
npm run test:unit

# E2E tests
npm run test:e2e
```

## Key dependencies

- **Vue 3**: main framework
- **TypeScript**: static typing
- **Tailwind CSS**: utility-first styling
- **Flowbite**: UI components
- **Leaflet**: interactive mapping
- **Pinia**: state management
- **Vue Router**: routing
