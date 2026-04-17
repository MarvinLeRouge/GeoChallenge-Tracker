# Scripts de Gestion de Base de Données et Données Géographiques

## 📋 Vue d'ensemble

Ce répertoire contient deux catégories de scripts :
- **Scripts de données géographiques** — setup one-shot pour la carte choroplèthe
- **Scripts de base de données** — préparation de la DB de test pour les tests d'intégration

---

## 🗺️ Scripts de données géographiques (carte choroplèthe)

Ces trois scripts sont à exécuter **une seule fois** après l'installation initiale, dans l'ordre indiqué.
Ils sont tous idempotents : les relancer sans risque si nécessaire.

### `download_geo_data.py`

**Télécharge les fichiers GeoJSON dans `data/admin/`.**

- Skip les fichiers déjà présents
- Sources configurées dans `config/geo_sources.yml`
- Actuellement : régions et départements français (france-geojson.gregoiredavid.fr)

```bash
cd backend
python scripts/download_geo_data.py
```

### `seed_zones.py`

**Peuple la collection MongoDB `administrative_zones` à partir des GeoJSON téléchargés.**

- Upsert par `code` — relançable sans effet
- Calcule le bbox de chaque zone via Shapely
- Extrait le `feature_code` (code INSEE) de chaque feature

```bash
cd backend
python scripts/seed_zones.py
```

### `assign_zones.py`

**Assigne les zones administratives aux caches existantes dans MongoDB.**

- Skip les caches dont `zones` est déjà renseigné (sauf `--force`)
- Filtre par pays (`--country FR` par défaut) pour ne pas traiter les caches étrangères
- Utilise le même algorithme 3 passes que le pipeline d'import GPX :
  1. Shapely point-in-polygon (exact)
  2. Nominatim reverse geocoding (batch, 1 req/s)
  3. Polygone le plus proche (fallback < 0,1°)
- Traitement par batch de 500 (bulk write)

```bash
cd backend
python scripts/assign_zones.py           # France uniquement
python scripts/assign_zones.py --force   # Réassigner même les caches déjà traitées
```

### Workflow complet

```bash
cd backend
python scripts/download_geo_data.py
python scripts/seed_zones.py
python scripts/assign_zones.py
```

---

---

## 🔄 `duplicate_db_for_tests.py`

**Copie complète de la DB de production vers la DB de test.**

### Fonctionnalités
- ✅ Copie toutes les collections
- ✅ Copie toutes les données
- ✅ Copie tous les indexes
- ✅ Anonymise les utilisateurs (emails, usernames)
- ✅ Drop la DB de test avant copie

### Usage
```bash
cd backend
python scripts/duplicate_db_for_tests.py
```

### Temps d'exécution
~30-60 secondes pour 23 Mo

### Quand l'utiliser ?
- Tests d'intégration qui nécessitent des données réalistes
- Tests de performance
- Tests de migration
- Avant une session de tests complète

---

## 📐 `copy_db_structure.py`

**Copie uniquement la structure (collections + indexes) sans les données.**

### Fonctionnalités
- ✅ Crée toutes les collections (vides)
- ✅ Copie tous les indexes
- ❌ Ne copie PAS les données
- ✅ Drop la DB de test avant copie

### Usage
```bash
cd backend
python scripts/copy_db_structure.py
```

### Temps d'exécution
~5-10 secondes

### Quand l'utiliser ?
- Tests d'intégration qui seedent leurs propres données
- Tests unitaires d'intégration
- Développement itératif rapide
- CI/CD (plus rapide)

---

## 🔧 Configuration Requise

### Variables d'Environnement

Les scripts lisent le fichier `.env` **à la racine du projet** (pas dans `backend/`) :

```bash
# .env (à la racine du projet)
MONGODB_USER=ton_user
MONGODB_PASSWORD=ton_password
MONGODB_URI_TPL=mongodb+srv://[[MONGODB_USER]]:[[MONGODB_PASSWORD]]@cluster.mongodb.net
MONGODB_DB=geoChallenge_Tracker
```

**Important** :
- Le fichier `.env` est à la **racine** du projet
- La DB de test est automatiquement nommée `{MONGODB_DB}_TEST`
- Les deux DBs (prod et test) sont dans le **même cluster**

### Pré-requis
- Python 3.11+
- `motor` (déjà installé)
- `python-dotenv` (déjà installé)
- Accès à MongoDB Atlas

---

## 🎯 Workflow Recommandé

### En Local (Développement)

```bash
# 1. S'assurer d'être dans le dossier backend
cd backend

# 2. Dupliquer la DB (une fois par session)
python scripts/duplicate_db_for_tests.py

# 3. Lancer les tests
pytest tests/integration/ -v

# 4. Si besoin de reset
python scripts/duplicate_db_for_tests.py
```

### En CI/CD

```bash
cd backend

# Structure seule (plus rapide)
python scripts/copy_db_structure.py

# Seed des données de test
pytest tests/integration/ --seed-data

# Cleanup automatique via fixtures
```

---

## 🔒 Anonymisation des Données

Le script `duplicate_db_for_tests.py` anonymise :

| Collection | Champs Anonymisés | Format |
|------------|------------------|--------|
| `users` | `email` | `test_{_id}@test.local` |
| `users` | `username` | `test_{_id[:8]}` |

**Notes** :
- Le `password_hash` est conservé (nécessaire pour les tests d'auth)
- Les autres collections ne sont pas anonymisées (données publiques)
- La DB de test est nommée `{MONGODB_DB}_TEST` (ex: `geoChallenge_Tracker_TEST`)

---

## 🛠️ Dépannage

### Erreur : "Authentication failed"
→ Vérifie tes credentials dans `.env` (à la racine)

### Erreur : "Database not found"
→ Vérifie le nom de la DB dans `.env`
→ La DB de test sera `{MONGODB_DB}_TEST`

### Erreur : "Timeout"
→ Vérifie ta connexion à MongoDB Atlas
→ Augmente le timeout de connexion

### La DB de test n'est pas vide
→ Le script drop la DB avant copie, mais tu peux manually drop :
```javascript
use geoChallenge_Tracker_TEST
db.dropDatabase()
```

### Erreur : "FileNotFoundError: No such file or directory: '.env'"
→ Assure-toi de lancer le script depuis le dossier `backend/`
→ Le script cherche automatiquement le `.env` à la racine

---

## 📊 Comparaison

| Critère | `duplicate_db_for_tests.py` | `copy_db_structure.py` |
|---------|----------------------------|------------------------|
| **Données** | ✅ Complètes | ❌ Vides |
| **Indexes** | ✅ Oui | ✅ Oui |
| **Temps** | 30-60s | 5-10s |
| **Anonymisation** | ✅ Oui | N/A |
| **Usage** | Tests réalistes | Tests rapides |

---

## 🎯 Prochaines Étapes

Après avoir lancé un des scripts :

```bash
# Lancer les tests d'intégration
pytest tests/integration/ -v

# Ou avec coverage
pytest tests/integration/ --cov=app --cov-report=html
```
