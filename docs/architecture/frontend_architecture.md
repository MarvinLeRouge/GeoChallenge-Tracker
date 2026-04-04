# Architecture Frontend - GeoChallenge Tracker

## Structure générale

L'architecture frontend suit les principes de composition Vue 3 et de modularité :

```
frontend/src/
├── api/                # Clients API et gestion des requêtes
├── app/                # Configuration principale de l'application
├── assets/             # Ressources statiques (images, CSS)
├── components/         # Composants réutilisables
│   ├── map/            # Composants liés à la cartographie
│   └── userChallenges/ # Composants liés aux challenges
├── composables/        # Logique métier réutilisable
├── config/             # Configuration de l'application
├── pages/              # Pages de l'application
│   ├── auth/           # Pages d'authentification
│   ├── caches/         # Pages liées aux caches
│   ├── misc/           # Pages diverses
│   └── userChallenges/ # Pages liées aux challenges utilisateur
├── router/             # Configuration des routes
├── store/              # Stores Pinia (état global)
├── types/              # Définitions TypeScript
├── utils/              # Utilitaires génériques
├── App.vue             # Composant racine
├── main.ts             # Point d'entrée
└── style.css           # Styles globaux
```

## Couches de l'application

### 1. Pages (`/pages`)
- **Responsabilité** : Composants de premier niveau correspondant aux routes
- **Structure** : Organisées par fonctionnalités

### 2. Composables (`/composables`)
- **Responsabilité** : Logique métier réutilisable
- **Exemples** : `useUserStats.ts`, `useMatrixData.ts`, `useCalendarData.ts`

### 3. Components (`/components`)
- **Responsabilité** : Composants réutilisables
- **Types** : 
  - Génériques (UI)
  - Spécifiques à des domaines (carte, challenges)

### 4. Store (`/store`)
- **Responsabilité** : Gestion de l'état global
- **Technologie** : Pinia
- **Usage** : Limité aux données partagées (ex: authStore)

### 5. API (`/api`)
- **Responsabilité** : Communication avec le backend
- **Clients** : Wrapper autour de fetch/axios

## Principes architecturaux

- **Composition API** : Utilisation systématique
- **Typage fort** : TypeScript pour la sûreté
- **Séparation des préoccupations** : Logique dans composables, présentation dans composants
- **Réutilisabilité** : Composables pour logique partagée
- **State management** : Pinia pour données globales, props/events pour locales