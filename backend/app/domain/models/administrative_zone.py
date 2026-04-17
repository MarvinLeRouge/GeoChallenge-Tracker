# backend/app/domain/models/administrative_zone.py
# Administrative zone model (regions, departments…) used for choropleth map.

from __future__ import annotations

from app.core.bson_utils import MongoBaseModel


class AdministrativeZone(MongoBaseModel):
    """Administrative zone document stored in `administrative_zones` collection.

    Description:
        Represents a geographic subdivision (region, department…) used to group
        caches on the choropleth map. GeoJSON geometry is NOT embedded — it lives
        in a FeatureCollection file referenced by `geojson_file`.

    Attributes:
        code (str): Unique zone code, e.g. "FR-38", "FR-84".
        country_code (str): ISO country code, e.g. "FR".
        level (int): Administrative level — 1 = region, 2 = department.
        name (str): Display name, e.g. "Isère".
        parent_code (str | None): Code of the parent zone (level 1 for a level-2 zone).
        geojson_file (str): Relative path to the FeatureCollection file, e.g. "FR/departements.geojson".
        feature_code (str): Code of this feature within the FeatureCollection (e.g. "38").
        bbox (list[float]): Bounding box [lon_min, lat_min, lon_max, lat_max].
    """

    code: str
    country_code: str
    level: int
    name: str
    parent_code: str | None = None
    geojson_file: str
    feature_code: str
    bbox: list[float]
