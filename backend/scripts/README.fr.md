🇫🇷 Version française | [🇬🇧 English version](README.md)

---

# Scripts de données géographiques

## Vue d'ensemble

Ce répertoire contient les scripts de setup one-shot pour la carte choroplèthe.

> Les scripts de gestion de la base de données de test (`duplicate_db_for_tests.py`, `copy_db_structure.py`) sont documentés séparément dans [`backend/tests/utils/README.fr.md`](../tests/utils/README.fr.md), là où ils se trouvent réellement.

---

## Scripts de données géographiques (carte choroplèthe)

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

- Upsert par `code` : relançable sans effet
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
