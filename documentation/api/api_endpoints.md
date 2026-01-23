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

## Utilitaires

### Health check
- **URL** : `GET /ping`
- **Description** : Vérifie la disponibilité de l'API
- **Réponse** : Statut de santé

### Types et tailles de caches
- **URL** : `GET /cache_types` ou `GET /cache_sizes`
- **Description** : Récupère les types/tailles de caches disponibles
- **Réponse** : Liste des types/tailles