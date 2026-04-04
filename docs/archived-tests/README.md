# Archived Tests

**Date d'archivage :** 2026-03-22

Ces tests ont été retirés du dossier `backend/tests/` car ils ne sont plus exécutables en l'état.
Ils sont conservés ici comme référence pour une réécriture future.

---

## `_test_challenge_autocreate.py`

**Raison :** Appels à `get_collection()` en mode synchrone alors que Motor est asynchrone.
Nécessite une réécriture avec `pytest-asyncio` et les fixtures async du projet.

---

## `_test_email_verification.py`

**Raison :** Style très ancien (pas de `pytest-asyncio`, `TestClient` synchrone, appels Motor synchrones).
Trop éloigné de l'architecture actuelle pour une correction simple.

---

## `_test_my_challenges_routes.py`

**Raison :** Override de `get_current_user` qui n'est plus le point d'entrée direct depuis la
refactorisation des dépendances vers `app.api.deps`. À réécrire avec les nouveaux mécanismes
d'injection de dépendances.

---

## `_test_upload_gpx.py`

**Raison :** Nettoyage de base de données synchrone dans les fixtures, dépendance à des fichiers
GPX de samples dont la présence n'est pas garantie. À réécrire avec fixtures async et données de test isolées.

---

## `_test_user_challenges_counts.py`

**Raison :** Valeurs attendues codées en dur (`EXPECTED_TOTAL = 222`, `EXPECTED_COMPLETED = 90`)
spécifiques à une base de données réelle. Non reproductible sans snapshot de la DB de prod.
À réécrire avec des fixtures qui seed les données nécessaires.
