from __future__ import annotations

from scripts.verify_fr_non_regression import compare_zones


def _live(code: str, name: str, bbox: list[float]) -> dict:
    return {"code": code, "name": name, "bbox": bbox}


def _exported(code: str, nom: str, bbox: list[float]) -> dict:
    return {"type": "Feature", "properties": {"code": code, "nom": nom}, "bbox": bbox}


def test_no_diffs_when_everything_matches():
    live = [_live("FR-84", "Auvergne-Rhône-Alpes", [4.0, 44.0, 7.0, 46.5])]
    exported = [_exported("FR-84", "Auvergne-Rhône-Alpes", [4.0, 44.0, 7.0, 46.5])]
    assert compare_zones(live, exported) == []


def test_reports_a_name_mismatch():
    live = [_live("FR-84", "Auvergne-Rhone-Alpes", [4.0, 44.0, 7.0, 46.5])]
    exported = [_exported("FR-84", "Auvergne-Rhône-Alpes", [4.0, 44.0, 7.0, 46.5])]
    diffs = compare_zones(live, exported)
    assert len(diffs) == 1
    assert "FR-84" in diffs[0] and "name" in diffs[0]


def test_reports_a_missing_code_in_the_export():
    live = [_live("FR-84", "Auvergne-Rhône-Alpes", [4.0, 44.0, 7.0, 46.5])]
    diffs = compare_zones(live, [])
    assert len(diffs) == 1
    assert "FR-84" in diffs[0] and "missing" in diffs[0]


def test_ignores_overseas_regions_not_present_in_the_export():
    # FR-01 (Guadeloupe) is out of scope for this migration - must not be reported.
    live = [_live("FR-01", "Guadeloupe", [-62.0, 15.8, -61.0, 16.5])]
    assert compare_zones(live, []) == []


def test_bbox_mismatch_uses_a_small_tolerance():
    live = [_live("FR-84", "Auvergne-Rhône-Alpes", [4.0, 44.0, 7.0, 46.5])]
    exported = [_exported("FR-84", "Auvergne-Rhône-Alpes", [4.0000001, 44.0, 7.0, 46.5])]
    assert compare_zones(live, exported) == []
