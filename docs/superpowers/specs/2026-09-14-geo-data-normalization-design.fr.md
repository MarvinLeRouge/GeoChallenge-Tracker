🇫🇷 Version française | [🇬🇧 English version](2026-09-14-geo-data-normalization-design.md)

---

# Design : normalisation multi-pays des zones administratives (Epic 9.1)

**Créé le :** 2026-09-14
**Statut :** validé par l'utilisateur, en attente du plan d'implémentation
**Lié à :** `docs/roadmap.md` Epic 9.1, `docs/superpowers/plans/2026-09-11-zones-explorer-step5.md`

## Contexte

GeoChallenge-Tracker stocke les limites des zones administratives (niveau région/département, niveaux 0/1/2) dans la collection `administrative_zones`, utilisée pour déterminer à quelles zones appartient une cache. Aujourd'hui, seule la France est renseignée (114 documents), via un pipeline legacy, spécifique à la France (`backend/scripts/seed_zones.py`). Un chemin d'upload admin plus récent, conforme au CONTRACT.md, existe déjà (`POST /admin/geo/{country_code}/upload`, `geo_admin_service.py`) mais n'a jamais servi pour un vrai pays et contient un bug confirmé.

Trois sources de données locales sont disponibles sous `~/projets/geo_data/data/` : `insee` (tables de référence officielles françaises, sans géométrie), `geonames` (tables de codes admin1/admin2 mondiales, certains pays ayant des codes obsolètes, ex. la France, pré-fusion des régions de 2016), et `geoboundaries` (géométries des limites administratives mondiales, par ISO3/niveau ADM, archives zip).

Ce document couvre le design d'un framework de normalisation générique et réutilisable, produisant des fichiers de zones administratives prêts à l'emploi pour n'importe quel pays, ainsi que les changements côté GeoChallenge-Tracker nécessaires pour les consommer en toute sécurité.

## Objectifs

- Framework générique et réutilisable pour transformer les données brutes geoBoundaries/geonames/INSEE en fichiers de zones administratives normalisés, non limité à l'usage de GeoChallenge-Tracker.
- Migrer la France vers ce même pipeline générique (actuellement alimentée par un pipeline legacy à part), en vérifiant que le résultat correspond à la base actuelle de 114 documents avant tout remplacement.
- Corriger le bug confirmé `feature_code`/`code` dans `geo_admin_service.py::upload_zone_level`, bloquant pour tout upload réellement conforme au CONTRACT.md.
- Aucune nouvelle collection MongoDB nécessaire : `administrative_zones` accueille déjà les nouveaux pays de façon additive, respectant la contrainte de ne pas impacter les collections existantes.
- Liste d'actions VPS concrète (l'utilisateur n'a pas d'accès SSH direct et exécute les commandes lui-même) et un plan de tests, incluant l'utilisation des vraies trouvailles de géocaching de l'utilisateur en Italie comme cas de validation de bout en bout.

## État des lieux (constats de l'exploration)

- **Deux pipelines d'ingestion incompatibles** coexistent côté backend :
  - Legacy `seed_zones.py` + `backend/config/geo_sources.yml` : FR uniquement, source `france-geojson.gregoiredavid.fr` (**pas** `geo_data/insee`, malgré la présence de fichiers dans ce dossier), recalcule `bbox` et `parent_code` via Shapely (containment géométrique, avec repli sur le parent le plus proche) plutôt que de faire confiance aux valeurs de la source.
  - Nouveau `geo_admin_service.py::upload_zone_level` (déjà branché sur `POST /admin/geo/{country_code}/upload`) : valide selon les propriétés requises par le CONTRACT.md (`code`, `nom`, `feature_code`, `parent_code` au niveau 2, `bbox`), fait confiance aux valeurs précalculées du fichier. **Bug ligne 139** : lit `feature_code = str(props["code"])` au lieu de `props["feature_code"]`. Selon le CONTRACT.md, `code` est déjà la valeur préfixée (ex. `FR-84`), ce qui produit des codes doublés (`FR-FR-84`) pour tout fichier réellement conforme au contrat. Masqué par le fixture de test actuel (`_feature()` dans `test_geo_admin_service.py`), qui donne la même valeur à `code` et `feature_code`.
- **Base en production** (`administrative_zones`, 114 docs) : FR uniquement (18 régions + 96 départements), correctement préfixés (`FR-11`, ...), `geojson_file: "FR/regions.geojson"` (nommage legacy, pas `adm{level}.geojson`).
- **`caches.distinct('zones.country')` retourne `['FR']` uniquement** : aucune cache italienne en base aujourd'hui. Les trouvailles réelles "earth" et "tradi" de l'utilisateur en Italie n'y sont pas encore importées ; `get_missing_countries()` ne peut faire remonter l'Italie tant qu'elles n'y sont pas (fonctionnalité d'import de caches existante, séparée, hors périmètre ici).
- **`geo_data_dir` (`data/admin`, par défaut) n'est pas un volume persistant** dans `docker-compose.prod.yml`, contrairement à `/backups` et `/app/uploads`. Les fichiers FR actuels n'existent que parce qu'ils sont commités dans git et intégrés à l'image Docker au build. Tout fichier écrit via l'endpoint d'upload admin en prod aujourd'hui serait perdu au prochain redéploiement.
- **`geo_data` est un clone git d'un paquet tiers** (`stefangabos/world_countries`, CC-BY-SA 4.0, `origin` pointe directement dessus). Tous les ajouts custom (`download_geoboundaries.py`, `download_geonames.py`, `data/insee`, `data/geonames`, `data/geoboundaries`) sont actuellement non suivis, sans historique. Décision : ne plus considérer ce dossier comme un clone upstream mais comme un projet indépendant (attribution au paquet d'origine conservée en documentation), et ne plus pousser vers `origin` (renommé en `upstream` pour la traçabilité, lors de l'implémentation).
- **`geo_json` (projet de tooling dev-only séparé) est abandonné** au profit d'une consolidation dans `geo_data`. Analyse : `geo_json` ne contient aucun code d'implémentation (un seul "Initial commit", ni script ni test), uniquement de la documentation (`CLAUDE.md`, `CONTRACT.md`, `README.md`/`.fr.md`, `SOURCES.md`) et un échantillon FR brut récupéré manuellement, dupliquant des données déjà présentes dans `geo_data/data/geoboundaries/FRA`. Seuls le `CONTRACT.md` et le concept de suivi d'attribution `SOURCES.md` méritent d'être migrés ; le reste est remplacé par ce design.
- **Le `shapeISO` de geoBoundaries est directement exploitable pour la France** (`FR-IDF`, `FR-CVL`, ...), contrairement à l'hypothèse initiale de l'esquisse Epic 9.1 selon laquelle toute jointure hors `geoboundaries_direct` nécessitait geonames. Cependant, pour conserver les codes exacts déjà en base (`FR-11`, format numérique INSEE), la France nécessite une jointure entre la géométrie geoBoundaries (par nom) et les codes/hiérarchie officiels INSEE, pas un mapping direct via `shapeISO`. geonames n'est pas utilisé pour la France : ses codes admin1 sont obsolètes (pré-fusion des régions de 2016, ex. `FR.84 Rhône-Alpes`, `FR.27 Bourgogne`), ce qui les rend également peu fiables pour la jointure hiérarchique.

## Décision de consolidation : `geo_data` comme dossier unique de tooling

Toute l'acquisition de données sources (existante) et la normalisation (nouvelle) vivent dans `~/projets/geo_data`, remplaçant entièrement `geo_json`. Justification : `geo_data` contient déjà les données brutes réellement téléchargées pour les trois sources (couverture mondiale confirmée pour geoBoundaries, ex. `FRA`, `DEU`, `ESP`, `ITA`, `GBR`), les scripts de téléchargement y vivent déjà, et d'autres futurs scripts (sans rapport avec GeoChallenge-Tracker) pourront réutiliser les mêmes données sources - centraliser la logique de normalisation ici évite de dupliquer ou re-télécharger des données dans un second projet vide.

### Structure de dossiers

```
geo_data/
  docs/                                 (existant, doc du paquet upstream, intouché)
  data/
    insee/, geonames/, geoboundaries/    (sources brutes existantes, inchangées)
    normalized/                          (NOUVEAU : zones résolues génériques par pays, indépendantes du consommateur)
  scripts/
    download_geoboundaries.py, download_geonames.py   (déplacés ici, inchangés sinon)
    README.md                            (vue d'ensemble de tous les scripts du dossier)
    docs/
      CONTRACT.md                        (migré depuis geo_json)
      SOURCES.md                         (migré et élargi : CC-BY-SA 4.0 world_countries, Licence Ouverte INSEE, CC-BY 4.0 geonames/geoBoundaries)
    normalize/
      common/
        handlers/       geoboundaries_direct.py, geonames_join.py, insee_geoboundaries_join.py, admin2_as_region.py
        countries/       fr.py, it.py, (de.py, es.py, gb.py au besoin plus tard)
        pipeline.py
      gctracker/
        export_contract.py
    tests/
```

### Interface des handlers et orchestration

- `ZoneRecord` (dataclass générique, indépendante du projet) : `feature_code`, `name`, `geometry` (GeoJSON), `parent_feature_code` (optionnel, niveau 2 uniquement).
- `NormalizationHandler` : interface commune, `resolve(level, country_config) -> list[ZoneRecord]`. Implémentations : `geoboundaries_direct` (utilise `shapeISO` directement), `geonames_join` (jointure par nom sur les tables de codes geonames), `insee_geoboundaries_join` (jointure par nom entre la géométrie geoBoundaries et les codes/hiérarchie INSEE, utilisée pour la France), `admin2_as_region` (utilise l'ADM2 de geoBoundaries comme niveau "région" quand l'ADM1 est trop grossier, ex. Royaume-Uni).
- `CountryConfig` (un module par pays sous `countries/`) : code ISO2, code ISO3 (chemins geoBoundaries), handler choisi par niveau, chemins des fichiers sources, table d'alias de noms optionnelle pour les jointures approximatives.
- `pipeline.py` : pour un pays donné, pour chaque niveau, appelle le handler configuré et résout `parent_feature_code` **via les clés de jointure propres à la source** (ex. le champ `DEP.REG` d'INSEE) plutôt que par containment géométrique Shapely, évitant ainsi le point faible du pipeline legacy. Sortie : `data/normalized/{cc}/adm{level}.geojson`, GeoJSON générique avec des propriétés minimales (`feature_code`, `name`, `parent_feature_code`), réutilisable en dehors de ce projet.
- `gctracker/export_contract.py` : consomme les fichiers normalisés génériques, calcule le `bbox` (Shapely), préfixe les codes (`{cc}-{feature_code}`), renomme les propriétés au schéma exact du CONTRACT.md (`code`, `nom`, `feature_code`, `parent_code`, `bbox`), produisant des fichiers prêts à l'upload. Cela isole la mise en forme spécifique au CONTRACT.md de la logique réutilisable de jointure/résolution.

### Gestion git

`origin` de `geo_data` pointe actuellement vers le dépôt upstream `stefangabos/world_countries` ; tous les ajouts custom sont non suivis. Ce dossier sera désormais traité comme un projet indépendant (pas un fork suivi) : renommer `origin` en `upstream` (plus aucun push dessus), committer le tooling custom localement, et documenter l'attribution au paquet d'origine (CC-BY-SA 4.0) ainsi que celles d'INSEE (Licence Ouverte), geonames et geoBoundaries (CC-BY 4.0) dans `scripts/docs/SOURCES.md`.

## Changements côté GeoChallenge-Tracker

- **Correction du bug** : `geo_admin_service.py::upload_zone_level` doit lire `feature_code` depuis `props["feature_code"]` au lieu de `props["code"]`. Test de régression dédié utilisant un fixture où `code` et `feature_code` diffèrent (le fixture actuel masque le bug en les rendant identiques).
- **Validation défensive** : si le `feature_code` résolu commence déjà par `{country_code}-`, lever une `ValueError` explicite (double-préfixage détecté) plutôt que de produire silencieusement un code incorrect.
- **Volume persistant** : ajouter un bind-mount pour `geo_data_dir` (`/app/data/admin` dans le conteneur) dans `docker-compose.prod.yml`, ex. `../shared/geo-admin` côté hôte, à l'image de `/backups` et `/app/uploads`. Nécessite une migration ponctuelle des 3 fichiers FR existants (actuellement intégrés à l'image) vers ce volume avant/pendant le déploiement introduisant le montage, pour éviter un trou de service.
- **FR migrée** vers le nouveau pipeline générique (jointure INSEE/geoBoundaries), avec un contrôle de non-régression comparant la sortie du pipeline aux 114 documents actuellement en base (mêmes codes, noms, bbox équivalents) avant tout remplacement en base.

## Plan de tests

- Tests unitaires par handler (fixtures isolées), y compris les cas d'échec de jointure (nom absent de la table d'alias → erreur explicite plutôt qu'une correspondance hasardeuse).
- Tests unitaires pour le fix du bug et le garde-fou anti-double-préfixage dans `geo_admin_service.py`.
- Non-régression FR : script/test dédié comparant la sortie du nouveau pipeline aux 114 documents actuels de `administrative_zones`, exécuté et validé avant tout remplacement des données FR.
- Dry-run Italie (zéro risque DB) : exécuter le pipeline complet sur l'Italie, valider le résultat via `_validate_feature_collection` (contrôle de schéma seul, aucune écriture), confirmant que le pipeline générique produit un résultat conforme au contrat avant tout contact avec la base réelle.
- Upload réel Italie (optionnel, après le dry-run) : backup de `administrative_zones` au préalable (règle standard du projet pour les changements structurels), puis upload via l'endpoint admin en local (qui cible la même base Atlas que la prod) - purement additif, aucun document FR touché. Une fois fait, l'utilisateur pourra importer ses vraies trouvailles italiennes (earth + tradi) via la fonctionnalité d'import de caches existante de GeoChallenge-Tracker (hors périmètre ici) pour valider `get_missing_countries()` et la résolution cache→zone de bout en bout.

## Actions VPS (exécutées par l'utilisateur, pas d'accès SSH direct pour l'assistant)

1. Créer le dossier hôte pour le nouveau volume persistant (ex. `../shared/geo-admin`) avant de déployer le `docker-compose.prod.yml` mis à jour.
2. Copier une fois les 3 fichiers FR existants (`backend/data/admin/FR/*.geojson`) dans le nouveau volume, pour éviter un trou de service entre l'ancien répertoire intégré à l'image (supprimé) et le nouveau volume (initialement vide).
3. Déployer normalement (merge, pull, `docker compose up -d`).
4. Backup de `administrative_zones` (`mongodump` ciblé, comme déjà pratiqué pour `countries_backup_*`) avant le tout premier upload réel d'un nouveau pays.
5. Appeler l'endpoint d'upload admin (`POST /admin/geo/{cc}/upload`) en prod, niveau par niveau, une fois le dry-run local validé.

Commandes exactes à fournir dans le plan d'implémentation.

## Hors périmètre

- Configurations par pays au-delà de la France (migration) et de l'Italie (cas de validation) - Allemagne, Espagne, Royaume-Uni restent esquissés (Epic 9.1) mais non implémentés ici.
- Import des vraies trouvailles italiennes de l'utilisateur dans `caches`/`found_caches` - fonctionnalité existante, sans rapport avec ce travail de normalisation.
- Toute modification des collections de référence `countries`/`states`.
