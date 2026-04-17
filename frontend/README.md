[🇫🇷 Version française](README.fr.md) | 🇬🇧 English version

---

# GeoChallenge Tracker — Frontend

Vue.js 3 SPA with TypeScript, Pinia, Vue Router, Tailwind CSS, and Leaflet maps.

## Local setup

```bash
cd frontend
npm install
```

Create a `.env` file in `frontend/`:

```env
VITE_API_URL=http://localhost:8000/api
```

Start the dev server:

```bash
npm run dev
# Available at http://localhost:5173
```

## Available scripts

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
│   │   ├── ZonesMap.vue   # Choropleth map — found caches by zone
│   │   └── ...
│   └── ...
├── stores/         # Pinia stores
├── types/
│   └── zones.ts    # ZoneListItem, ZoneDetail TypeScript types
└── components/     # Shared UI components
```
