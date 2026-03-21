# Roadmap produit — GeoChallenge Tracker

**Date de création :** 2026-03-20
**Type :** Roadmap fonctionnelle — ce qui reste à construire
**Sources :** README, analyses 1–4, `TODO_GC_TRACKER.md`, code existant

> Ce document recense les fonctionnalités manquantes, incomplètes ou planifiées.
> Il ne traite pas des corrections de bugs ou de dette technique — voir [`roadmap-corrections.md`](roadmap-corrections.md).

---

## Table des matières

- [Légende](#légende)
- [État actuel du projet](#état-actuel-du-projet)
- [Épic 1 — Authentification & comptes utilisateurs](#épic-1--authentification--comptes-utilisateurs)
- [Épic 2 — Import & gestion des caches](#épic-2--import--gestion-des-caches)
- [Épic 3 — Challenges & progression](#épic-3--challenges--progression)
- [Épic 4 — Visualisation & carte](#épic-4--visualisation--carte)
- [Épic 5 — Notifications & communication](#épic-5--notifications--communication)
- [Épic 6 — Statistiques & exports](#épic-6--statistiques--exports)
- [Épic 7 — Qualité, tests & observabilité](#épic-7--qualité-tests--observabilité)
- [Épic 8 — Infrastructure & déploiement](#épic-8--infrastructure--déploiement)
- [Synthèse par priorité](#synthèse-par-priorité)

---

## Légende

| Symbole | Signification |
|---------|---------------|
| ✅ | Implémenté et fonctionnel |
| 🔧 | Partiellement implémenté / à compléter |
| ❌ | Non implémenté |
| 🔴 | Priorité critique |
| 🟠 | Priorité haute |
| 🟡 | Priorité normale |
| 🟢 | Nice-to-have |

**Complexité :** `S` (< 1 jour) · `M` (1–3 jours) · `L` (3–7 jours) · `XL` (> 1 semaine)

---

## État actuel du projet

### Ce qui fonctionne aujourd'hui

| Domaine | Fonctionnalité | État |
|---------|----------------|------|
| Auth | Register, Login, Refresh token | ✅ |
| Auth | Vérification email par code | ✅ |
| Auth | Renvoi du code de vérification | ✅ |
| Caches | Import GPX / ZIP synchrone | ✅ |
| Caches | Recherche par bbox, rayon, filtres avancés | ✅ |
| Caches | Récupération par GC code ou MongoDB ID | ✅ |
| Challenges | Création challenges depuis caches | ✅ |
| My challenges | Listing paginé, détail, patch unitaire | ✅ |
| My challenges | Calendar challenge (vérification 365 jours) | ✅ |
| My challenges | Matrix D/T (vérification 9×9) | ✅ |
| Targets | Évaluation, listing, recherche à proximité, suppression | ✅ |
| Progress | Évaluation, historique, premier snapshot | ✅ |
| Tasks | Listing, remplacement, validation sans persistance | ✅ |
| Profil | Lecture/écriture profil + localisation | ✅ |
| Stats | Statistiques utilisateur de base | ✅ |
| Maintenance | Analyse orphelins, backup / restore BDD | ✅ |
| Meta | `/health`, `/version`, `/info` | ✅ |
| Carte | Visualisation caches (MapDemo) | ✅ |

### Ce qui est commencé mais incomplet

| Domaine | Fonctionnalité | État | Référence |
|---------|----------------|------|-----------|
| My challenges | Sync UserChallenges | 🔧 BACKLOG | `my_challenges.py:47` |
| My challenges | Batch PATCH challenges | 🔧 BACKLOG | `my_challenges.py:110` |
| Auth | Reset password | ❌ Route absente | — |
| Recherche caches | Recherche par filtre (frontend) | ❌ `_NotImplemented` | `router/index.ts` |
| Progress | Page progression (frontend) | ❌ `_NotImplemented` | `router/index.ts` |
| Targets | Page targets (frontend) | ❌ `_NotImplemented` | `router/index.ts` |
| Health check | Vérification SMTP réelle | 🔧 TODO dans code | `core/meta.py:39` |

---

## Épic 1 — Authentification & comptes utilisateurs

### 1.1 Reset de mot de passe ❌ 🔴 `M`

**Contexte :** L'email de vérification est en place, mais il n'existe aucune route de reset de mot de passe. Un utilisateur qui oublie son mot de passe ne peut pas récupérer son compte.

**À construire :**

| Étape | Backend | Frontend |
|-------|---------|----------|
| Demande de reset | `POST /auth/forgot-password` — génère un token, envoie un email | Formulaire avec champ email |
| Confirmation | `POST /auth/reset-password` — vérifie le token, hash le nouveau mot de passe | Formulaire token + nouveau mot de passe |
| Invalidation | Le token est à usage unique, TTL 1h | — |

**Dépendances :** service email fonctionnel (`aiosmtplib` déjà en place), `users.reset_token` + `users.reset_token_expires_at` à ajouter au modèle `User`.

---

### 1.2 Compléter la synchronisation UserChallenges 🔧 🟠 `M`

**Contexte :** La route `POST /my/challenges/sync` est marquée `TODO: [BACKLOG]` dans le code. La synchronisation crée les `UserChallenge` manquants pour un utilisateur, mais son comportement exact (full sync vs delta) n'est pas finalisé.

**À valider / construire :**
- Définir la logique de sync : full (recrée tout) ou delta (ajoute uniquement les manquants)
- Finaliser la route et la marquer `DONE`
- Ajouter des tests d'intégration couvrant le cas "premier sync" et "sync incrémental"

---

### 1.3 Batch PATCH challenges 🔧 🟡 `S`

**Contexte :** `PATCH /my/challenges` (mise à jour en masse) est déclaré mais non vérifié. Utilisé par le frontend pour changer le statut de plusieurs challenges d'un coup.

**À valider :** comportement en cas d'IDs inexistants, résultat retourné (liste des updated vs erreurs), tests.

---

### 1.4 Déconnexion (logout) avec invalidation côté serveur 🟡 `M`

**Contexte :** Le logout actuel vide simplement le state Pinia et le storage navigateur. Le `refreshToken` n'est pas invalidé côté serveur — si quelqu'un a capturé le token, il reste valide jusqu'à expiration (7 jours).

**À construire :**
- Route `POST /auth/logout` qui insère le `jti` (JWT ID) dans une blacklist (collection MongoDB ou Redis)
- Le middleware de validation JWT vérifie la blacklist
- Le frontend appelle la route avant de vider le storage

---

## Épic 2 — Import & gestion des caches

### 2.1 Import GPX asynchrone (background task) ❌ 🔴 `XL`

**Contexte :** L'import GPX/ZIP est actuellement synchrone. Pour un fichier Pocket Query (typiquement 500–1000 caches), la requête peut dépasser 30 secondes et timeout. Des fichiers Celery sont déjà présents dans le projet (`DETAIL_celery_gpx.md`), la décision d'architecture est prise.

**À construire :**

| Composant | Description |
|-----------|-------------|
| Worker Celery | Service Docker séparé, consomme une queue Redis |
| Task `import_gpx` | Déplace la logique d'import actuelle dans une tâche Celery |
| Route upload | `POST /caches/upload-gpx` retourne un `job_id` immédiatement (HTTP 202) |
| Route statut | `GET /caches/import-jobs/{job_id}` retourne `pending / processing / done / failed` + stats |
| Frontend | Composant de suivi de progression (polling ou SSE) sur la page `ImportGpx.vue` |

**Dépendances :** Redis (nouveau service Docker), Celery (`celery[redis]` à ajouter aux dépendances).

---

### 2.2 Validation GPX avant traitement complet ❌ 🟠 `S`

**Contexte :** Le parser GPX lit actuellement tout le fichier en mémoire avant de détecter un éventuel format invalide. Sur un fichier de 50 Mo corrompu, cela consomme inutilement de la RAM.

**À construire :**
- Lire uniquement les 4 premiers Ko du fichier pour valider le header XML / balise `<gpx>`
- Retourner HTTP 400 immédiatement si invalide, sans traitement complet
- Tester avec des fichiers invalides (JSON, binaire, GPX tronqué)

---

### 2.3 Page "Recherche par filtre" (frontend) ❌ 🟠 `L`

**Contexte :** La route frontend `/caches/by-filter` pointe sur `_NotImplemented.vue`. La route API `POST /caches/by-filter` est fonctionnelle.

**À construire :**
- Formulaire de filtres (type, taille, difficulté, terrain, attributs, dates de placement/trouvaille)
- Tableau de résultats paginé
- Lien vers la fiche d'un cache
- Composable `useCacheFilter` dédié

---

### 2.4 Support streaming pour gros fichiers GPX 🟡 `M`

**Contexte :** Même avec l'asynchronisme (2.1), traiter un GPX de plusieurs milliers de caches en une seule liste peut saturer la RAM. Le traitement par chunks évite ce problème.

**À construire :** Parser itératif (SAX/iterparse) plutôt que chargement complet en mémoire dans le service d'import GPX.

---

## Épic 3 — Challenges & progression

### 3.1 Page "Progression" (frontend) ❌ 🔴 `L`

**Contexte :** La route `/my/challenges/:id/progress` pointe sur `_NotImplemented.vue`. Les routes API de progression (`GET`, `POST /evaluate`, `POST /new/progress`) sont fonctionnelles.

**À construire :**
- Graphique d'évolution temporelle du taux de complétion (% sur le temps)
- Dernier snapshot avec détail (combien de cases remplies, combien manquantes)
- Bouton "Évaluer maintenant" → appelle `POST /evaluate`
- Composable `useProgress` dédié

---

### 3.2 Page "Targets" (frontend) ❌ 🔴 `L`

**Contexte :** La route `/my/challenges/:id/targets` (et la vue globale `/my/targets`) pointe sur `_NotImplemented.vue`. Les routes API targets sont complètes.

**À construire :**
- Liste paginée des caches cibles pour un challenge (avec tri : score, distance, difficulté…)
- Affichage sur carte des targets (via Leaflet)
- Bouton "Rechercher à proximité" → appelle `GET /targets/nearby` avec la localisation de l'utilisateur
- Bouton "Supprimer les targets" → appelle `DELETE /my/challenges/{uc_id}/targets`

---

### 3.3 Évaluation automatique de la progression 🟡 `M`

**Contexte :** L'évaluation de progression est actuellement déclenchée manuellement. Dans un flux naturel, elle devrait être recalculée automatiquement après chaque import GPX.

**À construire :** déclencher `POST /my/challenges/{uc_id}/progress/evaluate` (ou une version batch) automatiquement à la fin d'un import GPX réussi, pour tous les challenges actifs de l'utilisateur.

---

### 3.4 Suggestions de challenges réalisables 🟢 `L`

**Contexte :** Fonctionnalité décrite dans le README ("Get completion projections") mais absente du code.

**À construire :**
- Endpoint `GET /my/challenges/suggestions` : analyse les caches trouvés et non trouvés, calcule le % de complétion potentiel pour chaque challenge non encore actif
- Critère de suggestion : challenges réalisables à ≥ 70% avec les caches actuels de l'utilisateur
- Affichage dans le frontend sous forme de cartes "Challenges recommandés"

---

## Épic 4 — Visualisation & carte

### 4.1 Clustering des marqueurs sur la carte ❌ 🟡 `M`

**Contexte :** La carte affiche actuellement tous les caches comme autant de marqueurs individuels. Au-delà de 200–300 caches, la carte devient illisible et les performances se dégradent.

**À construire :**
- Intégrer `Leaflet.markercluster` dans `MapDemo.vue` et les futurs composants carte
- Configurer le dégroupement progressif au zoom
- Adapter l'API : ajouter un paramètre `cluster=true` optionnel à `GET /caches/within-bbox` pour retourner des centroïdes de cluster côté serveur (MongoDB `$geoNear` + `$group`)

---

### 4.2 Heatmap des trouvailles 🟢 `M`

**Contexte :** Fonctionnalité mentionnée dans le README ("Visualize progress on maps").

**À construire :**
- Intégrer `Leaflet.heat` dans le frontend
- Endpoint `GET /my/found-caches/heatmap` → retourne une liste de `[lat, lng, intensity]`
- Intensité = nombre de caches trouvés dans une zone (agrégation MongoDB)
- Page dédiée ou onglet dans la vue stats

---

### 4.3 Carte des targets d'un challenge 🟡 `S`

**Contexte :** La page Targets (3.2) listera les cibles en tableau, mais une vue carte complémentaire serait utile pour choisir un circuit géographique.

**À construire :** Onglet "Carte" dans la page Targets, réutilisant le composant carte existant avec les targets comme source de données.

---

## Épic 5 — Notifications & communication

### 5.1 Email de reset de mot de passe ❌ 🔴 `S`

Dépend de [1.1](#11-reset-de-mot-de-passe--🔴-m). Template email à créer dans le service email existant.

---

### 5.2 Email de notification "challenge complété" ❌ 🟠 `S`

**Contexte :** Non implémenté. Lors d'une évaluation de progression atteignant 100%, aucun email n'est envoyé.

**À construire :**
- Détecter le passage à 100% dans `POST /my/challenges/{uc_id}/progress/evaluate`
- Envoyer un email de félicitation via `aiosmtplib`
- Template HTML de notification (utiliser le système de templates email existant)

---

### 5.3 Système de notifications in-app ❌ 🟢 `L`

**Contexte :** Fonctionnalité planifiée mais non démarrée.

**À construire :**
- Collection `notifications` en MongoDB (`user_id`, `type`, `payload`, `read_at`, `created_at`)
- `GET /my/notifications` (paginé, avec filtre `unread_only`)
- `PATCH /my/notifications/{id}/read`
- Icône cloche dans le header frontend avec badge compteur
- Optionnel : WebSocket pour les notifications en temps réel

---

### 5.4 Health check email (SMTP réel) 🔧 🟡 `S`

**Contexte :** `check_email()` dans `core/meta.py` retourne toujours `"ok"` (TODO dans le code). En production, si le serveur SMTP est down, le `/health` ne le détecte pas.

**À construire :** Tenter une connexion SMTP (sans envoyer d'email) et retourner `"ok"` ou le message d'erreur.

---

## Épic 6 — Statistiques & exports

### 6.1 Export GPX d'un challenge ❌ 🟠 `M`

**Contexte :** Un geocacheur veut charger les cibles d'un challenge dans son application GPS. Fonctionnalité mentionnée dans `TODO_GC_TRACKER.md`.

**À construire :**
- Route `GET /my/challenges/{uc_id}/export-gpx`
- Générer un fichier GPX valide contenant les caches targets du challenge
- Utiliser `gpxpy` pour la génération (bibliothèque standard du domaine)
- Frontend : bouton "Exporter GPX" dans la page Targets / Détail d'un challenge

---

### 6.2 Statistiques utilisateur avancées 🔧 🟡 `L`

**Contexte :** La route `/user-stats` existe et retourne des statistiques de base. Le README mentionne des projections de complétion, des graphiques d'évolution et des heatmaps.

**À compléter :**

| Métrique | État | Notes |
|----------|------|-------|
| Total caches trouvés | ✅ | |
| Répartition par type/taille | ✅ probable | À vérifier |
| Évolution dans le temps (graphique) | ❌ | Agrégation par mois/semaine |
| D/T matrix complétée % | ✅ via matrix challenge | |
| Projection "à combien de caches du prochain milestone" | ❌ | Calcul côté backend |
| Pays/régions visités | ❌ | Agrégation sur `caches.country` |

**Frontend :** Page `MyStats.vue` existe, à enrichir avec des graphiques (Chart.js ou D3).

---

### 6.3 Recherche full-text sur les caches ❌ 🟡 `S`

**Contexte :** L'index texte est déclaré dans `seed_indexes.py` sur `caches` (`title` + `description`), mais aucune route ne l'exploite.

**À construire :**
- Paramètre `q: str` dans `POST /caches/by-filter` ou nouvelle route `GET /caches/search?q=...`
- Utiliser l'opérateur `$text` MongoDB
- Scoring par pertinence avec `$meta: "textScore"`
- Frontend : champ de recherche textuelle dans le formulaire de filtres (2.3)

---

## Épic 7 — Qualité, tests & observabilité

### 7.1 Tests API backend ❌ 🔴 `L`

**Contexte :** Les tests existants couvrent une partie de la logique métier, mais les routes elles-mêmes (authentification, upload GPX, recherche) ne sont pas testées via l'API.

**À construire :**

| Suite | Cas à couvrir |
|-------|---------------|
| Auth | Register (OK, email dupliqué, password faible), Login (OK, mauvais mot de passe), Refresh (OK, token expiré) |
| Upload GPX | Happy path (fichier valide), fichier trop grand, format invalide, utilisateur non vérifié |
| Recherche caches | `by-filter` avec chaque type de filtre, bbox, radius, résultat vide |
| Challenges | Sync, Calendar, Matrix |

**Stack :** `pytest` + `httpx` (client ASGI) + base MongoDB de test dédiée.

---

### 7.2 Coverage ≥ 60% 🟠 `M`

**Contexte :** Aucun objectif de coverage n'est actuellement mesuré en CI.

**À construire :**
- Configurer `pytest-cov` dans `pyproject.toml`
- Ajouter le rapport de coverage dans la CI GitHub Actions
- Bloquer le merge si coverage descend en dessous de 60%
- Badge coverage dans le README

---

### 7.3 Tests d'intégration challenges 🟡 `M`

Couvrir les flows complets :
- Sync → évaluation → progression
- Évaluation des targets → liste → export GPX
- Calendar / Matrix : cas "complété" et "non complété"

---

### 7.4 Logging structuré ❌ 🔴 `M`

**Contexte :** Le logging actuel utilise `print()` dans plusieurs fichiers. Il n'y a pas de correlation IDs, pas de format JSON, pas de middleware de logging des requêtes HTTP.

**À construire :**
- Remplacer tous les `print()` par `logging.getLogger(__name__)` ou adopter `structlog`
- Middleware FastAPI qui logue chaque requête avec : method, path, status code, durée, user_id
- Format JSON en production, format lisible en développement
- Correlation ID (`X-Request-ID`) propagé dans tous les logs d'une requête

---

### 7.5 Rate limiting sur routes sensibles ❌ 🟠 `S`

**Contexte :** Les routes d'authentification ne sont pas protégées contre le brute force.

**À construire :**
- Intégrer `slowapi` (wrapper FastAPI de `limits`)
- Appliquer : `POST /auth/login` (10 req/min par IP), `POST /auth/register` (5 req/min), `POST /auth/resend-verification` (3 req/min)
- Retourner HTTP 429 avec header `Retry-After`

---

### 7.6 Métriques Prometheus ❌ 🟢 `S`

**Contexte :** Aucune métrique d'instrumentation n'est exposée.

**À construire :**
- Intégrer `prometheus_fastapi_instrumentator`
- Exposer `/metrics` (endpoint Prometheus)
- Métriques : temps de réponse par route, taux d'erreur, nombre de requêtes

---

### 7.7 Tests frontend (Vitest + Playwright) ❌ 🟠 `L`

**Contexte :** L'infrastructure de test est en place (Vitest, Playwright configurés) mais les tests métier sont absents.

**À construire :**
- Tests unitaires Vitest : `useCalendarData`, `useMatrixData`, `useFormValidation`, `useApiErrorHandler`
- Tests de composants : `ChallengeCard`, `MatrixGrid`, `CalendarGrid`
- Tests e2e Playwright : flux login → import GPX → affichage challenges

---

## Épic 8 — Infrastructure & déploiement

### 8.1 Séparation config dev / prod ❌ 🔴 `M`

**Contexte :** Un seul fichier `.env` est utilisé pour les deux environnements. Les settings de debug, CORS, et log level doivent différer entre dev et prod.

**À construire :**
- `.env.dev` : debug activé, CORS permissif (`*`), logs verbose, MailDev
- `.env.prod` : debug désactivé, CORS restrictif (domaine précis), logs JSON, SMTP réel
- `docker-compose.override.yml` pour les overrides de développement
- Documentation dans `.env.example` pour chaque variable

---

### 8.2 Healthchecks Docker Compose 🟠 `M`

**Contexte :** Le backend peut démarrer alors que MongoDB est indisponible (init lazy), sans avertissement visible dans Docker Compose.

**À construire :**
```yaml
# docker-compose.yml
backend:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 10s
```
- Si MongoDB est local (dev) : ajouter service `mongo` avec healthcheck, `depends_on: condition: service_healthy`
- Si MongoDB est externe (Atlas) : ajouter un check de démarrage qui réessaie la connexion avant de déclarer le service healthy

---

### 8.3 CI/CD — Tests automatiques avant merge ❌ 🟠 `M`

**Contexte :** La CI actuelle (`.github/workflows/ci.yml`) ne lance que `ruff` et `mypy`. Les tests ne sont pas joués.

**À ajouter dans la CI :**
- `pytest` backend avec base MongoDB de test (service GitHub Actions)
- `npm run test:unit` frontend (Vitest)
- Rapport de coverage uploadé comme artifact
- Bloquer le merge si tests échouent ou si coverage < 60%

---

### 8.4 HTTPS en production 🔴 `M`

**Contexte :** La configuration Nginx existe dans `ops/nginx/` mais la redirection HTTP → HTTPS et les certificats SSL ne sont pas documentés / vérifiés.

**À construire / vérifier :**
- Configuration Nginx avec `return 301 https://$host$request_uri;` sur le port 80
- Intégration Let's Encrypt (Certbot) ou certificat manuel
- HSTS header
- Documenter le processus de renouvellement de certificat

---

### 8.5 Security headers HTTP ❌ 🟡 `S`

**À ajouter dans Nginx (production) ou FastAPI (dev) :**

```nginx
add_header X-Content-Type-Options "nosniff";
add_header X-Frame-Options "DENY";
add_header Content-Security-Policy "default-src 'self'; ...";
add_header Referrer-Policy "strict-origin-when-cross-origin";
```

---

### 8.6 Automatisation du `build_date` via GitHub Actions 🟡 `S`

**Contexte :** Le README documente un `TODO (Phase 4)` : automatiser la mise à jour du `BUILD_DATE` dans la CI lors d'un déploiement en production.

**À construire :**
- Step dans `build-push.yml` qui injecte `BUILD_DATE=$(git log -1 --format=%cI)` comme `build-arg` Docker
- Supprimer le script manuel `build.sh` ou le garder pour le dev local uniquement

---

### 8.7 Logs centralisés en production ❌ 🟢 `L`

**À construire :**
- Configurer le driver de logs Docker pour envoyer vers Loki ou un fichier centralisé
- Stack Loki + Grafana (légère, auto-hébergeable) ou équivalent cloud
- Dashboards : taux d'erreur, temps de réponse, imports GPX en cours

---

## Synthèse par priorité

### 🔴 Critique — À traiter en premier

| # | Fonctionnalité | Épic | Taille |
|---|----------------|------|--------|
| 1 | Reset de mot de passe | 1.1 | M |
| 2 | Import GPX asynchrone | 2.1 | XL |
| 3 | Page Progression (frontend) | 3.1 | L |
| 4 | Page Targets (frontend) | 3.2 | L |
| 5 | Tests API backend | 7.1 | L |
| 6 | Logging structuré | 7.4 | M |
| 7 | Séparation config dev/prod | 8.1 | M |
| 8 | HTTPS en production | 8.4 | M |

### 🟠 Haute — Sprint suivant

| # | Fonctionnalité | Épic | Taille |
|---|----------------|------|--------|
| 9 | Validation GPX avant traitement | 2.2 | S |
| 10 | Page recherche par filtre (frontend) | 2.3 | L |
| 11 | Email notification challenge complété | 5.2 | S |
| 12 | Export GPX d'un challenge | 6.1 | M |
| 13 | Coverage ≥ 60% | 7.2 | M |
| 14 | Rate limiting auth | 7.5 | S |
| 15 | Tests frontend (Vitest) | 7.7 | L |
| 16 | Healthchecks Docker Compose | 8.2 | M |
| 17 | CI/CD — Tests avant merge | 8.3 | M |

### 🟡 Normale — Backlog moyen terme

| # | Fonctionnalité | Épic | Taille |
|---|----------------|------|--------|
| 18 | Sync UserChallenges (finaliser) | 1.2 | M |
| 19 | Batch PATCH challenges (valider) | 1.3 | S |
| 20 | Support streaming GPX | 2.4 | M |
| 21 | Évaluation auto après import | 3.3 | M |
| 22 | Clustering carte | 4.1 | M |
| 23 | Carte des targets | 4.3 | S |
| 24 | Health check SMTP réel | 5.4 | S |
| 25 | Statistiques avancées | 6.2 | L |
| 26 | Recherche full-text caches | 6.3 | S |
| 27 | Tests d'intégration challenges | 7.3 | M |
| 28 | Security headers HTTP | 8.5 | S |
| 29 | Automatisation build_date CI | 8.6 | S |

### 🟢 Nice-to-have — Long terme

| # | Fonctionnalité | Épic | Taille |
|---|----------------|------|--------|
| 30 | Logout avec invalidation serveur | 1.4 | M |
| 31 | Suggestions de challenges | 3.4 | L |
| 32 | Heatmap des trouvailles | 4.2 | M |
| 33 | Notifications in-app | 5.3 | L |
| 34 | Métriques Prometheus | 7.6 | S |
| 35 | Logs centralisés production | 8.7 | L |
