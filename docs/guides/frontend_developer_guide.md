# Guide du développeur frontend - GeoChallenge Tracker

## Technologies

- **Framework** : Vue.js 3
- **Langage** : TypeScript
- **Styling** : Tailwind CSS + Flowbite
- **Cartographie** : Leaflet
- **Build** : Vite
- **Tests** : Vitest + Playwright

## Structure des pages

Les pages sont organisées par fonctionnalités dans `frontend/src/pages/` :

- `auth/` : Pages d'authentification
- `caches/` : Pages liées aux caches (import GPX, recherche, carte choroplèthe)
- `userChallenges/` : Pages liées aux challenges utilisateur (matrix, calendar, etc.)
- `misc/` : Pages diverses

### Pages caches notables

| Fichier | Route | Description |
|---------|-------|-------------|
| `ImportGpx.vue` | `/caches/import` | Import de fichiers GPX/ZIP |
| `ZonesMap.vue` | `/caches/zones` | Carte choroplèthe — caches trouvées par zone |
| `ZoneTypeStatsMap.vue` | `/caches/zone-types` | Carte choroplèthe — répartition par type par zone |
| `WithinBbox.vue` | `/caches/bbox` | Recherche dans une zone rectangulaire |
| `WithinRadius.vue` | `/caches/radius` | Recherche dans un rayon |

## Composables

La logique métier est extraite des composants dans des composables réutilisables :

- `useUserStats.ts` : Gestion des statistiques utilisateur
- `useMatrixData.ts` : Logique de la matrice D/T
- `useCalendarData.ts` : Logique du calendrier
- `useUserProfile.ts` : Gestion du profil utilisateur
- `useZones.ts` : Appels API pour les zones administratives — `fetchZones`, `fetchZoneDetail`, `fetchZoneTypeStats`

## Types

Tous les objets sont typés avec TypeScript dans `frontend/src/types/` :

- **Domaine** : Types correspondant aux modèles backend
- **Composants** : Types spécifiques aux composants
- **API** : Types pour les réponses/requêtes API

## Communication avec le backend

- **Client API** : Dans `frontend/src/api/http.ts`
- **Sérialisation des paramètres** : `paramsSerializer` personnalisé — les tableaux sont encodés sans bracket (`type=a&type=b`), compatible FastAPI qui n'accepte pas `type[]=a`
- **Refresh token** : intercepteur de réponse — les 401 déclenchent un refresh silencieux puis un retry de la requête originale

## Composants

- **Réutilisables** : Dans `frontend/src/components/`
- **Spécifiques** : Associés directement aux pages qui les utilisent
- **Cartographie** : Composants Leaflet dans `frontend/src/components/map/`

## Routage

- **Vue Router** : Configuration dans `frontend/src/router/index.ts`
- **Navigation** : Basée sur les noms de routes pour la maintenabilité

## Gestion d'état

- **Pinia** : Pour les données globales (ex: authStore)
- **Props/Events** : Pour la communication composant-parent/enfant
- **Composables** : Pour la logique métier partagée

## Bonnes pratiques

### Composition API
- Utilisation systématique de `<script setup>`
- Déclaration des props et emits explicites

### Typage
- TypeScript pour tous les composants
- Types stricts pour les props et les retours de fonctions

### Nommage
- PascalCase pour les composants Vue
- camelCase pour les variables/fonctions
- Utilisation de préfixes pour les composables (use*, get*, etc.)

### Structure
- Composables pour la logique métier
- Composants pour la présentation
- Pages pour l'orchestration

## Développement

### Lancement
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
# Tests unitaires
npm run test:unit

# Tests e2e
npm run test:e2e
```

## Dépendances importantes

- **Vue 3** : Framework principal
- **TypeScript** : Typage statique
- **Tailwind CSS** : Styling utility-first
- **Flowbite** : Composants UI
- **Leaflet** : Cartographie interactive
- **Pinia** : Gestion d'état
- **Vue Router** : Routage