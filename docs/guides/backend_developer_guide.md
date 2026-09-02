[🇫🇷 Version française](backend_developer_guide.fr.md) | 🇬🇧 English version

---

# Backend Developer Guide - GeoChallenge Tracker

## Technologies

- **Framework**: FastAPI
- **Language**: Python 3.11
- **Database**: MongoDB (via Motor)
- **Validation**: Pydantic
- **Authentication**: JWT

## Route structure

Routes are organized by functional domain in `backend/app/api/routes/`:

- `auth.py`: authentication and user management
- `caches.py`: cache management (GPX import, search, etc.)
- `challenges.py`: challenge management
- `my_challenges.py`: the user's challenges
- `my_profile.py`: user profile
- `maintenance.py`: admin tools
- `zones.py`: administrative zones (`/api/zones`)

## Models and validation

Pydantic models are used for data validation:

- **DTOs**: in `backend/app/api/dto/` for API input/output objects
- **Domain Models**: in `backend/app/domain/models/` for pure business entities
- **Validation**: automatic via Pydantic through FastAPI

## Services

Business logic is organized in `backend/app/services/`:

- **Modular architecture**: each complex service has its own subfolder
- **Single responsibility**: each module has a clear responsibility
- **Explicit dependencies**: dependency injection via constructors

Main subfolders:

| Folder | Description |
|---------|-------------|
| `gpx_import/` | GPX import pipeline (parsing, validation, persistence) |
| `parsers/` | Multi-format GPX parsers |
| `zones/` | Administrative zone assignment and aggregations for the map |
| `providers/` | External integrations (Nominatim, elevation) |

## Database access

- **MongoDB**: async access via Motor
- **Collections**: abstracted via `get_collection()` in `db/`
- **Geo indexes**: used for spatial queries

## Error handling

- **HTTP errors**: FastAPI's `HTTPException`
- **Validation**: clear messages via Pydantic
- **Logging**: structured, with appropriate levels

## GPX imports

The GPX import system is highly modular:

- **Parsing**: in `services/parsers/` (MultiFormatGPXParser)
- **Processing**: in `services/gpx_import/` (multi-module architecture)
- **Modes**: `all` for every cache, `found` for the user's found caches

## Cache attribute administration

The admin route `/maintenance/upload-gpx` allows re-importing cache attributes:

- **Purpose**: re-import cache attributes from a GPX file
- **Access**: admin only
- **Use case**: correcting inconsistent cache attributes in the database
- **Implementation**: reuses the existing GPX import services
- **Caution**: requires admin rights, can significantly impact the database

## Security

- **JWT**: authentication tokens
- **Hashing**: passwords with argon2id via Passlib (bcrypt is kept only to verify existing hashes; accounts migrate to argon2id progressively on login)
- **Validation**: password strength in `core/security.py`

## Development

### Linting and formatting
```bash
cd backend
ruff check .
ruff format .
```

### Type checking
```bash
mypy .
```

### Tests
```bash
pytest tests/unit/ --cov=app --cov-report=term-missing -q
```

## Geographic data (choropleth map)

The choropleth map feature relies on GeoJSON files and a MongoDB collection
`administrative_zones`. The scripts below must be run **inside the backend container**
(or with the `ENV_FILE` variable pointing to a valid `.env`).

### Initial setup

```bash
# 1. Download missing GeoJSON files into data/admin/
python scripts/download_geo_data.py

# 2. Populate the administrative_zones collection (idempotent)
python scripts/seed_zones.py

# 3. Assign administrative zones to existing caches (one-shot, idempotent)
python scripts/assign_zones.py
```

### Script options

| Script | Useful options |
|--------|---------------|
| `download_geo_data.py` | none (idempotent, skips existing files) |
| `seed_zones.py` | none (upserts by `code`, safe to rerun) |
| `assign_zones.py` | `--country FR` (default), `--force` to re-assign already-assigned caches |

### Assignment algorithm (3 passes)

1. **Shapely STRtree** (exact), point-in-polygon via `app/services/zones/zone_utils.py`
2. **Nominatim** (batch, 1 req/s), reverse geocoding for points outside any polygon
   (simplified coastlines, peninsulas, borders)
3. **Nearest polygon**, final fallback within a 0.1° (~10 km) radius

New caches imported via GPX are automatically assigned (step 5b of the
`gpx_import_service.py` pipeline).

### Endpoints

| Method | Path | Description |
|---------|--------|-------------|
| `GET` | `/api/zones?country=FR&level=1` | List of zones with cache counters |
| `GET` | `/api/zones/{code}` | Zone detail with the first 10 caches |
| `GET` | `/api/zones/{code}/type-stats` | Per-type counters for a zone (13 types, zeros included) |
| `GET` | `/api/geo/FR/regions.geojson` | Region FeatureCollection (StaticFiles) |
| `GET` | `/api/geo/FR/departements.geojson` | Department FeatureCollection (StaticFiles) |

## Best practices

- **Type annotations**: mandatory everywhere
- **Docstrings**: for every public function
- **Naming**: snake_case for variables/functions
- **Validation**: systematic use of Pydantic
- **Error handling**: clear, relevant messages
