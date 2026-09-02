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

1. **CI** (`.github/workflows/ci.yml`) s'exécute à chaque push/PR sur `main` : tests backend, tests frontend, lint, vérification des types.
2. **Build, Push & Deploy** (`.github/workflows/build-push.yml`) s'exécute automatiquement une fois la CI réussie sur `main` (déclencheur `workflow_run`), ou peut être déclenché manuellement (`workflow_dispatch`), ce qui court-circuite la validation CI pour les hotfix, rollbacks ou redéploiements.
   - **Build & push** : les images Docker backend et frontend sont construites et poussées sur GHCR, chacune taguée à la fois `sha-<7-caractères-du-commit>` et `latest` (`ghcr.io/marvinlerouge/geochallenge-tracker/{backend,frontend}`).
   - **Deploy** : une étape SSH sur le serveur de production récupère `docker-compose.prod.yml` et la config nginx des tuiles directement depuis `raw.githubusercontent.com`, épinglés sur le SHA de commit exact déployé, puis exécute `docker compose pull` suivi de `docker compose up -d --remove-orphans`.

### Prod : topologie

Le routage est basé sur le chemin, sur un domaine unique via Traefik (TLS via Let's Encrypt) : `${DOMAIN}/api/*` vers le backend (préfixe retiré avant d'atteindre FastAPI), `${DOMAIN}/tiles/*` vers le service nginx des tuiles, tout le reste vers le frontend. Voir [ADR 0004](adr/0004-traefik-reverse-proxy-with-harmonized-dev-prod-routing.md) pour le pourquoi de ce choix.

### Prod : disposition sur le serveur

Sur le serveur de déploiement, deux répertoires (chemins repris directement de `build-push.yml`) :

- `.../gc-tracker/compose/`: contient le `docker-compose.yml` déployé (récupéré à neuf depuis `docker-compose.prod.yml` à chaque déploiement, jamais édité à la main).
- `.../gc-tracker/shared/`: contient tout ce qui doit survivre à un redéploiement : `env/app.env` et `env/secrets.env` (absents du dépôt), `backups/` (monté dans le conteneur backend sur `/backups`), `uploads/` (monté sur `/app/uploads`), et `ops/nginx/` (config des tuiles, récupérée à neuf comme le fichier compose).

### Prod : rollback

Comme `build-push.yml` tague chaque image à la fois `sha-<7-caractères>` et `latest`, et que GHCR ne purge pas les anciens tags, le chemin de rollback direct consiste à redéployer une image plus ancienne précise sur le serveur : fixer `IMAGE_TAG=sha-xxxxxxx` et relancer `docker compose --env-file ../shared/env/app.env up -d` avec ce tag. Relancer manuellement le workflow de déploiement (`workflow_dispatch`) sur une référence plus ancienne est l'équivalent piloté par le pipeline.

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

Trois loggers écrivent des fichiers à rotation quotidienne, purgés automatiquement après 30 jours : `generic.log` (INFO et plus, `geocaching.generic`), `errors.log` (ERROR et plus, `geocaching.errors`), `security.log` (INFO et plus, `geocaching.security`, événements liés à la sécurité comme les échecs de connexion).

**Point d'attention :** ces fichiers sont écrits dans un répertoire relatif `logs/` à l'intérieur du conteneur backend (`backend/app/core/logging_config.py`), qui n'est **pas** monté sur l'hôte dans `docker-compose.prod.yml` (contrairement à `/backups` et `/app/uploads`). En pratique, l'historique des logs ne survit pas à une recréation de conteneur ou un redéploiement aujourd'hui ; seuls les sauvegardes et les uploads sont actuellement persistés ainsi.

---

## Réponse aux incidents

- **Un service semble down :** `docker compose ps` sur le serveur de déploiement pour vérifier l'état de santé des conteneurs ; le healthcheck du backend appelle `GET /health`, celui du service tuiles appelle `GET /tiles/_health.png`. `docker compose logs <service>` pour la sortie récente (sous réserve du point d'attention ci-dessus sur les logs : uniquement ce qui est présent dans le conteneur en cours d'exécution, rien d'avant la dernière recréation).
- **Un déploiement a cassé quelque chose :** voir Rollback plus haut, redéployer le tag d'image `sha-<7-caractères>` précédent.
- **Des données doivent être restaurées :** voir Sauvegarde et restauration plus haut, toujours en dry-run d'abord.
