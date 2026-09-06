[🇫🇷 Version française](architecture.fr.md) | 🇬🇧 English version

---

# Architecture - GeoChallenge Tracker

> Public technical reference. See [backend architecture](architecture/backend_architecture.md) and [frontend architecture](architecture/frontend_architecture.md) for implementation details.

## Overview

GeoChallenge Tracker is a two-component web application:

- **Backend** - FastAPI (Python), hexagonal layering (api / domain / services / core / db). Handles GPX import, challenge tracking, and administrative zone assignment for the choropleth map, backed by MongoDB.
- **Frontend** - Vue 3 (Composition API) + TypeScript SPA. Displays the cache map, matrix, calendar, and challenge dashboards, and consumes the backend REST API.

## Project structure

```
geochallenge-tracker/
├── backend/
│   └── app/
│       ├── api/        # Routes, DTOs
│       ├── domain/     # Business entities, base types
│       ├── services/   # Business logic (gpx_import, targets, zones, ...)
│       ├── core/       # Security, middleware, configuration
│       └── db/         # MongoDB access (Motor)
├── frontend/
│   └── src/
│       ├── pages/       # Route-level components
│       ├── composables/ # Reusable business logic
│       ├── components/  # Reusable UI/domain components
│       ├── store/       # Pinia stores
│       └── api/         # Backend API clients
└── docs/
    ├── architecture/    # backend/frontend architecture
    ├── adr/             # architecture decision records
    ├── api/             # API reference
    └── guides/          # developer/user guides
```

## Further reading

- [Backend architecture](architecture/backend_architecture.md)
- [Frontend architecture](architecture/frontend_architecture.md)
- [API reference](api/api_endpoints.md)
- [Architecture decision records](adr/README.md)
- [Developer guides](guides/)
- [Product context](product-context.md)
- [Operations](operations.md)
- [Design system](design-system.md)
