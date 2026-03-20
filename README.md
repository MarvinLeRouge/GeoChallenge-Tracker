[🇫🇷 Version française](README.fr.md) | 🇬🇧 English version

---

# 🧭 GeoChallenge Tracker

> *Full-stack geocaching challenge tracker — FastAPI + MongoDB REST API, Vue.js 3 frontend, GPX import, interactive maps.*

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.117+-009688?logo=fastapi&logoColor=white)
![Vue.js](https://img.shields.io/badge/Vue.js-3-4FC08D?logo=vuedotjs&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)
[![CI](https://github.com/MarvinLeRouge/GeoChallenge-Tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/MarvinLeRouge/GeoChallenge-Tracker/actions)
![License](https://img.shields.io/github/license/MarvinLeRouge/GeoChallenge-Tracker?cacheSeconds)

## Concept

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
