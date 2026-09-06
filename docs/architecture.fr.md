🇫🇷 Version française | [🇬🇧 English version](architecture.md)

---

# Architecture - GeoChallenge Tracker

> Référence technique publique. Voir [architecture backend](architecture/backend_architecture.fr.md) et [architecture frontend](architecture/frontend_architecture.fr.md) pour les détails d'implémentation.

## Vue d'ensemble

GeoChallenge Tracker est une application web à deux composants :

- **Backend** - FastAPI (Python), architecture en couches hexagonale (api / domain / services / core / db). Gère l'import GPX, le suivi des challenges et l'assignation des zones administratives pour la carte choroplèthe, adossé à MongoDB.
- **Frontend** - SPA Vue 3 (Composition API) + TypeScript. Affiche la carte des caches, la matrice, le calendrier et les tableaux de bord de challenges, et consomme l'API REST du backend.

## Structure du projet

```
geochallenge-tracker/
├── backend/
│   └── app/
│       ├── api/        # Routes, DTOs
│       ├── domain/     # Entités métier, types de base
│       ├── services/   # Logique métier (gpx_import, targets, zones, ...)
│       ├── core/       # Sécurité, middleware, configuration
│       └── db/         # Accès MongoDB (Motor)
├── frontend/
│   └── src/
│       ├── pages/       # Composants de niveau route
│       ├── composables/ # Logique métier réutilisable
│       ├── components/  # Composants UI/domaine réutilisables
│       ├── store/       # Stores Pinia
│       └── api/         # Clients API du backend
└── docs/
    ├── architecture/    # architecture backend/frontend
    ├── adr/             # architecture decision records
    ├── api/             # référence API
    └── guides/          # guides développeur/utilisateur
```

## Pour aller plus loin

- [Architecture backend](architecture/backend_architecture.fr.md)
- [Architecture frontend](architecture/frontend_architecture.fr.md)
- [Référence API](api/api_endpoints.fr.md)
- [Registre des décisions d'architecture](adr/README.md)
- [Guides développeur](guides/)
- [Contexte produit](product-context.fr.md)
- [Opérations](operations.fr.md)
- [Design system](design-system.fr.md)
