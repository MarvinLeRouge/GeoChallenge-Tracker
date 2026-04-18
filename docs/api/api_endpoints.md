# API Documentation - GeoChallenge Tracker

## Authentification

### Inscription
- **URL** : `POST /auth/register`
- **Description** : Crée un nouveau compte utilisateur
- **Body** : 
  ```json
  {
    "username": "string",
    "email": "string",
    "password": "string"
  }
  ```
- **Réponse** : Informations de l'utilisateur créé

### Connexion
- **URL** : `POST /auth/login`
- **Description** : Authentifie un utilisateur
- **Body** : 
  ```json
  {
    "identifier": "string", // email ou username
    "password": "string"
  }
  ```
- **Réponse** : Jetons JWT (access et refresh)

### Actualisation du token
- **URL** : `POST /auth/refresh`
- **Description** : Actualise le token d'accès avec le refresh token
- **Body** : 
  ```json
  {
    "refresh_token": "string"
  }
  ```

## Gestion des caches

### Import GPX
- **URL** : `POST /caches/upload-gpx`
- **Description** : Importe des caches depuis un fichier GPX/ZIP
- **Paramètres** : 
  - `import_mode` : "all" ou "found"
  - `source_type` : "auto", "cgeo", "pocket_query"
- **Body** : Fichier multipart `file`
- **Réponse** : Résumé des caches importées

### Recherche par filtres
- **URL** : `POST /caches/by-filter`
- **Description** : Recherche des caches avec filtres multiples
- **Body** : Objet de filtres (texte, type, difficulté, etc.)
- **Réponse** : Liste paginée de caches

### Caches dans une zone
- **URL** : `GET /caches/within-bbox` ou `GET /caches/within-radius`
- **Description** : Trouve les caches dans une zone géographique
- **Paramètres** : Coordonnées de la zone
- **Réponse** : Liste paginée de caches

## Challenges utilisateur

### Liste des challenges
- **URL** : `GET /my/challenges`
- **Description** : Récupère les challenges de l'utilisateur
- **Réponse** : Liste des UserChallenges

### Détail d'un challenge
- **URL** : `GET /my/challenges/{uc_id}`
- **Description** : Détail d'un challenge spécifique
- **Réponse** : Informations complètes du challenge

### Synchronisation
- **URL** : `POST /my/challenges/sync`
- **Description** : Synchronise les challenges manquants

## Profil utilisateur

### Récupération du profil
- **URL** : `GET /my/profile`
- **Description** : Récupère le profil de l'utilisateur connecté
- **Réponse** : Informations du profil

### Mise à jour du profil
- **URL** : `PUT /my/profile`
- **Description** : Met à jour le profil de l'utilisateur
- **Body** : Informations à modifier
- **Réponse** : Profil mis à jour

### Localisation
- **URL** : `GET /my/profile/location` ou `PUT /my/profile/location`
- **Description** : Gestion de la localisation de l'utilisateur

## Cibles de challenges

### Évaluation des cibles
- **URL** : `POST /my/challenges/{uc_id}/targets/evaluate`
- **Description** : Évalue les cibles pour un challenge
- **Réponse** : Liste des cibles identifiées

### Liste des cibles
- **URL** : `GET /my/challenges/{uc_id}/targets`
- **Description** : Récupère les cibles d'un challenge
- **Réponse** : Liste paginée des cibles

## Progression

### Historique de progression
- **URL** : `GET /my/challenges/{uc_id}/progress`
- **Description** : Récupère la progression d'un challenge
- **Réponse** : Dernier snapshot et historique

### Évaluation de progression
- **URL** : `POST /my/challenges/{uc_id}/progress/evaluate`
- **Description** : Évalue et sauvegarde un snapshot de progression

## Zones administratives

### Liste des zones avec compteurs

- **URL** : `GET /zones`
- **Description** : Retourne les zones administratives avec le nombre de caches trouvées par l'utilisateur connecté. Seules les zones où l'utilisateur a au moins une cache trouvée sont retournées.
- **Paramètres de requête** :
  - `country` *(obligatoire)* : code ISO pays, ex. `FR`
  - `level` *(obligatoire)* : niveau administratif — `1` (régions) ou `2` (départements)
  - `type` *(optionnel)* : filtre sur un type de cache, ex. `traditional`
- **Réponse** :
  ```json
  {
    "items": [
      { "code": "FR-38", "name": "Isère", "cache_count": 42 },
      { "code": "FR-84", "name": "Vaucluse", "cache_count": 7 }
    ]
  }
  ```

### Détail d'une zone

- **URL** : `GET /zones/{code}`
- **Description** : Retourne le détail d'une zone avec le total des caches trouvées et les 10 premières.
- **Paramètres de chemin** :
  - `code` : code de zone, ex. `FR-38`
- **Paramètres de requête** :
  - `level` *(optionnel)* : `1` ou `2` — désambiguïse les codes partagés entre niveaux (ex. FR-93 = PACA région *et* Seine-Saint-Denis département)
  - `type` *(optionnel)* : filtre sur un type de cache
- **Réponse** :
  ```json
  {
    "code": "FR-38",
    "name": "Isère",
    "cache_count": 42,
    "caches": [
      { "GC": "GC00001", "title": "Cache du Vercors", "type_code": "traditional", "difficulty": 2.0, "terrain": 3.0 }
    ]
  }
  ```

### Répartition par type d'une zone

- **URL** : `GET /zones/{code}/type-stats`
- **Description** : Retourne le nombre de caches trouvées par type pour une zone. Tous les types de caches sont toujours retournés (count=0 pour ceux sans correspondance), triés selon l'ordre canonique GC.com (`sort_order` dans la collection `cache_types`).
- **Paramètres de chemin** :
  - `code` : code de zone, ex. `FR-84`
- **Paramètres de requête** :
  - `level` *(optionnel)* : `1` ou `2` — désambiguïse les codes partagés entre niveaux
- **Réponse** :
  ```json
  {
    "code": "FR-84",
    "name": "Auvergne-Rhône-Alpes",
    "type_counts": [
      { "type_code": "traditional", "type_name": "Traditional Cache", "count": 42 },
      { "type_code": "mystery",     "type_name": "Mystery Cache",     "count": 7  },
      { "type_code": "letterbox",   "type_name": "Letterbox Hybrid",  "count": 0  }
    ]
  }
  ```
- **Erreurs** :
  - `404` si le code de zone est inconnu

### GeoJSON statiques

- **URL** : `GET /geo/FR/regions.geojson`
- **Description** : FeatureCollection GeoJSON des régions françaises. Servi par FastAPI StaticFiles.

- **URL** : `GET /geo/FR/departements.geojson`
- **Description** : FeatureCollection GeoJSON des départements français.

## Utilitaires

### Health check
- **URL** : `GET /ping`
- **Description** : Vérifie la disponibilité de l'API
- **Réponse** : Statut de santé

### Types et tailles de caches
- **URL** : `GET /cache_types` ou `GET /cache_sizes`
- **Description** : Récupère les types/tailles de caches disponibles
- **Réponse** : Liste des types/tailles