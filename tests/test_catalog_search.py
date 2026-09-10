from __future__ import annotations

import json
from pathlib import Path

from ._load_core import load

models = load("models")
search = load("catalog_search")
ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "ua_alerts"


def _catalog():
    raw = json.loads((INTEGRATION / "locations.json").read_text(encoding="utf-8"))
    return tuple(models.LocationDefinition(**item) for item in raw)


def test_kaharlyk_search_variants_resolve_current_hromada():
    catalog = _catalog()
    for query in (
        "Кагарлицька",
        "Кагарлик",
        "Кагарлык",
        "Кагарлицький район",
        "Кагарлыкский район",
        "726",
    ):
        results = search.search_catalog(catalog, query)
        assert results
        assert results[0].location.location_uid == "726", query
        assert results[0].location.raion_uid == "76"
        assert "Обухівський район" in results[0].label


def test_search_result_labels_disambiguate_duplicate_hromada_names():
    results = search.search_catalog(_catalog(), "Калинівська територіальна громада")
    assert len(results) >= 3
    labels = [item.label for item in results]
    assert len(labels) == len(set(labels))
    assert all("—" in label and "/" in label for label in labels[:3])


def test_search_can_find_parent_district_and_uid_exact_match_wins():
    catalog = _catalog()
    by_name = search.search_catalog(catalog, "Обухівський район")
    assert by_name[0].location.location_uid == "76"
    assert by_name[0].label == "Обухівський район — Київська область"

    by_uid = search.search_catalog(catalog, "31")
    assert by_uid[0].location.location_uid == "31"


def test_search_normalization_accepts_ukrainian_russian_and_punctuation():
    assert search.normalize_search_text("Київська") == search.normalize_search_text("Київська")
    assert search.normalize_search_text("Кагарлик—район") == "кагарлик район"
