🇫🇷 Version française | [🇬🇧 English version](README.md)

---

# GeoChallenge Tracker — Backend

API REST FastAPI avec MongoDB (driver async Motor), authentification JWT et import GPX.

## Setup local (sans Docker)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

Créer un fichier `.env` dans `backend/` (ou définir les variables d'environnement) :

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

Démarrer le serveur de développement :

```bash
uvicorn app.main:app --reload --port 8000
```

La doc API est disponible sur `http://localhost:8000/docs`.

## Lancer les tests

```bash
pytest tests/unit/ --cov=app --cov-report=term-missing -q
```

## Structure du projet

```
backend/
├── app/
│   ├── api/routes/     # Gestionnaires de routes FastAPI
│   ├── core/           # Config, auth, dépendances
│   ├── db/             # Connexion MongoDB, indexes, seed
│   ├── models/         # Modèles Pydantic
│   └── services/       # Logique métier
└── tests/
    └── unit/           # Tests unitaires (miroir de app/)
```
