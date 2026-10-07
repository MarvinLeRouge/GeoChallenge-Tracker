🇫🇷 Version française | [🇬🇧 English version](roadmap.md)

---

# Roadmap produit : GeoChallenge Tracker

**Date de création :** 2026-03-20
**Dernière mise à jour :** 2026-09-02 (vérification factuelle par rapport au code : health check SMTP, clustering des marqueurs, recherche full-text)
**Type :** Roadmap fonctionnelle, ce qui reste à construire
**Sources :** README, code existant

> Ce document recense les fonctionnalités manquantes, incomplètes ou planifiées.
> Il ne traite pas des corrections de bugs ou de dette technique (suivies séparément, hors dépôt).

---

## Table des matières

- [Légende](#légende)
- [État actuel du projet](#état-actuel-du-projet)
- [Épic 1 : Authentification & comptes utilisateurs](#épic-1--authentification--comptes-utilisateurs)
- [Épic 2 : Import & gestion des caches](#épic-2--import--gestion-des-caches)
- [Épic 3 : Challenges & progression](#épic-3--challenges--progression)
- [Épic 4 : Visualisation & carte](#épic-4--visualisation--carte)
- [Épic 5 : Notifications & communication](#épic-5--notifications--communication)
- [Épic 6 : Statistiques & exports](#épic-6--statistiques--exports)
- [Épic 7 : Qualité, tests & observabilité](#épic-7--qualité-tests--observabilité)
- [Épic 8 : Infrastructure & déploiement](#épic-8--infrastructure--déploiement)
- [Épic 9 : Données géographiques & zones administratives](#épic-9--données-géographiques--zones-administratives)
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
| Targets | Évaluation, listing, recherche à proximité, suppression (API) | ✅ |
| Targets | Page globale `/my/targets` (frontend) | ✅ |
| Progress | Évaluation, historique, premier snapshot | ✅ |
| Tasks | Listing, remplacement, validation sans persistance | ✅ |
| Profil | Lecture/écriture profil + localisation | ✅ |
| Stats | Statistiques utilisateur de base | ✅ |
| Maintenance | Analyse orphelins, backup / restore BDD | ✅ |
| Meta | `/health`, `/version`, `/info` (avec vérification SMTP réelle) | ✅ |
| Carte | Visualisation caches (MapDemo) | ✅ |
| Carte | Clustering des marqueurs (WithinBbox, WithinRadius, Targets) | ✅ |
| Caches | Recherche full-text (`$text` via `POST /caches/by-filter`) | ✅ |

### Ce qui est commencé mais incomplet

| Domaine | Fonctionnalité | État | Référence |
|---------|----------------|------|-----------|
| My challenges | Sync UserChallenges | 🔧 BACKLOG | `my_challenges.py:46` |
| My challenges | Batch PATCH challenges | 🔧 BACKLOG | `my_challenges.py:109` |
| Auth | Reset password | ❌ Route absente | - |
| Recherche caches | Recherche par filtre (frontend) | ❌ `_NotImplemented` | `router/index.ts` |
| Progress | Page progression (frontend) | ❌ `_NotImplemented` | `router/index.ts` |
| Targets | Page targets par challenge (frontend) | ❌ `_NotImplemented` | `router/index.ts` |

---

## Épic 1 : Authentification & comptes utilisateurs

### 1.1 Reset de mot de passe ❌ 🔴 `M`

**Contexte :** L'email de vérification est en place, mais il n'existe aucune route de reset de mot de passe. Un utilisateur qui oublie son mot de passe ne peut pas récupérer son compte.

**À construire :**

| Étape | Backend | Frontend |
|-------|---------|----------|
| Demande de reset | `POST /auth/forgot-password` : génère un token, envoie un email | Formulaire avec champ email |
| Confirmation | `POST /auth/reset-password` : vérifie le token, hash le nouveau mot de passe | Formulaire token + nouveau mot de passe |
| Invalidation | Le token est à usage unique, TTL 1h | - |

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

### 1.4 Déconnexion (logout) avec invalidation côté serveur ✅ 🟡 `M`

**Fait (2026-08-01) :** `POST /auth/logout` révoque le refresh token via son `jti` (collection MongoDB `revoked_refresh_tokens`, index TTL pour nettoyage automatique). `/auth/refresh` rejette les tokens révoqués. Le frontend appelle la route avant de vider le storage, en best-effort. Cookie `refresh_token` élargi de `path=/auth/refresh` à `path=/auth` pour atteindre le nouvel endpoint.

---

## Épic 2 : Import & gestion des caches

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

## Épic 3 : Challenges & progression

### 3.1 Page "Progression" (frontend) ❌ 🔴 `L`

**Contexte :** La route `/my/challenges/:id/progress` pointe sur `_NotImplemented.vue`. Les routes API de progression (`GET`, `POST /evaluate`, `POST /new/progress`) sont fonctionnelles.

**À construire :**
- Graphique d'évolution temporelle du taux de complétion (% sur le temps)
- Dernier snapshot avec détail (combien de cases remplies, combien manquantes)
- Bouton "Évaluer maintenant" → appelle `POST /evaluate`
- Composable `useProgress` dédié

---

### 3.2 Page "Targets" (frontend) 🔧 🔴 `L`

**Vue globale (fait) :** `/my/targets` (`Targets.vue`) est pleinement fonctionnelle : carte Leaflet, mode "à proximité" avec sélection du centre, bouton "Rechercher à proximité", évaluation et affichage des targets.

**Vue par challenge (reste à construire) :** `/my/challenges/:id/targets` pointe toujours sur `_NotImplemented.vue`. Les routes API targets sont complètes (`GET /targets/nearby`, `DELETE /my/challenges/{uc_id}/targets`, etc.).

**À construire (vue par challenge) :**
- Liste paginée des caches cibles pour ce challenge spécifique (avec tri : score, distance, difficulté…)
- Réutiliser le composant carte existant de `Targets.vue`
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

## Épic 4 : Visualisation & carte

### 4.1 Clustering des marqueurs sur la carte 🔧 🟡 `M`

**Fait :** `Leaflet.markercluster` est intégré côté client dans `WithinBbox.vue`, `WithinRadius.vue` et `Targets.vue` (`L.markerClusterGroup`), avec dégroupement progressif au zoom.

**Reste à construire :**
- Intégrer le clustering dans `MapDemo.vue`, qui affiche encore tous les caches comme marqueurs individuels
- Adapter l'API : ajouter un paramètre `cluster=true` optionnel à `GET /caches/within-bbox` pour retourner des centroïdes de cluster côté serveur (MongoDB `$geoNear` + `$group`), utile pour les très gros volumes où le clustering côté client seul ne suffit plus

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

## Épic 5 : Notifications & communication

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

### 5.4 Health check email (SMTP réel) ✅ 🟡 `S`

**Fait (2026-03-21) :** `check_email()` dans `core/meta.py` ouvre une vraie connexion SMTP (avec STARTTLS si le port est 587) et envoie un `NOOP` pour vérifier que le serveur répond, sans envoyer d'email. Retourne `"ok"` ou le message d'erreur.

---

## Épic 6 : Statistiques & exports

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

### 6.3 Recherche full-text sur les caches 🔧 🟡 `S`

**Fait :** l'index texte déclaré dans `seed_indexes.py` (`title` + `description`) est exploité via le paramètre `q` de `POST /caches/by-filter`, qui utilise l'opérateur `$text` MongoDB.

**Reste à construire :**
- Scoring par pertinence avec `$meta: "textScore"` (le tri actuel ne priorise pas les résultats les plus pertinents)
- Frontend : champ de recherche textuelle dans le formulaire de filtres (2.3)

---

## Épic 7 : Qualité, tests & observabilité

### 7.1 Tests API backend ✅ 🔴 `L`

**Fait (2026-08-03) :** les routes sont testées via l'API, avec des tests d'intégration (`backend/tests/integration/`, ex. `test_authenticated.py`) et des tests unitaires montant les vraies routes FastAPI avec dépendances mockées (`backend/tests/unit/test_maintenance_*.py`, etc.), stack `pytest` + `httpx.AsyncClient`. 1291 tests backend au total (`pytest tests/unit -q`).

---

### 7.2 Coverage ≥ 60% ✅ `M`

**Fait et largement dépassé (2026-08-03) :** Codecov intégré en CI (backend + frontend, `codecov.yml`), avec des seuils bloquants réels (`project target: 90%`, `patch target: 95%`, `informational: false`), bien au-delà de l'objectif initial de 60%. Badge dans le README.

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

### 7.5 Rate limiting sur routes sensibles ✅ 🟠 `S`

**Fait (2026-08-01) :** `slowapi` intégré. `POST /auth/login` (10/min), `POST /auth/register` (5/min), `POST /auth/resend-verification` (3/min). HTTP 429 avec header `Retry-After`.

---

### 7.6 Métriques Prometheus ❌ 🟢 `S`

**Contexte :** Aucune métrique d'instrumentation n'est exposée.

**À construire :**
- Intégrer `prometheus_fastapi_instrumentator`
- Exposer `/metrics` (endpoint Prometheus)
- Métriques : temps de réponse par route, taux d'erreur, nombre de requêtes

---

### 7.7 Tests frontend (Vitest + Playwright) 🔧 🟠 `L`

**Vitest (fait, 2026-08-03) :** 419 tests unitaires/composants (`npx vitest run frontend/tests/unit`, composables comme `useCalendarData`/`useMatrixData`, composants comme les pages `Calendar.vue`/`Matrix.vue`/`List.vue`), tournant en CI avec upload de couverture vers Codecov.

**Playwright (démarré, pas encore automatisé) :** deux specs e2e existent (`frontend/tests/e2e/login-map-center.spec.ts`, `smoke.spec.ts`) mais ne tournent pas en CI (aucune étape Playwright dans `.github/workflows/ci.yml`).

**Reste à construire :**
- Intégrer l'exécution Playwright dans la CI GitHub Actions
- Étoffer les specs e2e (flux login → import GPX → affichage challenges)

---

## Épic 8 : Infrastructure & déploiement

### 8.1 Séparation config dev / prod ❌ 🔴 `M`

**Contexte (corrigé le 2026-09-02) :** dev et prod utilisent déjà des fichiers env physiquement séparés, pas un `.env` partagé unique : dev lit le `.env` racine (voir `.env.example`), tandis que la prod lit `shared/env/app.env` et `shared/env/secrets.env` sur le serveur de déploiement (hors dépôt, renseignés manuellement, voir [`docs/operations.fr.md`](operations.fr.md)). Ce qui manque réellement est comportemental, pas structurel : sur les trois settings visés par cet item, seule `CORS_ORIGINS` est effectivement branchée au code (`settings.cors_origins`). `DEBUG` et `LOG_LEVEL`, bien que documentées dans `.env.example`, ne sont lues nulle part dans le backend (voir `DOC-5` dans la section [« Trouvés pendant la passe de documentation »](roadmap-corrections.fr.md#trouvés-pendant-la-passe-de-documentation-2026-09) de `roadmap-corrections.fr.md` pour le détail du bug).

**À construire :**
- Soit brancher `DEBUG` et `LOG_LEVEL` sur un comportement réel (ex. exposition reload/docs de FastAPI, verbosité des logs), soit les retirer de `.env.example` si elles ne serviront jamais (voir DOC-5).
- Vérifier et documenter que `CORS_ORIGINS` en prod (dans `shared/env/app.env`, hors dépôt) est bien restreint au domaine de production plutôt que laissé à la valeur par défaut de dev.
- `docker-compose.override.yml` pour les overrides propres au développement, si toujours souhaité en plus des fichiers env prod déjà séparés.

---

### 8.2 Healthchecks Docker Compose 🔧 `M`

**Prod (fait) :** `docker-compose.prod.yml` a un healthcheck sur `backend` (`curl -f http://localhost:8000/health`) et sur `tiles`.

**Dev (partiel) :** `docker-compose.yml` a un healthcheck sur `tiles` uniquement ; `backend` n'en a pas encore en dev.

**À construire (dev) :**
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
MongoDB étant externe (Atlas) dans les deux environnements, pas de service `mongo` local à ajouter : le `/health` backend fait déjà le check de connexion Atlas (voir Épic 5.4).

---

### 8.3 CI/CD : Tests automatiques avant merge ✅ 🟠 `M`

**Fait (2026-08-03) :** la CI (`.github/workflows/ci.yml`) lance `pytest tests/unit/ --cov=app` (backend) et `npm run test:unit` (frontend), toutes deux avec upload de couverture vers Codecov, dont les seuils (`project: 90%`, `patch: 95%`) sont bloquants (`informational: false`).

---

### 8.4 HTTPS en production ✅ 🟡 `M`

**Fait (2026-03-30, PR #25 ; harmonisé le 2026-06-24, PR #61) :** la production tourne derrière Traefik, qui termine le TLS via Let's Encrypt (challenge DNS Cloudflare) sur l'entrypoint `websecure` pour les trois services (backend, frontend, tuiles), voir [ADR 0004](adr/0004-traefik-reverse-proxy-with-harmonized-dev-prod-routing.md) et [`docs/operations.fr.md`](operations.fr.md). L'approche basée sur Nginx esquissée ici à l'origine (redirection manuelle `return 301`, Certbot) a été remplacée avant d'être construite ; l'émission et le renouvellement des certificats sont gérés par Traefik lui-même, pas documentés comme un processus manuel séparé.

---

### 8.5 Security headers HTTP ✅ 🟡 `S`

**Fait (2026-08-01) :** en-têtes `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`, `Referrer-Policy`, `Strict-Transport-Security`, `Permissions-Policy` ajoutés via un snippet Nginx partagé (`include`d dans chaque `location`, pour contourner le fait qu'un bloc `location` avec son propre `add_header` n'hérite pas de ceux du `server` parent). Vérifié en conditions réelles (headers observés sur les réponses).

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

### 8.8 Vulnérabilités des dépendances npm frontend (`npm audit`) ❌ 🟠 `L`

**Découvert (2026-10-07) :** en corrigeant un problème `pip-audit` backend sans rapport (PR #181), la modification du fichier partagé `.github/workflows/ci.yml` a déclenché le job CI `frontend-security` (ce fichier est surveillé à la fois par les filtres de chemin `backend` et `frontend`), qui ne s'était pas réellement exécuté sur un commit récent de `main`. Il a échoué avec **22 vulnérabilités connues (6 modérées, 14 élevées, 2 critiques)**. Confirmé via un worktree propre (`npm ci && npm audit --audit-level=critical` directement sur `main`) que c'est 100% préexistant sur `main`, sans rapport avec la PR #181 - la modification de son workflow CI a été annulée pour la garder backend-only et la débloquer, ce fix étant reporté.

**Constats (`npm audit`, 2026-10-07) :**
- **Critique :** `tinypool` (transitif via `@vitest/mocker`/`@vitest/coverage-v8` de `vitest` 2.1.0-4.1.10) - gadget de pollution de prototype menant à une RCE ([GHSA-5gmw-xhrv-c9v3](https://github.com/advisories/GHSA-5gmw-xhrv-c9v3), [GHSA-85c8-ppgw-ccpr](https://github.com/advisories/GHSA-85c8-ppgw-ccpr)). Le fix nécessite `vitest@5.0.3` - **changement cassant**.
- **Élevée :** chaîne `braces`/`chokidar`/`tailwindcss` - DoS par épuisement de pile ([GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm)). Le fix nécessite `tailwindcss@4.3.3` - **changement cassant** (montée de version majeure, format de config différent entre Tailwind v3 et v4).
- **Élevée :** chaîne `nanoid`/`flowbite-vue` - dépassement d'entier / boucle infinie ([GHSA-28wg-ghj8-5hjv](https://github.com/advisories/GHSA-28wg-ghj8-5hjv) et autres). Le fix n'est disponible que via une **régression de version** vers `flowbite-vue@0.0.7` (actuellement figé à `0.2.3`) - nécessite d'abord un audit des usages réels de l'API, une telle régression risque fort de supprimer des fonctionnalités utilisées ; pas un `--force` à l'aveugle.
- **Élevée :** `axios` (1.0.0-1.19.0) - pollution de prototype, ReDoS, injection d'en-têtes, contournement SSRF (11 avis, voir le log brut). Fix disponible **sans rupture** via `npm audit fix`.
- **Élevée :** `@vue/server-renderer`/`vue` (3.2.13-3.5.41) - XSS via l'absence de CR dans la liste noire des noms d'attributs ([GHSA-g2v6-rqmx-r4w6](https://github.com/advisories/GHSA-g2v6-rqmx-r4w6)). Fix disponible **sans rupture** via `npm audit fix`.
- **Élevée :** `source-map-js`, `js-yaml` - DoS par blocage de la boucle d'événements / usage CPU incontrôlé. Fix disponible **sans rupture**.
- **Modérée (6) :** `@humanfs/node`, `@vitest/mocker` (voir tinypool ci-dessus), `baseline-browser-mapping`, `dompurify` (XSS via la suppression du hook `IN_PLACE` - à prioriser malgré la sévérité "modérée" puisque ce projet utilise DOMPurify pour la sanitization), `postcss-selector-parser`. La plupart réparables **sans rupture** via `npm audit fix`.
- Point annexe trouvé en creusant : `flowbite-vue@0.2.3` log déjà un avertissement `EBADENGINE` en CI (`required: node >=22.12.0`, la CI tourne sous Node 20) - toute montée de version de ce paquet devra aussi traiter/revisiter la version Node de la CI.

**À construire :**
- Scinder en deux passes : (1) `npm audit fix` pour les fixes sans rupture (axios, vue/server-renderer, source-map-js, js-yaml, dompurify, la plupart des modérées) - risque faible, à livrer en premier ; (2) une revue dédiée pour chaque fix cassant (`vitest` 2→5, `tailwindcss` 3→4, `flowbite-vue` 0.2.3→0.0.7) - vérifier l'usage réel de l'API dans `frontend/src/` avant de monter/descendre de version, le fix de `flowbite-vue` étant une régression qui supprime probablement des fonctionnalités en cours d'utilisation.
- Relancer `npm audit --audit-level=critical` (le seuil bloquant en CI) après chaque passe pour confirmer.
- Décider de la version Node pour les jobs CI frontend en touchant à `flowbite-vue` (actuellement Node 20, le paquet demande >=22.12).

---

## Épic 9 : Données géographiques & zones administratives

### 9.1 Framework de normalisation multi-pays pour les zones administratives 🔧 🟡 `XL`

**État (2026-09-15) :** implémentation terminée pour la France (métropolitaine) et l'Italie,
répartie sur deux dépôts : `geo_data` (pipeline de normalisation, `feat/geo-data-normalization`,
mergée) et le côté consommateur de ce dépôt (index spatial, validation à l'upload, vérification
de non-régression FR, `feat/geo-data-normalization`, mergée). La production tourne encore sur les
données legacy de `seed_zones.py` tant que les étapes VPS du plan
(`docs/superpowers/plans/2026-09-14-geo-data-normalization-plan.md`, "VPS actions") n'ont pas été
exécutées - étapes confiées à l'utilisateur, pas d'accès SSH depuis ici. Les 5 régions d'outre-mer
françaises (Guadeloupe, Martinique, Guyane, La Réunion, Mayotte) sont hors périmètre de cette
migration et perdent leur couverture géométrique une fois le nouvel export uploadé (documents
conservés, non supprimés).

**Contexte :** Le seeding des zones administratives (`administrative_zones`) ne couvre aujourd'hui que la France, via un pipeline dédié (`scripts/seed_zones.py` + `config/geo_sources.yml`) qui consomme des fichiers source INSEE bruts (propriété `code` = numéro de région/département nu, sans préfixe pays). L'exploration de nouveaux pays (Allemagne, Espagne, Royaume-Uni) montre que les sources externes envisagées (`geoBoundaries`, `geonames`) ne sont pas uniformes d'un pays à l'autre :

- **Allemagne :** `geoBoundaries` fournit un champ `shapeISO` directement exploitable (`DE-BW`, etc.)
- **Espagne :** `shapeISO` est cassé dans `geoBoundaries` (valeur `"ESP"` identique sur les 19 régions) — nécessite une jointure par nom avec les codes `geonames`
- **Royaume-Uni :** le niveau ADM1 de `geoBoundaries` ne compte que 4 entités (nations), trop grossier pour servir de niveau "région" — le niveau ADM2 (~185 comtés/unitary authorities) est plus pertinent
- **France :** fichiers source INSEE déjà récupérés entre-temps, structure propre à l'INSEE, à intégrer ou non dans ce nouveau pipeline (voir périmètre ci-dessous)

Le format de sortie normalisé attendu par l'endpoint d'upload de zones (`geo_admin_service.py::upload_zone_level`) est fixé par `~/projets/geo_json/CONTRACT.md` (`code` préfixé pays, `feature_code` brut, `nom`, `parent_code`, `bbox`).

**Conception envisagée lors du brainstorming (à raffiner à l'implémentation) :**
- Un wrapper de normalisation unique, indépendant de tout pays, qui gère le calcul du `bbox` (Shapely), le préfixage du `code`, la résolution géométrique du `parent_code`, et l'écriture au format `CONTRACT.md`
- Un profil déclaratif par pays (chemins de fichiers source, alias de noms pour les jointures, etc.) qui sélectionne un *handler*
- Des handlers réutilisables entre pays plutôt qu'un handler par pays : `geoboundaries_direct` (DE), `geonames_join` (ES), `admin2_as_region` (GB), et potentiellement `insee_source` (FR) si la migration est décidée
- Interface commune des handlers : retourner des tuples `(feature_code, nom, géométrie, parent_feature_code)` par niveau — le wrapper se charge du reste, de façon identique quel que soit le handler

**Éléments à couvrir lors de la préparation (avant implémentation) :**
- Gestion des différentes sources (`geoBoundaries`, `geonames`, INSEE)
- Normalisation des codes zone (préfixage pays, gestion des cas de jointure par nom avec table d'alias)
- Gestion de la synchronisation des fichiers normalisés avec les dossiers externes côté serveur (déploiement)
- Décision de périmètre : migrer la France vers ce framework (handler `insee_source`) ou la laisser indéfiniment sur `seed_zones.py`

**Point de vigilance identifié pendant la conception :** `geo_admin_service.py::upload_zone_level` (ligne 139) lit actuellement `feature_code` depuis `props["code"]` au lieu de `props["feature_code"]`, ce qui produirait des codes zone doublement préfixés (`FR-FR-84`) pour tout fichier réellement conforme à `CONTRACT.md`. Masqué par le fixture de test actuel (`_feature()` dans `test_geo_admin_service.py`, qui met la même valeur dans `code` et `feature_code`). Non traité ici (bugs suivis hors dépôt), mais bloquant pour cette fonctionnalité — à corriger avant tout upload réel de fichiers normalisés.

**Dépendances :** `CONTRACT.md` (`~/projets/geo_json/`), scripts `download_geoboundaries.py` / `download_geonames.py` (`~/projets/geo_data/`).

---

## Synthèse par priorité

### 🔴 Critique, à traiter en premier

| # | Fonctionnalité | Épic | Taille |
|---|----------------|------|--------|
| 1 | Reset de mot de passe | 1.1 | M |
| 2 | Import GPX asynchrone | 2.1 | XL |
| 3 | Page Progression (frontend) | 3.1 | L |
| 4 | Page Targets (frontend) (🔧 vue globale faite, vue par challenge restante) | 3.2 | L |
| 5 | ~~Tests API backend~~ ✅ fait | 7.1 | L |
| 6 | Logging structuré | 7.4 | M |
| 7 | Séparation config dev/prod | 8.1 | M |
| 8 | ~~HTTPS en production~~ ✅ fait | 8.4 | M |

### 🟠 Haute, sprint suivant

| # | Fonctionnalité | Épic | Taille |
|---|----------------|------|--------|
| 9 | Validation GPX avant traitement | 2.2 | S |
| 10 | Page recherche par filtre (frontend) | 2.3 | L |
| 11 | Email notification challenge complété | 5.2 | S |
| 12 | Export GPX d'un challenge | 6.1 | M |
| 13 | ~~Coverage ≥ 60%~~ ✅ fait (90%/95% en CI) | 7.2 | M |
| 14 | ~~Rate limiting auth~~ ✅ fait | 7.5 | S |
| 15 | Tests frontend (Vitest + Playwright) (🔧 Vitest fait, Playwright pas en CI) | 7.7 | L |
| 16 | Healthchecks Docker Compose (🔧 prod fait, dev partiel) | 8.2 | M |
| 17 | ~~CI/CD : Tests avant merge~~ ✅ fait | 8.3 | M |
| 18 | Vulnérabilités des dépendances npm frontend (`npm audit`, 2 critiques) | 8.8 | L |

### 🟡 Normale, backlog moyen terme

| # | Fonctionnalité | Épic | Taille |
|---|----------------|------|--------|
| 19 | Sync UserChallenges (finaliser) | 1.2 | M |
| 20 | Batch PATCH challenges (valider) | 1.3 | S |
| 21 | Support streaming GPX | 2.4 | M |
| 22 | Évaluation auto après import | 3.3 | M |
| 23 | Clustering carte (🔧 client fait, MapDemo + clustering serveur restants) | 4.1 | M |
| 24 | Carte des targets | 4.3 | S |
| 25 | ~~Health check SMTP réel~~ ✅ fait | 5.4 | S |
| 26 | Statistiques avancées | 6.2 | L |
| 27 | Recherche full-text caches (🔧 recherche fonctionnelle, scoring pertinence restant) | 6.3 | S |
| 28 | Tests d'intégration challenges | 7.3 | M |
| 29 | ~~Security headers HTTP~~ ✅ fait | 8.5 | S |
| 30 | Automatisation build_date CI | 8.6 | S |
| 31 | ~~Framework de normalisation multi-pays (zones admin)~~ 🔧 code mergé, upload VPS en attente | 9.1 | XL |

### 🟢 Nice-to-have, long terme

| # | Fonctionnalité | Épic | Taille |
|---|----------------|------|--------|
| 32 | ~~Logout avec invalidation serveur~~ ✅ fait | 1.4 | M |
| 33 | Suggestions de challenges | 3.4 | L |
| 34 | Heatmap des trouvailles | 4.2 | M |
| 35 | Notifications in-app | 5.3 | L |
| 36 | Métriques Prometheus | 7.6 | S |
| 37 | Logs centralisés production | 8.7 | L |
