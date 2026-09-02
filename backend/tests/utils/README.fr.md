🇫🇷 Version française | [🇬🇧 English version](README.md)

---

# Scripts de gestion de la base de données de test

## Vue d'ensemble

Ce répertoire contient deux scripts pour préparer la base MongoDB de test à partir de la base de production, utilisés pour les tests d'intégration.

> ⚠️ Malgré leur commentaire d'en-tête `Usage: python scripts/...`, ces scripts vivent dans `backend/tests/utils/`, pas dans `backend/scripts/` (qui ne contient que les scripts de données géographiques, voir [`backend/scripts/README.fr.md`](../../scripts/README.fr.md)).

---

## `duplicate_db_for_tests.py`

**Copie la base de production vers la base de test.**

### Fonctionnalités
- Copie les collections manquantes, les indexes et les documents
- **Ne supprime pas** les collections existantes : une collection de test déjà peuplée est laissée telle quelle (skip), le script ne fait donc que compléter, pas repartir de zéro
- Anonymise les utilisateurs : `email` → `test_{_id}@geochallenge.app`, `username` → `test_{_id[:8]}` (le `password_hash` est conservé pour les tests d'auth)
- Force la création de l'index `2dsphere` sur `caches.loc` s'il manque

### Usage
```bash
cd backend
python tests/utils/duplicate_db_for_tests.py
```

### Temps d'exécution
~30-60 secondes pour 23 Mo

### Quand l'utiliser ?
- Tests d'intégration qui nécessitent des données réalistes
- Tests de performance
- Tests de migration
- Avant une session de tests complète

---

## `copy_db_structure.py`

**Copie uniquement la structure (collections + indexes) sans les données.**

### Fonctionnalités
- Supprime entièrement la base de test avant copie (`drop_database`)
- Crée toutes les collections (vides)
- Copie tous les indexes
- Ne copie pas les données

### Usage
```bash
cd backend
python tests/utils/copy_db_structure.py
```

### Temps d'exécution
~5-10 secondes

### Quand l'utiliser ?
- Tests d'intégration qui seedent leurs propres données
- Développement itératif rapide
- CI/CD (plus rapide)

---

## Configuration requise

### Variables d'environnement

Les scripts lisent le fichier `.env` à la racine du projet (pas dans `backend/`) :

```bash
# .env (à la racine du projet)
MONGODB_USER=ton_user
MONGODB_PASSWORD=ton_password
MONGODB_URI_TPL=mongodb+srv://[[MONGODB_USER]]:[[MONGODB_PASSWORD]]@cluster.mongodb.net
MONGODB_DB=geoChallenge_Tracker
```

**Important** :
- La DB de test est automatiquement nommée `{MONGODB_DB}_TEST`
- Les deux DBs (prod et test) sont dans le même cluster

⚠️ **Bug connu** : `copy_db_structure.py` calcule la racine du projet avec `Path(__file__).resolve().parents[2]`, ce qui pointe vers `backend/` (donc `backend/.env`, actuellement vide) au lieu de la racine du dépôt utilisée par `duplicate_db_for_tests.py` (`parents[3]`). Le script tombe alors sur les identifiants par défaut codés en dur, potentiellement invalides. Correction attendue : passer à `parents[3]`.

### Pré-requis
- Python 3.11+
- `motor`, `python-dotenv` (déjà installés)
- Accès à MongoDB Atlas

---

## Workflow recommandé

### En local (développement)

```bash
cd backend
python tests/utils/duplicate_db_for_tests.py
pytest tests/integration/ -v
```

### En CI/CD

```bash
cd backend
python tests/utils/copy_db_structure.py   # structure seule, plus rapide
pytest tests/integration/ -v
```

---

## Comparaison

| Critère | `duplicate_db_for_tests.py` | `copy_db_structure.py` |
|---------|------------------------------|-------------------------|
| Données | Copiées (si absentes) | Non copiées |
| Indexes | Oui | Oui |
| Reset de la DB de test | Non (skip par collection) | Oui (`drop_database`) |
| Temps | 30-60s | 5-10s |
| Anonymisation | Oui | Sans objet |
| Usage | Tests réalistes | Tests rapides |

---

## Dépannage

### Erreur : "Authentication failed"
Vérifie tes identifiants dans `.env` (racine du projet). Pour `copy_db_structure.py`, voir le bug connu ci-dessus.

### Erreur : "Database not found"
Vérifie le nom de la DB dans `.env`. La DB de test sera `{MONGODB_DB}_TEST`.

### La DB de test contient des données inattendues
`duplicate_db_for_tests.py` ne réinitialise pas les collections déjà peuplées. Pour repartir de zéro, utilise `copy_db_structure.py` ou supprime manuellement :
```javascript
use geoChallenge_Tracker_TEST
db.dropDatabase()
```

### Erreur : "FileNotFoundError: No such file or directory: '.env'"
Lance le script depuis le dossier `backend/` (`cd backend`).
