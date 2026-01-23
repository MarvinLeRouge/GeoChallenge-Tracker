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

## Bonnes pratiques

- **Annotations de type** : Obligatoires partout
- **Docstrings** : Pour toutes les fonctions publiques
- **Nommage** : snake_case pour les variables/fonctions
- **Validation** : Utilisation systématique de Pydantic
- **Gestion des erreurs** : Messages clairs et pertinents