[🇫🇷 Version française](backend_architecture.fr.md) | 🇬🇧 English version

---

# Backend Architecture - GeoChallenge Tracker

## Overall structure

The backend architecture follows separation-of-concerns and hexagonal principles:

```
backend/app/
├── api/                # Entry layer (routes, DTOs)
│   ├── dto/            # Data transfer objects
│   └── routes/         # FastAPI route definitions
├── domain/             # Domain models
│   ├── models/         # Business entities
│   └── types/          # Base types
├── services/           # Business logic
├── core/               # Configuration, security, central utilities
├── db/                 # Database access
├── shared/             # Shared types/utilities
└── main.py             # Application entry point
```

## Application layers

### 1. API Layer (`/api`)
- **Responsibility**: interface with the outside world
- **Routes**: HTTP endpoint definitions
- **DTOs**: data transfer objects for serialization

### 2. Domain Layer (`/domain`)
- **Responsibility**: pure business models with no external dependencies
- **Entities**: representations of business concepts (User, Cache, Challenge)

### 3. Service Layer (`/services`)
- **Responsibility**: complex business logic
- **Organization**: by feature or subsystem
- **Examples**:
  - `gpx_import/`: GPX file import
  - `user_profile_service.py`: user profile management
  - `targets/`: challenge target management
  - `zones/`: administrative zone assignment and aggregation

### 4. Core Layer (`/core`)
- **Responsibility**: cross-cutting concerns
- **Content**: security (JWT), middleware, logging, configuration

### 5. Database Layer (`/db`)
- **Responsibility**: MongoDB access
- **Technologies**: Motor (async driver)

## Specific features

### Administrative zones (choropleth map)

The `services/zones/` subsystem assigns and exposes administrative zones for the choropleth map.

**Modules:**

| Module | Responsibility |
|--------|---------------|
| `zone_utils.py` | Builds the Shapely spatial index (STRtree) and resolves point-in-polygon lookups |
| `zone_nominatim.py` | Batch reverse geocoding via the Nominatim API (1 req/s) |
| `zone_assigner.py` | 3-pass assignment pipeline: Shapely → Nominatim → nearest polygon |
| `zone_service.py` | MongoDB aggregations for the `/api/zones` endpoints |

**Assignment pipeline (3 passes):**
1. **Shapely STRtree** — exact, in-memory, fast point-in-polygon
2. **Nominatim** — reverse geocoding for points outside any polygon (simplified coastlines, borders)
3. **Nearest polygon** — final fallback within 0.1° (~10 km), skipped if Nominatim identifies a foreign point

**MongoDB collection `administrative_zones`:**

Each document represents a zone (region or department):
- `code` (unique): e.g. `FR-38`
- `country_code`: `FR`
- `level`: `1` (region) or `2` (department)
- `name`: human-readable name
- `geojson_file`: relative path under `data/admin/`, e.g. `FR/departements.geojson`
- `feature_code`: the feature's code within the FeatureCollection
- `bbox`: `[lon_min, lat_min, lon_max, lat_max]`

**`zones` field on caches:**
```json
{ "country": "FR", "level1": "FR-84", "level2": "FR-38" }
```

**DTOs (`api/dto/zones.py`):**

| Class | Fields | Description |
|--------|--------|-------------|
| `ZoneListItem` | `code`, `name`, `cache_count` | List item for the choropleth map |
| `ZoneDetail` | `code`, `name`, `cache_count`, `caches` | Detail with the first 10 caches |
| `ZoneTypeStatItem` | `type_code`, `type_name`, `count` | Counter for a given type |
| `ZoneTypeStatsResponse` | `code`, `name`, `type_counts` | Breakdown by type for a zone |

**`cache_types` collection — `sort_order` field:**

Each document has a `sort_order` field (integer 1-13) that defines the canonical GC.com display order: traditional → mystery → letterbox → multi → wig → earth → virtual → webcam → locationless → event-regular → event-cito → event-mega → event-giga. `zone_service.get_zone_type_stats` sorts by this field.

**Exposed endpoints:**
- `GET /api/zones?country=FR&level=1[&type=traditional]`
- `GET /api/zones/{code}[?level=1&type=traditional]`
- `GET /api/zones/{code}/type-stats[?level=1]`
- `GET /api/geo/FR/regions.geojson` (StaticFiles)
- `GET /api/geo/FR/departements.geojson` (StaticFiles)

### Cache attribute administration
- **Route**: `/maintenance/upload-gpx` (POST)
- **Responsibility**: re-import cache attributes from a GPX file
- **Purpose**: lets an admin correct inconsistent cache attributes in the database
- **Access**: admin only
- **Integration**: reuses the existing GPX import services to process attributes

## Architectural principles

- **Separation of concerns**: each layer has a clear role
- **Unidirectional dependencies**: upper layers depend on lower ones, never the reverse
- **Dependency injection**: uses FastAPI's DI
- **Validation**: Pydantic for data validation
- **Error handling**: typed exceptions with explicit messages
