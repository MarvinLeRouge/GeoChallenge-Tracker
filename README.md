# 🧭 GeoChallenge Tracker

[Go to English version](#english-version) | [Aller à la version française](#french-version)

---

## Navigation
- [Version française](#french-version)
- [English version](#english-version)

---

<a id="french-version"></a>
# Version Française

## 🚀 Présentation

GeoChallenge Tracker est une application web complète conçue pour les passionnés de géocaching. Elle permet de suivre les challenges personnalisés, d'importer les trouvailles au format GPX, de visualiser la progression sur carte et d'obtenir des statistiques sur la complétion des défis.

L'application permet aux géocacheurs passionnés de :
- Définir et suivre leurs challenges personnalisés
- Importer leurs trouvailles au format GPX
- Visualiser leur avancement sur carte (OpenStreetMap)
- Obtenir des projections de complétion via des statistiques
- Suivre les challenges classiques comme la matrice D/T et le calendrier
- Identifier les caches cibles pour atteindre leurs objectifs

---

## 🧱 Technologies utilisées

### Backend
- **FastAPI** - Framework web Python moderne et rapide
- **MongoDB** - Base de données NoSQL pour le stockage des données
- **Motor** - Pilote asynchrone Python pour MongoDB
- **JWT** - Authentication par jetons web JSON
- **Pydantic** - Validation de données et gestion des paramètres
- **Python-Multipart** - Gestion du multipart form data pour les uploads
- **PassLib** - Hashage sécurisé des mots de passe
- **Bcrypt** - Algorithme de hashage pour les mots de passe

### Frontend
- **Vue.js 3** - Framework JavaScript pour les interfaces utilisateur
- **TypeScript** - Superset typé de JavaScript
- **Vue Router** - Routeur officiel pour Vue.js
- **Pinia** - Solution de gestion d'état pour Vue.js
- **Tailwind CSS** - Framework CSS utilitaire
- **Flowbite** - Composants UI open-source basés sur Tailwind
- **Flowbite Vue** - Composants Vue.js basés sur Flowbite
- **Leaflet** - Bibliothèque JavaScript pour les cartes interactives
- **Leaflet Draw** - Outils de dessin interactifs pour les cartes Leaflet
- **Heroicons Vue** - Icônes SVG élégantes
- **Lucide Vue** - Icônes SVG légères
- **Vite** - Environnement de développement rapide
- **Vitest** - Exécuteur de tests rapide pour Vue et Vite
- **Playwright** - Framework de test de bout en bout

### DevOps & Déploiement
- **Docker** - Plateforme de conteneurisation
- **Docker Compose** - Outil pour définir et exécuter des applications multi-conteneurs
- **Nginx** - Serveur web utilisé comme reverse proxy
- **MongoDB Atlas** - Service cloud MongoDB (externement hébergé)

### Tests
- **Pytest** - Framework de test pour Python (backend)
- **Vitest** - Exécuteur de tests rapide pour Vite et Vue.js (frontend)
- **Playwright** - Framework de test de bout en bout pour frontend
- **@vitest/coverage-v8** - Outil de couverture de code pour Vitest
- **JSDOM** - Implémentation JavaScript des standards du web pour les tests

---

## 🎯 Fonctionnalités

### Authentification & Gestion des utilisateurs
- Système d'inscription avec validation de mot de passe
- Authentification sécurisée avec JWT
- Vérification d'email avec codes de confirmation
- Renvoi d'email de vérification
- Gestion du profil utilisateur

### Gestion des caches
- Import de fichiers GPX/ZIP provenant de cgeo et Pocket Queries
- Recherche avancée de caches avec filtres multiples (type, difficulté, terrain, attributs, dates, etc.)
- Recherche géographique (dans une bounding box ou dans un rayon autour d'un point)
- Visualisation des caches sur carte interactive
- Récupération de caches par code GC ou par identifiant

### Système de challenges
- Synchronisation automatique des challenges utilisateurs
- Suivi de l'état des challenges (pending, accepted, dismissed, completed)
- Mise à jour par lot des challenges
- Détail des informations pour chaque challenge
- Évaluation et persistance des cibles pour les challenges

### Challenges classiques
- Vérification de la matrice D/T (9x9 combinaisons difficulté/terrain)
- Vérification du challenge calendrier (365/366 jours)
- Support des filtres par type et taille de cache
- Visualisation interactive des résultats

### Suivi de progression
- Évaluation en temps réel de la progression
- Historique des snapshots de progression
- Calcul automatique de la première progression pour les nouveaux challenges
- Visualisation de l'évolution de la progression

### Identification des cibles
- Évaluation et persistance des cibles pour chaque challenge
- Liste paginée des cibles avec tri possible
- Recherche des cibles à proximité d'un point
- Suppression des cibles pour un challenge spécifique

### Gestion des tâches de challenge
- Visualisation des tâches d'un challenge
- Remplacement de l'ensemble des tâches avec maintien de l'ordre
- Validation des tâches sans persistance

### Maintenance et outils
- Analyse et nettoyage des enregistrements orphelins
- Sauvegarde complète de la base de données
- Restauration depuis un fichier de sauvegarde
- Backfill des données d'altitude pour les caches (admin seulement)

---

## 📡 API Routes

### Authentification (`/auth`)
- `POST /auth/register` - Enregistrement d'un nouvel utilisateur
- `POST /auth/login` - Connexion d'un utilisateur
- `POST /auth/refresh` - Renouvellement du token d'accès
- `GET /auth/verify-email` - Vérification d'email par code
- `POST /auth/verify-email` - Vérification d'email via POST
- `POST /auth/resend-verification` - Renvoi du code de vérification

### Base (`/`)
- `GET /cache_types` - Récupération de tous les types de cache
- `GET /cache_sizes` - Récupération de toutes les tailles de cache
- `GET /ping` - Vérification de santé de l'API

### Caches (`/caches`)
- `POST /caches/upload-gpx` - Import de caches depuis fichier GPX/ZIP
- `POST /caches/by-filter` - Recherche de caches par filtres
- `GET /caches/within-bbox` - Caches dans une bounding box
- `GET /caches/within-radius` - Caches autour d'un point (rayon)
- `GET /caches/{gc}` - Récupération d'une cache par code GC
- `GET /caches/by-id/{id}` - Récupération d'une cache par identifiant MongoDB

### Challenges (`/challenges`)
- `POST /challenges/refresh-from-caches` - Recréation des challenges à partir des caches

### Mes challenges (`/my/challenges`)
- `POST /my/challenges/sync` - Synchronisation des UserChallenges manquants
- `GET /my/challenges` - Liste des UserChallenges
- `PATCH /my/challenges` - Patch en lot de plusieurs UserChallenges
- `GET /my/challenges/{uc_id}` - Détail d'un UserChallenge
- `PATCH /my/challenges/{uc_id}` - Modification d'un UserChallenge
- `GET /my/challenges/basics/calendar` - Vérification du challenge calendrier
- `GET /my/challenges/basics/matrix` - Vérification du challenge matrice D/T

### Mes tâches de challenge (`/my/challenges/{uc_id}/tasks`)
- `GET /my/challenges/{uc_id}/tasks` - Liste des tâches d'un UserChallenge
- `PUT /my/challenges/{uc_id}/tasks` - Remplacement des tâches d'un UserChallenge
- `POST /my/challenges/{uc_id}/tasks/validate` - Validation des tâches sans persistance

### Mon profil (`/my/profile`)
- `PUT /my/profile/location` - Enregistrement de la localisation
- `GET /my/profile/location` - Récupération de la localisation
- `GET /my/profile` - Récupération du profil utilisateur

### Mes cibles (`/my`)
- `POST /my/challenges/{uc_id}/targets/evaluate` - Évaluation des cibles d'un UserChallenge
- `GET /my/challenges/{uc_id}/targets` - Liste des cibles d'un UserChallenge
- `GET /my/challenges/{uc_id}/targets/nearby` - Liste des cibles proches d'un UserChallenge
- `GET /my/targets` - Liste de toutes les cibles
- `GET /my/targets/nearby` - Liste des cibles proches de tous les challenges
- `DELETE /my/challenges/{uc_id}/targets` - Suppression des cibles d'un UserChallenge

### Mon avancement (`/my/challenges`)
- `GET /my/challenges/{uc_id}/progress` - Récupération du dernier snapshot et historique
- `POST /my/challenges/{uc_id}/progress/evaluate` - Évaluation et sauvegarde d'un snapshot
- `POST /my/challenges/new/progress` - Évaluation de la première progression

### Élévation des caches (`/caches_elevation`)
- `POST /caches_elevation/caches/elevation/backfill` - Backfill de l'altitude manquante (admin)

### Maintenance (`/maintenance`) <span style="color:white; background-color:#cc0000">&nbsp;Réservé admin&nbsp;</span>
- `GET /maintenance/db_cleanup` - Analyse de la base de données pour orphelins
- `DELETE /maintenance/db_cleanup` - Exécution du nettoyage des orphelins
- `GET /maintenance/db_cleanup/backups` - Liste des sauvegardes de nettoyage
- `GET /maintenance/backups/{filepath:path}` - Téléchargement d'un fichier de sauvegarde
- `POST /maintenance/db_full_backup` - Création d'une sauvegarde complète
- `POST /maintenance/db_full_restore/{filename}` - Restauration depuis une sauvegarde
- `GET /maintenance/db_backups` - Liste de tous les fichiers de sauvegarde
- `POST /maintenance/upload-gpx` - Réimport des attributs des caches à partir d'un fichier GPX

---

## 🐳 Installation & Lancement

> MongoDB **doit être accessible depuis l’extérieur** (par ex : MongoDB Atlas)

### 📁 Pré-requis
- Docker & Docker Compose installés
- Node.js (pour développement frontend)
- Un fichier `.env` ou une variable d'environnement `MONGO_URI` disponible

### ▶️ Lancement en mode développement

```bash
# Construire et lancer les services
docker compose up --build

# Le frontend est accessible à http://localhost:5173
# Le backend est accessible à http://localhost:8000
```

### 🔧 Configuration

Créez un fichier `.env` à la racine du projet avec les variables suivantes :

```env
# Backend
MONGO_URI=your_mongodb_connection_string
JWT_SECRET_KEY=your_secret_key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_MINUTES=43200

# Frontend (dans frontend/.env)
VITE_API_URL=http://localhost:8000/api
```

### 🧪 Lancement des tests

```bash
# Backend tests
cd backend
poetry run pytest

# Frontend tests
cd frontend
npm run test:unit
npm run test:e2e
```

---

## 🔨 Build & Déploiement

### Build avec date de commit

Le script `build.sh` met à jour automatiquement la date de build dans `.env` en utilisant la date du dernier commit Git.

```bash
# Mettre à jour BUILD_DATE et rebuilder l'image backend
./build.sh

# Puis lancer l'application
docker-compose up
```

**Note** : La date de build est affichée dans l'endpoint `/version` :

```bash
curl http://localhost:8000/version

# Réponse :
{
  "version": "0.1.0",
  "environment": "development",
  "build_date": "2026-02-27T18:42:15+01:00"
}
```

### Workflow recommandé

1. Développer et tester vos modifications
2. Committer vos changements
3. Lancer `./build.sh` pour mettre à jour la build date
4. Tester l'application
5. Push sur GitHub

**TODO (Phase 4)** : Automatiser la build date via GitHub Actions lors du déploiement en production.

---

## 🤝 Contribution

Les contributions sont les bienvenues ! Voici comment vous pouvez contribuer :

1. Fork du projet
2. Création d'une branche pour votre fonctionnalité (`git checkout -b feature/AmazingFeature`)
3. Commit de vos changements (`git commit -m 'Add some AmazingFeature'`)
4. Push vers la branche (`git push origin feature/AmazingFeature`)
5. Ouverture d'une Pull Request

### Convention de nommage des branches
- Backend features : `backend/feat/nom-fonctionnalite`
- Frontend features : `frontend/feat/nom-fonctionnalite`
- Corrections : `fix/nom-correction`

---

## 📋 Licence

Ce projet est sous licence MIT - voir le fichier [LICENSE](LICENSE) pour plus de détails.

---

***


<a id="english-version"></a>
# English Version

## 🚀 Overview

GeoChallenge Tracker is a comprehensive web application designed for geocaching enthusiasts. It allows tracking custom challenges, importing finds from GPX files, visualizing progress on maps, and getting completion statistics for challenges.

The application enables passionate geocachers to:
- Define and track their custom challenges
- Import their finds in GPX format
- Visualize their progress on maps (OpenStreetMap)
- Get completion projections through statistics
- Track classic challenges such as the D/T matrix and calendar challenges
- Identify target caches to reach their goals

---

## 🧱 Technologies Used

### Backend
- **FastAPI** - Modern, fast Python web framework
- **MongoDB** - NoSQL database for data storage
- **Motor** - Asynchronous Python driver for MongoDB
- **JWT** - JSON Web Token authentication
- **Pydantic** - Data validation and configuration management
- **Python-Multipart** - Multipart form data handling for uploads
- **PassLib** - Secure password hashing
- **Bcrypt** - Password hashing algorithm

### Frontend
- **Vue.js 3** - JavaScript framework for user interfaces
- **TypeScript** - Typed superset of JavaScript
- **Vue Router** - Official router for Vue.js
- **Pinia** - State management solution for Vue.js
- **Tailwind CSS** - Utility-first CSS framework
- **Flowbite** - Open-source UI components based on Tailwind
- **Flowbite Vue** - Vue.js components based on Flowbite
- **Leaflet** - JavaScript library for interactive maps
- **Leaflet Draw** - Interactive drawing tools for Leaflet maps
- **Heroicons Vue** - Elegant SVG icons
- **Lucide Vue** - Lightweight SVG icons
- **Vite** - Development environment
- **Vitest** - Fast test runner for Vue and Vite
- **Playwright** - End-to-end testing framework

### DevOps & Deployment
- **Docker** - Containerization platform
- **Docker Compose** - Tool to define and run multi-container applications
- **Nginx** - Web server used as reverse proxy
- **MongoDB Atlas** - Cloud MongoDB service (externally hosted)

### Testing
- **Pytest** - Testing framework for Python (backend)
- **Vitest** - Fast test runner for Vite and Vue.js (frontend)
- **Playwright** - End-to-end testing framework for frontend
- **@vitest/coverage-v8** - Code coverage tool for Vitest
- **JSDOM** - JavaScript implementation of web standards for testing

---

## 🎯 Features

### Authentication & User Management
- Registration system with password validation
- Secure JWT-based authentication
- Email verification with confirmation codes
- Resend verification email
- User profile management

### Cache Management
- Import GPX/ZIP files from cgeo and Pocket Queries
- Advanced cache search with multiple filters (type, difficulty, terrain, attributes, dates, etc.)
- Geographic search (within bounding box or radius around a point)
- Visualization of caches on interactive map
- Retrieval of caches by GC code or by identifier

### Challenge System
- Automatic synchronization of user challenges
- Tracking of challenge status (pending, accepted, dismissed, completed)
- Bulk update of challenges
- Detailed information for each challenge
- Evaluation and persistence of targets for challenges

### Classic Challenges
- D/T matrix verification (9x9 difficulty/terrain combinations)
- Calendar challenge verification (365/366 days)
- Support for type and size filters
- Interactive visualization of results

### Progress Tracking
- Real-time evaluation of progress
- History of progress snapshots
- Automatic calculation of first progress for new challenges
- Visualization of progress evolution

### Target Identification
- Evaluation and persistence of targets for each challenge
- Paginated list of targets with sorting options
- Search for targets near a specific point
- Deletion of targets for a specific challenge

### Challenge Task Management
- Visualization of tasks for a challenge
- Replacement of all tasks while preserving order
- Validation of tasks without persistence

### Maintenance and Tools
- Analysis and cleanup of orphaned records
- Full database backup
- Restore from backup file
- Backfill of elevation data for caches (admin only)

---

## 📡 API Routes

### Authentication (`/auth`)
- `POST /auth/register` - Register a new user
- `POST /auth/login` - Login a user
- `POST /auth/refresh` - Refresh access token
- `GET /auth/verify-email` - Verify email by code
- `POST /auth/verify-email` - Verify email via POST
- `POST /auth/resend-verification` - Resend verification code

### Base (`/`)
- `GET /cache_types` - Retrieve all cache types
- `GET /cache_sizes` - Retrieve all cache sizes
- `GET /ping` - API health check

### Caches (`/caches`)
- `POST /caches/upload-gpx` - Import caches from GPX/ZIP file
- `POST /caches/by-filter` - Search caches by filters
- `GET /caches/within-bbox` - Caches within bounding box
- `GET /caches/within-radius` - Caches around a point (radius)
- `GET /caches/{gc}` - Retrieve a cache by GC code
- `GET /caches/by-id/{id}` - Retrieve a cache by MongoDB identifier

### Challenges (`/challenges`)
- `POST /challenges/refresh-from-caches` - Recreate challenges from caches

### My challenges (`/my/challenges`)
- `POST /my/challenges/sync` - Synchronize missing UserChallenges
- `GET /my/challenges` - List UserChallenges
- `PATCH /my/challenges` - Bulk update multiple UserChallenges
- `GET /my/challenges/{uc_id}` - Detail of a UserChallenge
- `PATCH /my/challenges/{uc_id}` - Update a UserChallenge
- `GET /my/challenges/basics/calendar` - Calendar challenge verification
- `GET /my/challenges/basics/matrix` - D/T matrix challenge verification

### My challenge tasks (`/my/challenges/{uc_id}/tasks`)
- `GET /my/challenges/{uc_id}/tasks` - List tasks of a UserChallenge
- `PUT /my/challenges/{uc_id}/tasks` - Replace tasks of a UserChallenge
- `POST /my/challenges/{uc_id}/tasks/validate` - Validate tasks without persistence

### My profile (`/my/profile`)
- `PUT /my/profile/location` - Set location
- `GET /my/profile/location` - Get location
- `GET /my/profile` - Get user profile

### My targets (`/my`)
- `POST /my/challenges/{uc_id}/targets/evaluate` - Evaluate targets for a UserChallenge
- `GET /my/challenges/{uc_id}/targets` - List targets for a UserChallenge
- `GET /my/challenges/{uc_id}/targets/nearby` - List nearby targets for a UserChallenge
- `GET /my/targets` - List of all targets
- `GET /my/targets/nearby` - List nearby targets for all challenges
- `DELETE /my/challenges/{uc_id}/targets` - Delete targets for a UserChallenge

### My progress (`/my/challenges`)
- `GET /my/challenges/{uc_id}/progress` - Retrieve latest snapshot and history
- `POST /my/challenges/{uc_id}/progress/evaluate` - Evaluate and save snapshot
- `POST /my/challenges/new/progress` - Evaluate first progress

### Cache elevation (`/caches_elevation`)
- `POST /caches_elevation/caches/elevation/backfill` - Backfill missing elevation (admin)

### Maintenance (`/maintenance`)
- `GET /maintenance/db_cleanup` - Analyze database for orphans
- `DELETE /maintenance/db_cleanup` - Execute orphan cleanup
- `GET /maintenance/db_cleanup/backups` - List cleanup backup files
- `GET /maintenance/backups/{filepath:path}` - Download backup file
- `POST /maintenance/db_full_backup` - Create full backup
- `POST /maintenance/db_full_restore/{filename}` - Restore from backup
- `GET /maintenance/db_backups` - List all backup files

---

## 🐳 Installation & Launch

> MongoDB **must be accessible from the outside** (e.g., MongoDB Atlas)

### 📁 Prerequisites
- Docker & Docker Compose installed
- Node.js (for frontend development)
- A `.env` file or `MONGO_URI` environment variable available

### ▶️ Development mode launch

```bash
# Build and launch services
docker compose up --build

# Frontend is accessible at http://localhost:5173
# Backend is accessible at http://localhost:8000
```

### 🔧 Configuration

Create a `.env` file at the project root with the following variables:

```env
# Backend
MONGO_URI=your_mongodb_connection_string
JWT_SECRET_KEY=your_secret_key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_MINUTES=43200

# Frontend (in frontend/.env)
VITE_API_URL=http://localhost:8000/api
```

### 🧪 Running tests

```bash
# Backend tests
cd backend
poetry run pytest

# Frontend tests
cd frontend
npm run test:unit
npm run test:e2e
```

---

## 🔨 Build & Deployment

### Build with commit date

The `build.sh` script automatically updates the build date in `.env` using the last Git commit date.

```bash
# Update BUILD_DATE and rebuild backend image
./build.sh

# Then start the application
docker-compose up
```

**Note**: The build date is displayed in the `/version` endpoint:

```bash
curl http://localhost:8000/version

# Response:
{
  "version": "0.1.0",
  "environment": "development",
  "build_date": "2026-02-27T18:42:15+01:00"
}
```

### Recommended workflow

1. Develop and test your changes
2. Commit your changes
3. Run `./build.sh` to update the build date
4. Test the application
5. Push to GitHub

**TODO (Phase 4)**: Automate build date via GitHub Actions during production deployment.

---

## 🤝 Contribution

Contributions are welcome! Here's how you can contribute:

1. Fork the project
2. Create a branch for your feature (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

### Branch naming convention
- Backend features: `backend/feat/feature-name`
- Frontend features: `frontend/feat/feature-name`
- Fixes: `fix/fix-name`

---

## 📋 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.