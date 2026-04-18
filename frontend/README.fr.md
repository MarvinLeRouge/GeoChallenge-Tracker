🇫🇷 Version française | [🇬🇧 English version](README.md)

---

# GeoChallenge Tracker — Frontend

SPA Vue.js 3 avec TypeScript, Pinia, Vue Router, Tailwind CSS et cartes Leaflet.

## Setup local

```bash
cd frontend
npm install
```

Créer un fichier `.env` dans `frontend/` :

```env
VITE_API_URL=http://localhost:8000/api
```

Démarrer le serveur de développement :

```bash
npm run dev
# Accessible sur http://localhost:5173
```

## Scripts disponibles

| Commande | Description |
|----------|-------------|
| `npm run dev` | Serveur de développement avec hot-reload |
| `npm run build` | Build de production |
| `npm run lint` | Vérification ESLint |
| `npm run typecheck` | Vérification des types TypeScript |
| `npm run test:unit` | Tests unitaires avec Vitest |

## Structure du projet

```
frontend/src/
├── api/            # Instances Axios et fonctions d'appel API
├── app/            # Shell de l'app, layout, router
├── composables/    # Fonctions de composition réutilisables
│   └── useZones.ts # Composable API zones (carte choroplèthe)
├── pages/
│   ├── caches/
│   │   ├── ZonesMap.vue          # Carte choroplèthe — caches trouvées par zone
│   │   ├── ZoneTypeStatsMap.vue  # Carte choroplèthe — répartition par type par zone
│   │   └── ...
│   └── ...
├── stores/         # Stores Pinia
├── types/
│   └── zones.ts    # Types TypeScript ZoneListItem, ZoneDetail, ZoneTypeStatsResponse
└── components/     # Composants UI partagés
```
