🇫🇷 Version française | [🇬🇧 English version](CONTRIBUTING.md)

---

# Contribuer à GeoChallenge Tracker

Merci de l'intérêt que vous portez au projet. Ce document couvre les prérequis, le workflow et les conventions à respecter lors de la soumission de modifications.

---

## Prérequis

- **Docker & Docker Compose** — pour exécuter la stack complète en local
- **Python 3.11+** — pour le développement backend sans Docker
- **Node.js 20+** — pour le développement frontend sans Docker
- **Git**

---

## Setup local

### Stack complète (Docker)

```bash
git clone https://github.com/MarvinLeRouge/GeoChallenge-Tracker.git
cd GeoChallenge-Tracker
cp .env.example .env  # remplir les valeurs requises
docker compose up --build
```

- Frontend : `http://localhost:5173`
- Backend : `http://localhost:8000`
- Doc API : `http://localhost:8000/docs`

### Backend seul

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend seul

```bash
cd frontend
npm install
npm run dev
```

---

## Lancer les tests

```bash
cd backend
pytest tests/unit/ --cov=app --cov-report=term-missing -q
```

---

## Workflow

1. **Forker** le dépôt
2. **Créer une branche** depuis `main` en respectant la convention de nommage ci-dessous
3. **Committer** les modifications en respectant la convention de commit ci-dessous
4. **Ouvrir une Pull Request** vers `main` avec une description claire de ce qui a été modifié et pourquoi
5. Attendre que la CI passe avant de demander une revue

---

## Nommage des branches

| Type | Pattern | Exemple |
|------|---------|---------|
| Fonctionnalité | `feat/description-courte` | `feat/gpx-auto-evaluate` |
| Correction | `fix/description-courte` | `fix/auth-redirect-loop` |
| Tests | `test/description-courte` | `test/progress-service` |
| Documentation | `docs/description-courte` | `docs/api-routes` |
| Chore / CI | `chore/description-courte` | `chore/codecov` |
| Refactoring | `refactor/description-courte` | `refactor/targets-pipeline` |

Utiliser le kebab-case en minuscules, sans caractères spéciaux.

---

## Convention de commit

Ce projet suit la spécification [Conventional Commits](https://www.conventionalcommits.org/).

```
<type>(<scope optionnel>): <résumé court>

Modified files:
- chemin/vers/fichier.ext — ce qui a été fait
```

**Types :** `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `style`, `perf`, `ci`

**Résumé :** mode impératif, minuscules, sans point final.

**Exemples :**

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

## Style de code

- **Backend :** vérifié par `ruff` (lint + format) et `mypy` (typage) — exécuter `ruff check backend/ && ruff format --check backend/ && mypy backend/` avant de pousser
- **Frontend :** vérifié par ESLint et TypeScript — exécuter `npm run lint && npm run typecheck` avant de pousser

La CI rejettera toute PR qui ne passe pas ces vérifications.

---

## Licence

En contribuant, vous acceptez que vos contributions soient publiées sous la [licence MIT](LICENSE).
