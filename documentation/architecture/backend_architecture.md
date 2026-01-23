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

### 4. Core Layer (`/core`)
- **Responsabilité** : Fonctionnalités transversales
- **Contenu** : Sécurité (JWT), middleware, logging, configuration

### 5. Database Layer (`/db`)
- **Responsabilité** : Accès à MongoDB
- **Technologies** : Motor (driver asynchrone)

## Principes architecturaux

- **Séparation des responsabilités** : Chaque couche a un rôle clair
- **Dépendances unidirectionnelles** : Les couches supérieures dépendent des inférieures, jamais l'inverse
- **Injection de dépendances** : Utilisation de FastAPI pour la DI
- **Validation** : Pydantic pour la validation des données
- **Gestion des erreurs** : Exceptions typées avec messages explicites