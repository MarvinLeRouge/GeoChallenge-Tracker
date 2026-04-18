# Architecture Backend - GeoChallenge Tracker

## Structure générale

L'architecture backend suit les principes de séparation des responsabilités et d'hexagonalité :

```
backend/app/
├── api/                # Couches d'entrée (routes, DTOs)
│   ├── dto/            # Objets de transfert de données
│   └── routes/         # Définition des routes FastAPI
├── domain/             # Modèles de domaine
│   ├── models/         # Entités métier
│   └── types/          # Types de base
├── services/           # Logique métier
├── core/               # Configuration, sécurité, utilitaires centraux
├── db/                 # Accès à la base de données
├── shared/             # Types/utilitaires partagés
└── main.py             # Point d'entrée de l'application
```

## Couches de l'application

### 1. API Layer (`/api`)
- **Responsabilité** : Interface avec le monde extérieur
- **Routes** : Définition des endpoints HTTP
- **DTOs** : Objets de transfert de données pour la sérialisation

### 2. Domain Layer (`/domain`)
- **Responsabilité** : Modèles métier purs sans dépendances externes
- **Entités** : Représentations des concepts métier (User, Cache, Challenge)

### 3. Service Layer (`/services`)
- **Responsabilité** : Logique métier complexe
- **Organisation** : Par fonctionnalités ou sous-systèmes
- **Exemples** :
  - `gpx_import/` : Import de fichiers GPX
  - `user_profile/` : Gestion du profil utilisateur
  - `targets/` : Gestion des cibles de challenge
  - `zones/` : Assignation et agrégation des zones administratives

### 4. Core Layer (`/core`)
- **Responsabilité** : Fonctionnalités transversales
- **Contenu** : Sécurité (JWT), middleware, logging, configuration

### 5. Database Layer (`/db`)
- **Responsabilité** : Accès à MongoDB
- **Technologies** : Motor (driver asynchrone)

## Fonctionnalités spécifiques

### Zones administratives (carte choroplèthe)

Le sous-système `services/zones/` assigne et expose des zones administratives pour la carte choroplèthe.

**Modules :**

| Module | Responsabilité |
|--------|---------------|
| `zone_utils.py` | Construction de l'index spatial Shapely (STRtree) et résolution point-dans-polygone |
| `zone_nominatim.py` | Reverse geocoding batch via l'API Nominatim (1 req/s) |
| `zone_assigner.py` | Pipeline d'assignation 3 passes : Shapely → Nominatim → polygone le plus proche |
| `zone_service.py` | Agrégations MongoDB pour les endpoints `/api/zones` |

**Pipeline d'assignation (3 passes) :**
1. **Shapely STRtree** — point-in-polygon exact, en mémoire, rapide
2. **Nominatim** — reverse geocoding pour les points hors polygone (côtes simplifiées, frontières)
3. **Polygone le plus proche** — fallback final à moins de 0,1° (~10 km), ignoré si Nominatim identifie un point étranger

**Collection MongoDB `administrative_zones` :**

Chaque document représente une zone (région ou département) :
- `code` (unique) : ex. `FR-38`
- `country_code` : `FR`
- `level` : `1` (région) ou `2` (département)
- `name` : nom lisible
- `geojson_file` : chemin relatif dans `data/admin/`, ex. `FR/departements.geojson`
- `feature_code` : code du feature dans le FeatureCollection
- `bbox` : `[lon_min, lat_min, lon_max, lat_max]`

**Champ `zones` sur les caches :**
```json
{ "country": "FR", "level1": "FR-84", "level2": "FR-38" }
```

**DTOs (`api/dto/zones.py`) :**

| Classe | Champs | Description |
|--------|--------|-------------|
| `ZoneListItem` | `code`, `name`, `cache_count` | Élément de liste pour la carte choroplèthe |
| `ZoneDetail` | `code`, `name`, `cache_count`, `caches` | Détail avec les 10 premières caches |
| `ZoneTypeStatItem` | `type_code`, `type_name`, `count` | Compteur pour un type donné |
| `ZoneTypeStatsResponse` | `code`, `name`, `type_counts` | Répartition par type pour une zone |

**Collection `cache_types` — champ `sort_order` :**

Chaque document possède un champ `sort_order` (entier 1–13) qui définit l'ordre d'affichage canonique GC.com : traditional → mystery → letterbox → multi → wig → earth → virtual → webcam → locationless → event-regular → event-cito → event-mega → event-giga. `zone_service.get_zone_type_stats` trie par ce champ.

**Endpoints exposés :**
- `GET /api/zones?country=FR&level=1[&type=traditional]`
- `GET /api/zones/{code}[?level=1&type=traditional]`
- `GET /api/zones/{code}/type-stats[?level=1]`
- `GET /api/geo/FR/regions.geojson` (StaticFiles)
- `GET /api/geo/FR/departements.geojson` (StaticFiles)

### Administration des attributs de caches
- **Route** : `/admin/upload-gpx` (POST)
- **Responsabilité** : Réimport des attributs des caches à partir d'un fichier GPX
- **Utilité** : Permet de corriger les incohérences dans les attributs des caches dans la base de données
- **Accès** : Réservé aux administrateurs
- **Intégration** : Utilise les services d'import GPX existants pour traiter les attributs

## Principes architecturaux

- **Séparation des responsabilités** : Chaque couche a un rôle clair
- **Dépendances unidirectionnelles** : Les couches supérieures dépendent des inférieures, jamais l'inverse
- **Injection de dépendances** : Utilisation de FastAPI pour la DI
- **Validation** : Pydantic pour la validation des données
- **Gestion des erreurs** : Exceptions typées avec messages explicites