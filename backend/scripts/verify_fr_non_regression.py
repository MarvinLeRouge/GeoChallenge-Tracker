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


def compare_zones(
    live_docs: list[dict], exported_features: list[dict]
) -> tuple[list[str], list[str]]:
    """Compares live `administrative_zones` docs against exported CONTRACT.md features.

    `code` is only unique per level (INSEE region and department codes share the
    same numeric namespace, e.g. `FR-11` is both a region and a department) -
    live docs and exported features are matched on `(level, code)`, mirroring
    how the app itself disambiguates them.

    Args:
        live_docs (list[dict]): `{"code", "level", "name", "bbox"}` from `administrative_zones`.
        exported_features (list[dict]): GeoJSON features with `properties.code`,
            `properties.nom`, and a top-level `bbox`; level is inferred from
            which file (`adm1`/`adm2`) each feature came from.

    Returns:
        tuple[list[str], list[str]]: (failures, notes). Failures are missing
            zones or name mismatches - these fail the check. Notes are bbox
            drift, reported for visibility only: geoBoundaries geometry is
            trusted as the source of truth, so bbox differences from the
            currently-live data are expected, not a regression.
            Overseas region codes present only in `live_docs` are silently skipped.
    """
    exported_by_key = {
        (f["properties"]["level"], f["properties"]["code"]): f for f in exported_features
    }
    failures = []
    notes = []

    for live in live_docs:
        code = live["code"]
        if code in OVERSEAS_CODES:
            continue
        key = (live["level"], code)
        exported = exported_by_key.get(key)
        if exported is None:
            failures.append(f"{code} (level {live['level']}): missing from the exported output")
            continue
        if exported["properties"]["nom"] != live["name"]:
            failures.append(
                f"{code} (level {live['level']}): name mismatch (live={live['name']!r}, "
                f"exported={exported['properties']['nom']!r})"
            )
        if not _bbox_close(exported["bbox"], live["bbox"]):
            notes.append(
                f"{code} (level {live['level']}): bbox drift (live={live['bbox']}, "
                f"exported={exported['bbox']})"
            )

    return failures, notes


async def _load_live_docs() -> list[dict]:
    from app.db.mongodb import get_collection

    collection = await get_collection("administrative_zones")
    cursor = collection.find({"country_code": "FR"})
    return [doc async for doc in cursor]


def _load_exported_features(exported_fr_dir: Path) -> list[dict]:
    """Loads adm1/adm2 features, tagging each with its level (not itself a
    GeoJSON property - it's implicit in which file the feature came from)."""
    features = []
    for level in (1, 2):
        payload = json.loads((exported_fr_dir / f"adm{level}.geojson").read_text())
        for feature in payload["features"]:
            feature["properties"]["level"] = level
        features.extend(payload["features"])
    return features


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)

    exported_fr_dir = Path(sys.argv[1])
    live_docs = asyncio.run(_load_live_docs())
    exported_features = _load_exported_features(exported_fr_dir)

    failures, notes = compare_zones(live_docs, exported_features)

    if notes:
        print(
            f"{len(notes)} bbox drift note(s) (informational, geoBoundaries geometry is trusted):"
        )
        for note in notes:
            print(f"  - {note}")

    if failures:
        print(f"{len(failures)} discrepancies found:")
        for failure in failures:
            print(f"  - {failure}")
        sys.exit(1)

    print(
        f"OK: {len(exported_features)} exported zones match the live data on code/name "
        "(overseas regions skipped, bbox drift reported above is informational only)."
    )


if __name__ == "__main__":
    main()
