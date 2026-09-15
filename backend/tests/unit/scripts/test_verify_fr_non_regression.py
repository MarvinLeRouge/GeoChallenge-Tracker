from __future__ import annotations

from scripts.verify_fr_non_regression import compare_zones


def _live(code: str, level: int, name: str, bbox: list[float]) -> dict:
    return {"code": code, "level": level, "name": name, "bbox": bbox}


def _exported(code: str, level: int, nom: str, bbox: list[float]) -> dict:
    return {
        "type": "Feature",
        "properties": {"code": code, "level": level, "nom": nom},
        "bbox": bbox,
    }


def test_no_diffs_when_everything_matches():
    live = [_live("FR-84", 1, "Auvergne-Rhône-Alpes", [4.0, 44.0, 7.0, 46.5])]
    exported = [_exported("FR-84", 1, "Auvergne-Rhône-Alpes", [4.0, 44.0, 7.0, 46.5])]
    assert compare_zones(live, exported) == ([], [])


def test_reports_a_name_mismatch():
    live = [_live("FR-84", 1, "Auvergne-Rhone-Alpes", [4.0, 44.0, 7.0, 46.5])]
    exported = [_exported("FR-84", 1, "Auvergne-Rhône-Alpes", [4.0, 44.0, 7.0, 46.5])]
    failures, notes = compare_zones(live, exported)
    assert len(failures) == 1
    assert "FR-84" in failures[0] and "name" in failures[0]
    assert notes == []


def test_reports_a_missing_code_in_the_export():
    live = [_live("FR-84", 1, "Auvergne-Rhône-Alpes", [4.0, 44.0, 7.0, 46.5])]
    failures, notes = compare_zones(live, [])
    assert len(failures) == 1
    assert "FR-84" in failures[0] and "missing" in failures[0]
    assert notes == []


def test_ignores_overseas_regions_not_present_in_the_export():
    # FR-01 (Guadeloupe) is out of scope for this migration - must not be reported.
    live = [_live("FR-01", 1, "Guadeloupe", [-62.0, 15.8, -61.0, 16.5])]
    assert compare_zones(live, []) == ([], [])


def test_bbox_mismatch_uses_a_small_tolerance():
    live = [_live("FR-84", 1, "Auvergne-Rhône-Alpes", [4.0, 44.0, 7.0, 46.5])]
    exported = [_exported("FR-84", 1, "Auvergne-Rhône-Alpes", [4.0000001, 44.0, 7.0, 46.5])]
    assert compare_zones(live, exported) == ([], [])


def test_bbox_drift_beyond_tolerance_is_a_note_not_a_failure():
    # geoBoundaries geometry is trusted as the source of truth - bbox drift from the
    # currently-live data is expected, not a regression, so it must not fail the check.
    live = [_live("FR-84", 1, "Auvergne-Rhône-Alpes", [4.0, 44.0, 7.0, 46.5])]
    exported = [_exported("FR-84", 1, "Auvergne-Rhône-Alpes", [4.1, 44.0, 7.0, 46.5])]
    failures, notes = compare_zones(live, exported)
    assert failures == []
    assert len(notes) == 1
    assert "FR-84" in notes[0] and "bbox" in notes[0]


def test_region_and_department_sharing_the_same_insee_number_are_not_confused():
    # FR-11 is both the Île-de-France region (level 1) and the Aude department
    # (level 2) - code alone does not disambiguate, level must be used too.
    live = [
        _live("FR-11", 1, "Île-de-France", [1.0, 48.0, 3.0, 49.0]),
        _live("FR-11", 2, "Aude", [2.0, 42.0, 3.0, 43.0]),
    ]
    exported = [
        _exported("FR-11", 1, "Île-de-France", [1.0, 48.0, 3.0, 49.0]),
        _exported("FR-11", 2, "Aude", [2.0, 42.0, 3.0, 43.0]),
    ]
    assert compare_zones(live, exported) == ([], [])
