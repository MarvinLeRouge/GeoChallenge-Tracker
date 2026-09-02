🇫🇷 Version française | [🇬🇧 English version](api_endpoints.md)

---

# API Documentation - GeoChallenge Tracker

> Routes publiques (authentifiées ou non). Les routes admin-only (`/maintenance/*`, `/caches_elevation/*`, `/caches_geocoding/*`) ne sont pas documentées ici.

## Authentification (`/auth`)

### Inscription
- **URL** : `POST /auth/register`
- **Description** : Crée un nouveau compte utilisateur (non vérifié), envoie un email de vérification (code valide 24h)
- **Body** :
  ```json
  {
    "username": "string",
    "email": "string",
    "password": "string"
  }
  ```
- **Réponse** (201) : informations publiques du compte créé (`_id`, `username`, `email`, `role`)

### Connexion
- **URL** : `POST /auth/login`
- **Description** : Authentifie un utilisateur (accepte JSON `{identifier, password}` ou formulaire OAuth2). Le compte doit être vérifié.
- **Body** :
  ```json
  {
    "identifier": "string", // email ou username
    "password": "string"
  }
  ```
- **Réponse** : `{ "access_token": "string", "token_type": "bearer" }` (le refresh token n'est **pas** dans la réponse JSON, il est déposé dans un cookie `HttpOnly` : `refresh_token`, scope `/auth`, 7 jours)

### Actualisation du token
- **URL** : `POST /auth/refresh`
- **Description** : Génère un nouvel access token à partir du refresh token lu depuis le cookie `HttpOnly` (**aucun body requis**, le token n'est jamais envoyé par le client)
- **Réponse** : `{ "access_token": "string", "token_type": "bearer" }`

### Déconnexion
- **URL** : `POST /auth/logout`
- **Description** : Révoque le refresh token côté serveur (par son `jti`) et supprime le cookie. Idempotent, ne nécessite pas d'access token valide.
- **Réponse** : `{ "message": "Logged out" }`

### Vérification d'email
- **URL** : `GET /auth/verify-email?code=...` ou `POST /auth/verify-email`
- **Description** : Vérifie un code de confirmation reçu par email et active le compte. La variante `GET` (query param) est conservée pour compatibilité ; le frontend utilise la variante `POST` (body JSON) pour éviter qu'un code se retrouve dans les logs d'accès.
- **Body (POST)** : `{ "code": "string" }`
- **Réponse** : `{ "message": "Email verified" }`

### Renvoi du code de vérification
- **URL** : `POST /auth/resend-verification`
- **Description** : Régénère et renvoie un code de vérification si le compte existe et n'est pas encore activé (ne révèle jamais si le compte existe réellement)
- **Body** : `{ "identifier": "string" }` (username ou email)
- **Réponse** : message générique, identique que le compte existe ou non

## Gestion des caches (`/caches`)

### Import GPX
- **URL** : `POST /caches/upload-gpx`
- **Description** : Importe des caches depuis un fichier GPX ou ZIP (cgeo, Pocket Query), déclenche ensuite la création automatique des challenges et la synchronisation des UserChallenges
- **Paramètres de requête** :
  - `import_mode` : `all` (toutes les caches) ou `found` (mes trouvailles), défaut `all`
  - `source_type` : `auto`, `cgeo`, `pocket_query`, défaut `auto`
- **Body** : fichier multipart `file`
- **Réponse** : `{ "summary": {...}, "challenges_stats": {...}, "sync_stats": {...}, "progress_stats": {...} }` (le dernier champ seulement si `import_mode=found`)
- **Erreurs** : `400` fichier invalide, `413` fichier trop volumineux

### Recherche par filtres
- **URL** : `POST /caches/by-filter`
- **Description** : Recherche des caches avec filtres combinables (texte, type, taille, difficulté/terrain, pays/état, période de placement, etc.)
- **Body** : objet de filtres
- **Réponse** : liste paginée de caches

### Caches dans une zone
- **URL** : `GET /caches/within-bbox`
- **Paramètres de requête** : `min_lat`, `min_lon`, `max_lat`, `max_lon` *(obligatoires)*, `type_id`, `size_id` *(optionnels)*, `page`, `page_size` (max 200), `sort` (`-placed_at`, `-favorites`, `difficulty`, `terrain`), `compact` (bool)

- **URL** : `GET /caches/within-radius`
- **Paramètres de requête** : `lat`, `lon` *(obligatoires)*, `radius_km` (0.1–100, défaut 10), `type_id`, `size_id`, `page`, `page_size`, `compact`

### Récupération d'une cache
- **URL** : `GET /caches/{gc}`
- **Description** : Retourne une cache par son code GC. `404` si non trouvée.

- **URL** : `GET /caches/by-id/{id}`
- **Description** : Retourne une cache par son identifiant MongoDB (ObjectId).

## Zones administratives (`/zones`, `/geo`)

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

## Challenges (`/challenges`)

### (Re)création des challenges depuis les caches
- **URL** : `POST /challenges/refresh-from-caches`
- **Description** : Scanne les caches marquées `challenge` et crée/met à jour les documents challenge correspondants. Réservé aux administrateurs.
- **Body** : `{ "cache_ids": ["string", ...] }` *(optionnel, si absent scanne toute la collection)*

## Mes challenges (`/my/challenges`)

### Liste des challenges
- **URL** : `GET /my/challenges`
- **Paramètres de requête** : `status` *(optionnel)*, `page` (défaut 1), `page_size` (défaut 50, max 200)
- **Réponse** : liste paginée des UserChallenges

### Synchronisation
- **URL** : `POST /my/challenges/sync`
- **Description** : Crée les UserChallenges manquants pour l'utilisateur connecté

### Mise à jour en masse (batch)
- **URL** : `PATCH /my/challenges`
- **Description** : Met à jour statut/notes/`override_reason` de plusieurs UserChallenges en une fois (non transactionnel, best-effort, 200 items max)
- **Body** : tableau de `{ "uc_id": "string", "status"?: "string", "notes"?: "string", "override_reason"?: "string" }`
- **Réponse** : résultat détaillé par item (succès/erreur) + compteur de mises à jour

### Détail d'un challenge
- **URL** : `GET /my/challenges/{uc_id}`
- **Réponse** : `404` si le UserChallenge n'existe pas ou n'appartient pas à l'utilisateur

### Mise à jour unitaire
- **URL** : `PATCH /my/challenges/{uc_id}`
- **Body** : `{ "status"?: "pending"|"accepted"|"dismissed"|"completed", "notes"?: "string", "override_reason"?: "string" }`

### Calendar challenge
- **URL** : `GET /my/challenges/basics/calendar`
- **Description** : Vérifie la complétion du challenge calendrier (365 et 366 jours) pour l'utilisateur connecté
- **Paramètres de requête** : `cache_type`, `cache_size` *(optionnels, filtres par nom)*

### Matrix D/T
- **URL** : `GET /my/challenges/basics/matrix`
- **Description** : Vérifie la complétion de la matrice difficulté/terrain (9×9) pour l'utilisateur connecté
- **Paramètres de requête** : `cache_type`, `cache_size` *(optionnels, filtres par nom)*

## Tâches de challenge (`/my/challenges/{uc_id}/tasks`)

### Liste des tâches
- **URL** : `GET /my/challenges/{uc_id}/tasks`
- **Réponse** : liste ordonnée des tâches

### Remplacement des tâches
- **URL** : `PUT /my/challenges/{uc_id}/tasks`
- **Description** : Remplace l'intégralité des tâches (y compris leur ordre)
- **Body** : liste complète des tâches à appliquer

### Validation sans persistance
- **URL** : `POST /my/challenges/{uc_id}/tasks/validate`
- **Description** : Valide la cohérence d'une liste de tâches sans la sauvegarder

## Progression (`/my/challenges`)

### Historique de progression
- **URL** : `GET /my/challenges/{uc_id}/progress`
- **Réponse** : dernier snapshot et historique

### Évaluation de progression
- **URL** : `POST /my/challenges/{uc_id}/progress/evaluate`
- **Description** : Évalue et sauvegarde un nouveau snapshot de progression

### Premier snapshot en masse
- **URL** : `POST /my/challenges/new/progress`
- **Description** : Évalue un premier snapshot pour les UserChallenges `accepted` sans progression existante
- **Body** : `{ "include_pending"?: bool, "limit"?: int, "since"?: "datetime" }` *(optionnel)*

## Cibles de challenges (targets)

### Évaluation des cibles d'un challenge
- **URL** : `POST /my/challenges/{uc_id}/targets/evaluate`
- **Paramètres de requête** : `limit_per_task` (défaut 500), `hard_limit_total` (défaut 2000), `include_geo_filter` (bool), `lat`, `lon`, `radius_km`, `force` (bool)

### Liste des cibles d'un challenge
- **URL** : `GET /my/challenges/{uc_id}/targets`
- **Paramètres de requête** : `page`, `page_size` (max 200), `sort` (défaut `-score`)

### Cibles d'un challenge à proximité
- **URL** : `GET /my/challenges/{uc_id}/targets/nearby`
- **Description** : Comme ci-dessus, mais filtré par proximité (`lat`/`lon`, défaut : dernière position enregistrée de l'utilisateur)
- **Paramètres de requête** : `radius_km` (défaut 50), `lat`, `lon`, `page`, `page_size`, `sort` (défaut `distance`)

### Suppression des cibles d'un challenge
- **URL** : `DELETE /my/challenges/{uc_id}/targets`

### Liste de toutes mes cibles (tous challenges)
- **URL** : `GET /my/targets`
- **Paramètres de requête** : `status_filter` *(optionnel, ex. `accepted`)*, `page`, `page_size`, `sort` (défaut `-score`)

### Toutes mes cibles à proximité
- **URL** : `GET /my/targets/nearby`
- **Paramètres de requête** : `radius_km` (défaut 50), `lat`, `lon`, `page`, `page_size`, `status_filter`

### Statut de fraîcheur des cibles
- **URL** : `GET /my/targets/refresh-status`
- **Description** : Indique si des caches non trouvées ont été importées depuis la dernière évaluation des cibles (`needs_refresh`)

### Évaluation en masse
- **URL** : `POST /my/targets/evaluate-all`
- **Description** : Évalue les cibles pour tous les UserChallenges `accepted` de l'utilisateur

## Profil utilisateur (`/my/profile`)

### Récupération du profil
- **URL** : `GET /my/profile`
- **Réponse** : informations publiques du profil (`UserOut`)

> ⚠️ Il n'existe pas de route générique `PUT /my/profile` : les mises à jour passent par les sous-routes dédiées ci-dessous (`/location`, `/preferences`).

### Préférences
- **URL** : `PATCH /my/profile/preferences`
- **Description** : Met à jour partiellement les préférences (seuls les champs fournis sont modifiés)
- **Body** : `{ "language"?: "string", "dark_mode"?: bool }`

### Localisation
- **URL** : `GET /my/profile/location` (dernière position enregistrée)
- **URL** : `PUT /my/profile/location` (enregistre la position, via `position` en texte, ex. coordonnées DM, **ou** `lat`/`lon` numériques)

### Statistiques
- **URL** : `GET /my/profile/stats`
- **Réponse** : statistiques utilisateur de base

### Synchronisation des found caches
- **URL** : `POST /my/profile/found-caches/sync`
- **Description** : Envoie un fichier texte contenant des codes GC, traité comme la liste **complète et faisant foi** des caches trouvées : les caches absentes de la liste sont supprimées, les nouvelles sont ajoutées, les codes non reconnus sont signalés.
- **Body** : fichier multipart `file` (texte brut)
- **Réponse** : `{ "nb_provided": int, "nb_deleted": int, "nb_added": int, "nb_unknown_gc": int, "unknown_gc_codes": [...] }`

## Utilitaires

### Health check
- **URL** : `GET /health`
- **Description** : Vérifie la disponibilité de l'API et de ses dépendances (base de données, email). Retourne `503` si un service est dégradé.
- **Réponse** : `{ "status": "ok"|"degraded", "timestamp": "...", "version": "...", "checks": { "database": "ok", "email": "ok" } }`

### Version et informations
- **URL** : `GET /version`
- **Réponse** : `{ "version": "...", "environment": "...", "build_date": "..." }`

- **URL** : `GET /info`
- **Réponse** : nom de l'API, version, date de build, lien de documentation, URL de support

### Types et tailles de caches
- **URL** : `GET /cache_types` ou `GET /cache_sizes`
- **Réponse** : liste des types/tailles disponibles
