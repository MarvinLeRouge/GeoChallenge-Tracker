# 🧭 GeoChallenge Tracker

> Un outil de suivi des challenges pour la communauté de géocacheurs, développé dans le cadre d’un projet de formation.

---

## 🚀 Objectif

Permettre aux géocacheurs passionnés de :
- Définir et suivre leurs challenges personnalisés
- Importer leurs trouvailles au format GPX
- Visualiser leur avancement sur carte (OpenStreetMap)
- Obtenir des projections de complétion via des statistiques

---

## 🧱 Stack technique

| Composant  | Techno utilisée         |
|------------|-------------------------|
| Backend    | FastAPI + MongoDB       |
| Frontend   | Vue.js + Vite + Nginx   |
| BDD        | MongoDB Atlas (externe) |
| DevOps     | Docker + docker-compose |
| Tests      | TDD (backend), E2E (frontend), fonctionnels |

---

## 🐳 Lancement local (via Docker)

> MongoDB **doit être accessible depuis l’extérieur** (par ex : MongoDB Atlas)

### 📁 Pré-requis
- Docker & Docker Compose installés
- Un fichier `.env` ou une variable d’environnement `MONGO_URI` disponible

### ▶️ Démarrage

```bash
docker compose up --build
```

modification test pour webhook discord 09h49