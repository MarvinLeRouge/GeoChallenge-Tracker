[🇫🇷 Version française](README.fr.md) | 🇬🇧 English version

---

# GeoChallenge Tracker - Frontend

Vue.js 3 SPA with TypeScript, Pinia, Vue Router, Tailwind CSS, and Leaflet maps.

## Local setup

The frontend has no separate `package.json`; it shares the one at the repository root, with Vite's `root` pointed at `frontend/`. Install dependencies from the repository root:

```bash
npm install
```

Create a `.env` file in `frontend/` (this is where Vite looks for it):

```env
VITE_API_URL=http://localhost:8000/api
```

Start the dev server, also from the repository root:

```bash
npm run dev
# Available at http://localhost:5173
```

## Available scripts

Run from the repository root.

| Command | Description |
|---------|-------------|
| `npm run dev` | Start dev server with hot-reload |
| `npm run build` | Production build |
| `npm run lint` | ESLint check |
| `npm run typecheck` | TypeScript type check |
| `npm run test:unit` | Run unit tests with Vitest |

## Project structure

```
frontend/src/
├── api/            # Axios instances and API call functions
├── app/            # App shell, layout, router
├── composables/    # Reusable composition functions
│   └── useZones.ts # Zones API composable (choropleth map)
├── pages/
│   ├── caches/
│   │   ├── ZonesMap.vue          # Choropleth map: found caches by zone
│   │   ├── ZoneTypeStatsMap.vue  # Choropleth map: per-type cache breakdown by zone
│   │   └── ...
│   └── ...
├── store/          # Pinia stores
├── types/
│   └── zones.ts    # ZoneListItem, ZoneDetail, ZoneTypeStatsResponse TypeScript types
└── components/     # Shared UI components
```
