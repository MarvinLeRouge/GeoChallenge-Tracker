[🇫🇷 Version française](README.fr.md) | 🇬🇧 English version

---

# Test database management scripts

## Overview

This directory contains two scripts that prepare the test MongoDB database from the production database, used for integration tests.

> ⚠️ Despite their header comment saying `Usage: python scripts/...`, these scripts live in `backend/tests/utils/`, not `backend/scripts/` (which only contains the geographic data scripts, see [`backend/scripts/README.md`](../../scripts/README.md)).

---

## `duplicate_db_for_tests.py`

**Copies the production database to the test database.**

### Features
- Copies missing collections, indexes, and documents
- **Does not drop** existing collections: an already-populated test collection is left as-is (skipped), so the script only fills in gaps rather than starting from scratch
- Anonymizes users: `email` -> `test_{_id}@geochallenge.app`, `username` -> `test_{_id[:8]}` (`password_hash` is kept for auth tests)
- Forces creation of the `2dsphere` index on `caches.loc` if missing

### Usage
```bash
cd backend
python tests/utils/duplicate_db_for_tests.py
```

### Runtime
~30-60 seconds for 23 MB

### When to use it?
- Integration tests that need realistic data
- Performance tests
- Migration tests
- Before a full test session

---

## `copy_db_structure.py`

**Copies only the structure (collections + indexes) without the data.**

### Features
- Fully drops the test database before copying (`drop_database`)
- Creates all collections (empty)
- Copies all indexes
- Does not copy data

### Usage
```bash
cd backend
python tests/utils/copy_db_structure.py
```

### Runtime
~5-10 seconds

### When to use it?
- Integration tests that seed their own data
- Fast iterative development
- CI/CD (faster)

---

## Required configuration

### Environment variables

The scripts read the `.env` file at the project root (not in `backend/`):

```bash
# .env (project root)
MONGODB_USER=your_user
MONGODB_PASSWORD=your_password
MONGODB_URI_TPL=mongodb+srv://[[MONGODB_USER]]:[[MONGODB_PASSWORD]]@cluster.mongodb.net
MONGODB_DB=geoChallenge_Tracker
```

**Important**:
- The test DB is automatically named `{MONGODB_DB}_TEST`
- Both DBs (prod and test) live in the same cluster

⚠️ **Known bug**: `copy_db_structure.py` computes the project root with `Path(__file__).resolve().parents[2]`, which points to `backend/` (so `backend/.env`, currently empty) instead of the repo root used by `duplicate_db_for_tests.py` (`parents[3]`). The script then falls back to the hardcoded default credentials, which may be invalid. Expected fix: change to `parents[3]`.

### Prerequisites
- Python 3.11+
- `motor`, `python-dotenv` (already installed)
- Access to MongoDB Atlas

---

## Recommended workflow

### Locally (development)

```bash
cd backend
python tests/utils/duplicate_db_for_tests.py
pytest tests/integration/ -v
```

### In CI/CD

```bash
cd backend
python tests/utils/copy_db_structure.py   # structure only, faster
pytest tests/integration/ -v
```

---

## Comparison

| Criteria | `duplicate_db_for_tests.py` | `copy_db_structure.py` |
|----------|------------------------------|--------------------------|
| Data | Copied (if missing) | Not copied |
| Indexes | Yes | Yes |
| Test DB reset | No (skip per collection) | Yes (`drop_database`) |
| Time | 30-60s | 5-10s |
| Anonymization | Yes | Not applicable |
| Use case | Realistic tests | Fast tests |

---

## Troubleshooting

### Error: "Authentication failed"
Check your credentials in `.env` (project root). For `copy_db_structure.py`, see the known bug above.

### Error: "Database not found"
Check the DB name in `.env`. The test DB will be `{MONGODB_DB}_TEST`.

### The test DB has unexpected data
`duplicate_db_for_tests.py` does not reset already-populated collections. To start fresh, use `copy_db_structure.py` or drop manually:
```javascript
use geoChallenge_Tracker_TEST
db.dropDatabase()
```

### Error: "FileNotFoundError: No such file or directory: '.env'"
Run the script from the `backend/` folder (`cd backend`).
