[🇫🇷 Version française](CONTRIBUTING.fr.md) | 🇬🇧 English version

---

# Contributing to GeoChallenge Tracker

Thank you for your interest in contributing. This document covers the prerequisites, workflow, and conventions to follow when submitting changes.

---

## Prerequisites

- **Docker & Docker Compose** — to run the full stack locally
- **Python 3.11+** — for backend development without Docker
- **Node.js 20+** — for frontend development without Docker
- **Git**

---

## Local setup

### Full stack (Docker)

```bash
git clone https://github.com/MarvinLeRouge/GeoChallenge-Tracker.git
cd GeoChallenge-Tracker
cp .env.example .env  # fill in the required values
docker compose up --build
```

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- API docs: `http://localhost:8000/docs`

### Backend only

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend only

```bash
cd frontend
npm install
npm run dev
```

---

## Running tests

```bash
cd backend
pytest tests/unit/ --cov=app --cov-report=term-missing -q
```

---

## Workflow

1. **Fork** the repository
2. **Create a branch** from `main` following the naming convention below
3. **Commit** your changes following the commit convention below
4. **Open a Pull Request** against `main` with a clear description of what was changed and why
5. Wait for CI to pass before requesting a review

---

## Branch naming

| Type | Pattern | Example |
|------|---------|---------|
| Feature | `feat/short-description` | `feat/gpx-auto-evaluate` |
| Bug fix | `fix/short-description` | `fix/auth-redirect-loop` |
| Tests | `test/short-description` | `test/progress-service` |
| Documentation | `docs/short-description` | `docs/api-routes` |
| Chore / CI | `chore/short-description` | `chore/codecov` |
| Refactor | `refactor/short-description` | `refactor/targets-pipeline` |

Use lowercase kebab-case. No special characters.

---

## Commit convention

This project follows [Conventional Commits](https://www.conventionalcommits.org/).

```
<type>(<optional scope>): <short summary>

Modified files:
- path/to/file.ext — what was done
```

**Types:** `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `style`, `perf`, `ci`

**Summary:** imperative mood, lowercase, no trailing period.

**Examples:**

```
feat(targets): add nearby mode with radius filter

Modified files:
- backend/app/api/routes/targets.py — add within-radius query param
- frontend/src/pages/Targets.vue — add radius toggle and circle overlay
```

```
fix(auth): redirect to login on 401 response

Modified files:
- frontend/src/api/http.ts — add Axios interceptor for 401 handling
```

---

## Code style

- **Backend:** enforced by `ruff` (lint + format) and `mypy` (type checking) — run `ruff check backend/ && ruff format --check backend/ && mypy backend/` before pushing
- **Frontend:** enforced by ESLint and TypeScript — run `npm run lint && npm run typecheck` before pushing

CI will reject any PR that fails these checks.

---

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
