"""Compares the new normalization pipeline's FR output against the live
`administrative_zones` documents, scoped to the 109 metropolitan zones this
migration covers (overseas regions are out of scope, see the implementation
plan's Global Constraints, and are skipped rather than reported as missing).

Usage (from `backend/`, matching this project's other one-shot scripts, e.g. assign_zones.py):
    python scripts/verify_fr_non_regression.py <exported_fr_dir>

Where <exported_fr_dir> is `~/projets/geo_data/data/gctracker_export/FR`
(Task 8's export_country output for FR).
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

BBOX_TOLERANCE = 1e-4

# INSEE REG codes for the 5 overseas regions - out of scope for this migration.
OVERSEAS_CODES = {f"FR-{code}" for code in ("01", "02", "03", "04", "06")}


def _bbox_close(a: list[float], b: list[float]) -> bool:
    return len(a) == len(b) == 4 and all(abs(x - y) <= BBOX_TOLERANCE for x, y in zip(a, b))


def compare_zones(live_docs: list[dict], exported_features: list[dict]) -> list[str]:
    """Compares live `administrative_zones` docs against exported CONTRACT.md features.

    Args:
        live_docs (list[dict]): `{"code", "name", "bbox"}` from `administrative_zones`.
        exported_features (list[dict]): GeoJSON features with `properties.code`,
            `properties.nom`, and a top-level `bbox`.

    Returns:
        list[str]: one human-readable diff per discrepancy found, empty if none.
            Overseas region codes present only in `live_docs` are silently skipped.
    """
    exported_by_code = {f["properties"]["code"]: f for f in exported_features}
    diffs = []

    for live in live_docs:
        code = live["code"]
        if code in OVERSEAS_CODES:
            continue
        exported = exported_by_code.get(code)
        if exported is None:
            diffs.append(f"{code}: missing from the exported output")
            continue
        if exported["properties"]["nom"] != live["name"]:
            diffs.append(
                f"{code}: name mismatch (live={live['name']!r}, "
                f"exported={exported['properties']['nom']!r})"
            )
        if not _bbox_close(exported["bbox"], live["bbox"]):
            diffs.append(
                f"{code}: bbox mismatch (live={live['bbox']}, exported={exported['bbox']})"
            )

    return diffs


async def _load_live_docs() -> list[dict]:
    from app.db.mongodb import get_collection

    collection = await get_collection("administrative_zones")
    cursor = collection.find({"country_code": "FR"})
    return [doc async for doc in cursor]


def _load_exported_features(exported_fr_dir: Path) -> list[dict]:
    features = []
    for level in (1, 2):
        payload = json.loads((exported_fr_dir / f"adm{level}.geojson").read_text())
        features.extend(payload["features"])
    return features


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    exported_fr_dir = Path(sys.argv[1])
    live_docs = asyncio.run(_load_live_docs())
    exported_features = _load_exported_features(exported_fr_dir)

    diffs = compare_zones(live_docs, exported_features)
    if diffs:
        print(f"{len(diffs)} discrepancies found:")
        for diff in diffs:
            print(f"  - {diff}")
        sys.exit(1)

    print(
        f"OK: {len(exported_features)} exported zones match the live data (overseas regions skipped)."
    )


if __name__ == "__main__":
    main()
