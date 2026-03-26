[🇫🇷 Version française](README.fr.md) | 🇬🇧 English version

---

# GeoChallenge Tracker — Backend

FastAPI REST API with MongoDB (Motor async driver), JWT authentication, and GPX import.

## Local setup (without Docker)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

Create a `.env` file in `backend/` (or set environment variables):

```env
MONGODB_USER=
MONGODB_PASSWORD=
MONGODB_URI_TPL=mongodb://localhost:27017
MONGODB_DB=geochallenge
JWT_SECRET_KEY=change-me
ADMIN_USERNAME=admin
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=change-me
MAIL_FROM=noreply@example.com
SMTP_HOST=localhost
SMTP_PORT=25
SMTP_USERNAME=
SMTP_PASSWORD=
ELEVATION_ENABLED=false
ENVIRONMENT=development
```

Start the dev server:

```bash
uvicorn app.main:app --reload --port 8000
```

API docs available at `http://localhost:8000/docs`.

## Running tests

```bash
pytest tests/unit/ --cov=app --cov-report=term-missing -q
```

## Project structure

```
backend/
├── app/
│   ├── api/routes/     # FastAPI route handlers
│   ├── core/           # Config, auth, dependencies
│   ├── db/             # MongoDB connection, indexes, seed
│   ├── models/         # Pydantic models
│   └── services/       # Business logic
└── tests/
    └── unit/           # Unit tests (mirrors app/ structure)
```
