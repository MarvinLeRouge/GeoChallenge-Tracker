# Guide du développeur backend - GeoChallenge Tracker

## Technologies

- **Framework** : FastAPI
- **Langage** : Python 3.11
- **Base de données** : MongoDB (via Motor)
- **Validation** : Pydantic
- **Authentification** : JWT

## Structure des routes

Les routes sont organisées par domaines fonctionnels dans `backend/app/api/routes/` :

- `auth.py` : Authentification et gestion des utilisateurs
- `caches.py` : Gestion des caches (import GPX, recherche, etc.)
- `challenges.py` : Gestion des challenges
- `my_challenges.py` : Challenges de l'utilisateur
- `my_profile.py` : Profil utilisateur
- `maintenance.py` : Outils d'administration
- `zones.py` : Zones administratives — `/api/zones`

## Modèles et validation

Les modèles Pydantic sont utilisés pour la validation des données :

- **DTOs** : Dans `backend/app/api/dto/` pour les objets d'entrée/sortie API
- **Domain Models** : Dans `backend/app/domain/models/` pour les entités métier pures
- **Validation** : Automatique avec Pydantic via FastAPI

## Services

La logique métier est organisée dans `backend/app/services/` :

- **Architecture modulaire** : Chaque service complexe a son propre sous-dossier
- **Responsabilités uniques** : Chaque module a une responsabilité claire
- **Dépendances explicites** : Injection de dépendances via constructeurs

Sous-dossiers principaux :

| Dossier | Description |
|---------|-------------|
| `gpx_import/` | Pipeline d'import GPX (parsing, validation, persistance) |
| `parsers/` | Parsers GPX multi-formats |
| `zones/` | Assignation de zones administratives et agrégations pour la carte |
| `providers/` | Intégrations externes (Nominatim, élévation) |

## Accès à la base de données

- **MongoDB** : Accès asynchrone via Motor
- **Collections** : Abstraction via `get_collection()` dans `db/`
- **Index géographiques** : Utilisés pour les requêtes spatiales

## Gestion des erreurs

- **Erreurs HTTP** : Utilisation de `HTTPException` de FastAPI
- **Validation** : Messages clairs via Pydantic
- **Logging** : Structuré avec les niveaux appropriés

## Imports GPX

Le système d'import GPX est hautement modulaire :

- **Parsing** : Dans `services/parsers/` (MultiFormatGPXParser)
- **Traitement** : Dans `services/gpx_import/` (architecture en plusieurs modules)
- **Modes** : 'all' pour toutes les caches, 'found' pour les caches trouvées par l'utilisateur

## Administration des attributs de caches

La route d'administration `/admin/upload-gpx` permet de réimporter les attributs des caches :

- **Fonctionnalité** : Réimport des attributs des caches à partir d'un fichier GPX
- **Accès** : Réservé aux administrateurs
- **Utilité** : Correction des incohérences dans les attributs des caches dans la base de données
- **Implémentation** : Réutilise les services d'import GPX existants
- **Précautions** : Nécessite des droits d'administrateur, peut avoir un impact significatif sur la base de données

## Sécurité

- **JWT** : Tokens d'authentification
- **Hashage** : Mots de passe avec bcrypt via PassLib
- **Validation** : Force des mots de passe dans `core/security.py`

## Développement

### Linting et formatage
```bash
cd backend
uv run ruff check .
uv run ruff format .
```

### Typage
```bash
uv run mypy .
```

### Tests
```bash
uv run pytest
```

## Données géographiques (carte choroplèthe)

La fonctionnalité de carte choroplèthe repose sur des fichiers GeoJSON et une collection MongoDB
`administrative_zones`. Les scripts ci-dessous doivent être exécutés **à l'intérieur du conteneur backend**
(ou avec la variable `ENV_FILE` pointant vers un `.env` valide).

### Setup initial

```bash
# 1. Télécharger les fichiers GeoJSON manquants dans data/admin/
python scripts/download_geo_data.py

# 2. Peupler la collection administrative_zones (idempotent)
python scripts/seed_zones.py

# 3. Assigner les zones administratives aux caches existantes (one-shot, idempotent)
python scripts/assign_zones.py
```

### Options des scripts

| Script | Options utiles |
|--------|---------------|
| `download_geo_data.py` | aucune — idempotent, skip les fichiers existants |
| `seed_zones.py` | aucune — upsert par `code`, relançable sans effet |
| `assign_zones.py` | `--country FR` (défaut), `--force` pour réassigner les caches déjà assignées |

### Algorithme d'assignation (3 passes)

1. **Shapely STRtree** (exact) — point-in-polygon via `app/services/zones/zone_utils.py`
2. **Nominatim** (batch, 1 req/s) — reverse geocoding pour les points hors polygone
   (côtes simplifiées, presqu'îles, frontières)
3. **Polygone le plus proche** — fallback final dans un rayon de 0,1° (~10 km)

Les nouvelles caches importées via GPX sont automatiquement assignées (étape 5b du pipeline
`gpx_import_service.py`).

### Endpoints

| Méthode | Chemin | Description |
|---------|--------|-------------|
| `GET` | `/api/zones?country=FR&level=1` | Liste des zones avec compteurs de caches |
| `GET` | `/api/zones/{code}` | Détail d'une zone avec les 10 premières caches |
| `GET` | `/api/zones/{code}/type-stats` | Compteurs par type pour une zone (13 types, zéros inclus) |
| `GET` | `/api/geo/FR/regions.geojson` | FeatureCollection des régions (StaticFiles) |
| `GET` | `/api/geo/FR/departements.geojson` | FeatureCollection des départements (StaticFiles) |

## Bonnes pratiques

- **Annotations de type** : Obligatoires partout
- **Docstrings** : Pour toutes les fonctions publiques
- **Nommage** : snake_case pour les variables/fonctions
- **Validation** : Utilisation systématique de Pydantic
- **Gestion des erreurs** : Messages clairs et pertinents