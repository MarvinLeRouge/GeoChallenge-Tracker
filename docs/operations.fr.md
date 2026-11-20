🇫🇷 Version française | [🇬🇧 English version](operations.md)

---

# Guide d'exploitation : GeoChallenge Tracker

**Date de création :** 2026-09-02
**Type :** Référence opérationnelle, maintenue à jour au fil de l'évolution du périmètre déploiement/maintenance
**Périmètre :** Déploiement (dev et prod), sauvegarde et restauration, maintenance de routine, réponse aux incidents

> Ce document couvre *comment faire fonctionner le système*, pas *pourquoi il est construit ainsi* (voir [`docs/adr/`](adr/) pour le "pourquoi" derrière Traefik, le rate limiting, etc.), ni *comment installer un environnement de dev local from scratch* (voir la section "Installation & Launch" du [`README.md`](../README.md) racine et [`docs/guides/`](guides/) pour cela).

---

## Déploiement

### Dev

Couvert par le [`README.md`](../README.md) racine : `docker compose up --build`, backend sur `:8000`, frontend sur `:5173`. Non dupliqué ici.

### Prod : pipeline

Les déploiements en prod sont entièrement automatisés via GitHub Actions, en deux workflows enchaînés :

1. **CI** (`.github/workflows/ci.yml`) s'exécute sur chaque PR et chaque push sur `main`, filtrée par partie : backend lint, vérification des types, tests unitaires, tests d'intégration sur un MongoDB jetable et `pip-audit` ; frontend lint, vérification des types, build, tests unitaires, tests e2e Playwright et `npm audit`. Le job `CI status` les agrège et constitue le check obligatoire sur `main`.
2. **Build, Push & Deploy** (`.github/workflows/build-push-deploy.yml`) s'exécute automatiquement une fois la CI réussie sur `main` (déclencheur `workflow_run`), ou peut être déclenché manuellement (`workflow_dispatch`), ce qui court-circuite la validation CI pour les hotfix, rollbacks ou redéploiements.
   - **Build & push** : les images Docker backend et frontend sont construites et poussées sur GHCR, chacune taguée à la fois `sha-<7-caractères-du-commit>` et `latest` (`ghcr.io/marvinlerouge/geochallenge-tracker/{backend,frontend}`).
   - **Deploy** : une étape SSH sur le serveur de production récupère `docker-compose.prod.yml` et la config nginx des tuiles directement depuis `raw.githubusercontent.com`, épinglés sur le SHA de commit exact déployé, puis exécute `docker compose pull` suivi de `docker compose up -d --remove-orphans`.

### Prod : topologie

Le routage est basé sur le chemin, sur un domaine unique via Traefik (TLS via Let's Encrypt) : `gc-tracker.marvinlerouge.dev/api/*` vers le backend (préfixe retiré avant d'atteindre FastAPI), `gc-tracker.marvinlerouge.dev/tiles/*` vers le service nginx des tuiles, tout le reste vers le frontend. Voir [ADR 0004](adr/0004-traefik-reverse-proxy-with-harmonized-dev-prod-routing.md) pour le pourquoi de ce choix.

### Prod : disposition sur le serveur

Sur le serveur de déploiement, deux répertoires sous `/home/mlr/marvinlerouge.dev/gc-tracker/` (chemins repris directement de `build-push-deploy.yml`) :

- `compose/` : contient uniquement le `docker-compose.yml` déployé (récupéré à neuf depuis `docker-compose.prod.yml` à chaque déploiement, jamais édité à la main).
- `shared/` : contient tout ce qui doit survivre à un redéploiement : `env/app.env` et `env/secrets.env` (absents du dépôt, voir plus bas), `backups/` (monté dans le conteneur backend sur `/backups`), `uploads/` (monté sur `/app/uploads`), et `ops/nginx/` (config des tuiles, récupérée à neuf comme le fichier compose).

### Prod : fichiers d'environnement

Les conteneurs reçoivent leur configuration uniquement via `env_file` dans `docker-compose.prod.yml` ; le fichier compose n'interpole rien depuis un fichier (le domaine est écrit dans les règles Traefik, `IMAGE_BACKEND` / `IMAGE_FRONTEND` sont fournis par le workflow de déploiement, avec les images `:latest` par défaut pour que les commandes `docker compose` manuelles dans `compose/` fonctionnent sans eux). Le développement local garde le `.env` racine unique.

| Fichier sur le VPS | Chargé par | Contenu | Modèle |
|---|---|---|---|
| `shared/env/app.env` | backend, frontend | réglages non secrets (identité de l'app, CORS, URL du frontend, expéditeur mail, sauvegardes, limites d'upload, élévation, `SENTRY_ENVIRONMENT`) | [`docker/env/app.env.example`](../docker/env/app.env.example) |
| `shared/env/secrets.env` | backend, chargé en dernier donc prioritaire | chaque sujet contenant un secret, regroupé en entier : `MONGODB_*`, `JWT_*`, `ADMIN_*`, `SMTP_*`, DSN Sentry | [`docker/env/secrets.env.example`](../docker/env/secrets.env.example) |

Les deux fichiers sont en `chmod 600` et jamais commités. Le workflow de déploiement crée `shared/env/` s'il manque, mais n'écrit aucun des deux fichiers.

### Prod : rollback

Comme `build-push-deploy.yml` tague chaque image à la fois `sha-<7-caractères>` et `latest`, et que GHCR ne purge pas les anciens tags, le chemin de rollback direct consiste à redéployer une image plus ancienne précise sur le serveur, depuis `compose/` : `IMAGE_BACKEND=ghcr.io/marvinlerouge/geochallenge-tracker/backend:sha-xxxxxxx IMAGE_FRONTEND=ghcr.io/marvinlerouge/geochallenge-tracker/frontend:sha-xxxxxxx docker compose up -d`. Relancer manuellement le workflow de déploiement (`workflow_dispatch`) sur une référence plus ancienne est l'équivalent piloté par le pipeline.

---

## Sauvegarde et restauration

Toutes les routes de sauvegarde/restauration vivent sous `/maintenance` et nécessitent un compte admin (tout le routeur est protégé par `require_admin`).

- **`POST /maintenance/db_full_backup`** : dumpe toutes les collections dans un unique fichier JSON zippé et horodaté sous `/backups/full_backup`, monté sur `shared/backups/` côté hôte, donc survit aux redéploiements et à la recréation des conteneurs.
- **`GET /maintenance/db_backups`** : liste tous les fichiers de sauvegarde, cleanup et full.
- **`GET /maintenance/backups/{filepath}`** : télécharge un fichier de sauvegarde précis.
- **`POST /maintenance/db_full_restore/{filename}`** : restaure depuis un fichier de sauvegarde. Deux paramètres contrôlent le rayon d'impact :
  - `dry_run` (par défaut `True`) : prévisualise la restauration (compte ce qui serait inséré) sans rien écrire.
  - `drop_existing` (par défaut `False`) : vide une collection avant d'y restaurer.
  - Un appel réellement destructeur (`dry_run=False` **et** `drop_existing=True`) ne peut pas s'exécuter en une seule requête : le premier appel (sans `key`) se contente de valider le fichier de sauvegarde et renvoie une `confirmation_key` valable 10 minutes ; la restauration ne s'exécute qu'une fois cette même clé resoumise via `?key=...`. Toute combinaison non destructrice s'exécute immédiatement, sans clé nécessaire.

**Usage pratique en incident :** toujours appeler `db_full_restore` avec `dry_run=True` en premier pour confirmer que le fichier de sauvegarde est bien celui attendu (noms de collections, nombre de documents) avant d'envisager une restauration destructrice.

---

## Maintenance de routine

Également sous `/maintenance`, réservé aux admins :

- **`GET /maintenance/db_cleanup`** : scanne toutes les collections (dans l'ordre de dépendance, les plus référencées en premier) à la recherche de documents orphelins (références pendantes vers des parents supprimés) et renvoie un rapport plus une `confirmation_key` valable 10 minutes. Lecture seule, ne modifie rien.
- **`DELETE /maintenance/db_cleanup?key=...`** : exécute le nettoyage trouvé par l'appel `GET` correspondant, en sauvegardant d'abord chaque document supprimé dans un zip horodaté sous `/backups/db_cleanup`.
- **`DELETE /maintenance/expired-verifications`** : supprime les codes de vérification d'email expirés.

### Logs

Le backend écrit chaque ligne de log sur stderr (`docker logs`), un objet JSON par ligne, via `structlog` (`configure_logging()` dans `backend/app/core/observability.py`) : `timestamp` (UTC), `level`, `logger`, `event`, plus les champs de l'appel et la traceback dans `exception`. Les loggers `logging.getLogger(...)` existants passent par la même sortie. `LOG_FORMAT=console` donne des lignes lisibles à la place (défaut quand stderr est un terminal), `LOG_LEVEL` règle le niveau (défaut `info`).

Chaque requête produit une ligne `request_handled` (`method`, `path`, `status`, `duration_ms` ; niveau ERROR pour un 5xx), écrite par `backend/app/core/request_logging.py`. La query string, les headers et le body ne sont jamais logués, d'où la désactivation de l'access log d'uvicorn : il gardait les query strings, comme le code de vérification d'email.

Les fichiers ci-dessous restent écrits en parallèle.

Trois loggers écrivent des fichiers à rotation quotidienne, purgés automatiquement après 30 jours : `generic.log` (INFO et plus, `geocaching.generic`), `errors.log` (ERROR et plus, `geocaching.errors`), `security.log` (INFO et plus, `geocaching.security`, événements liés à la sécurité comme les échecs de connexion).

**Point d'attention :** ces fichiers sont écrits dans un répertoire relatif `logs/` à l'intérieur du conteneur backend (`backend/app/core/logging_config.py`), qui n'est **pas** monté sur l'hôte dans `docker-compose.prod.yml` (contrairement à `/backups` et `/app/uploads`). En pratique, l'historique des logs ne survit pas à une recréation de conteneur ou un redéploiement aujourd'hui ; seuls les sauvegardes et les uploads sont actuellement persistés ainsi.

### Suivi des erreurs (Sentry)

Les erreurs non gérées (500 du backend, erreurs Vue et JavaScript du frontend) sont remontées à Sentry, région UE, un projet par côté (`geochallenge-backend`, `geochallenge-frontend`). Les erreurs client (401, 404, 422, 429) ne sont pas remontées. Seules les stack traces sont envoyées : aucun corps de requête, en-tête, cookie, query string, donnée utilisateur, prop de composant, breadcrumb ni variable locale (`dataCollection` plus un filtre `beforeSend` / `before_send` ; les URL de page ne gardent que leur chemin). Chaque 500 est aussi loggée avec sa traceback (`log.exception` dans `general_exception_handler`).

Le suivi est désactivé quand les DSN sont vides.

| Variable | Lue par | En local | En production |
|---|---|---|---|
| `SENTRY_BACKEND_DSN` | backend, au démarrage (`app/core/observability.py`) | `.env` | `secrets.env` du serveur |
| `SENTRY_FRONTEND_DSN` | backend, au démarrage (liste blanche du relais) | `.env` | `secrets.env` du serveur |
| `SENTRY_ENVIRONMENT` | backend (défaut `development`) | `.env` | `app.env` du serveur (`production`) |
| `VITE_SENTRY_DSN` | frontend, au build (`src/observability.ts`) | depuis `SENTRY_FRONTEND_DSN` dans `docker-compose.yml` | secret GitHub, argument de build dans `build-push-deploy.yml` |
| `VITE_SENTRY_ENVIRONMENT` | frontend, au build (défaut `development`) | depuis `SENTRY_ENVIRONMENT` dans `docker-compose.yml` | `production`, défini par `build-push-deploy.yml` |

Le backend lit ces variables dans l'environnement du processus, pas dans les settings de l'app : hors Docker, il faut les exporter.

**Relais.** Les bloqueurs de pub (uBlock Origin, protection contre le pistage de Firefox) bloquent les requêtes du navigateur vers `*.sentry.io`. Le navigateur envoie donc ses events à sa propre origine, sur `/api/<hash de son DSN>`, et le backend les transmet à Sentry (`app/api/routes/sentry_tunnel.py`). La CSP reste `connect-src 'self'`.

- Le chemin est un hash du DSN frontend, calculé de la même façon des deux côtés. Le secret GitHub `VITE_SENTRY_DSN` et le `SENTRY_FRONTEND_DSN` du serveur doivent être identiques au caractère près : sinon chaque event frontend finit en 404, sans bruit. Le backend logue un warning au démarrage quand un seul des deux `SENTRY_BACKEND_DSN` / `SENTRY_FRONTEND_DSN` est défini.
- Seules les enveloppes de `SENTRY_FRONTEND_DSN` sont transmises (les autres reçoivent 403, un corps mal formé 400, un Sentry injoignable 502). Les cookies, le `Referer` et l'IP du client ne sont pas transmis.
- La route n'a pas de limite de débit propre : un abus ne peut que consommer le quota du projet Sentry, que Sentry limite lui-même.

**Mise en place, une seule fois :** dans chaque projet Sentry, *Settings*, *Security & Privacy* : activer *Data Scrubber* et *Use Default Scrubbers*, et *Prevent Storing of IP Addresses*. Puis redéployer.

**Vérifier en production :** depuis un navigateur **sans** extensions, lancer `setTimeout(() => { throw new Error('sentry check') }, 0)` dans la console et vérifier l'issue sous `environment: production`. Puis recommencer avec uBlock / la protection contre le pistage activés, pour valider le relais (un POST vers `/api/<hash>` qui répond 200, rien vers `sentry.io`).

---

## Réponse aux incidents

- **Un service semble down :** `docker compose ps` sur le serveur de déploiement pour vérifier l'état de santé des conteneurs ; le healthcheck du backend appelle `GET /health`, celui du service tuiles appelle `GET /tiles/_health.png`. `docker compose logs <service>` pour la sortie récente (sous réserve du point d'attention ci-dessus sur les logs : uniquement ce qui est présent dans le conteneur en cours d'exécution, rien d'avant la dernière recréation).
- **Un déploiement a cassé quelque chose :** voir Rollback plus haut, redéployer le tag d'image `sha-<7-caractères>` précédent.
- **Des données doivent être restaurées :** voir Sauvegarde et restauration plus haut, toujours en dry-run d'abord.
