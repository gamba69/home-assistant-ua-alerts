from __future__ import annotations

import pytest

from ._load_core import load

parser = load("catalog_parser")


def test_official_catalog_parser_preserves_hierarchy_and_crimea_exception():
    csv_text = """UID,Назва,Тип,Примітки
31,м. Київ,Місто з спеціальним статусом,
8,Волинська область,Область,
29,Автономна Республіка Крим,Область,
38,Володимирський район,Район,
255,м. Володимир та Володимирська територіальна громада,Громада,
14,Київська область,Область,
75,Бучанський район,Район,
699,Білогородська територіальна громада,Громада,
"""
    locations = parser.parse_catalog_csv(csv_text, validate_full=False)
    by_uid = {item.location_uid: item for item in locations}
    assert by_uid["31"].location_type == "city"
    assert by_uid["38"].oblast_uid == "8"
    assert by_uid["255"].raion_uid == "38"
    assert by_uid["75"].oblast_uid == "14"
    assert by_uid["699"].oblast_uid == "14"
    assert by_uid["699"].raion_uid == "75"


def test_full_catalog_validation_rejects_partial_data():
    with pytest.raises(ValueError, match="unexpectedly small"):
        parser.parse_catalog_csv(
            "31,м. Київ,Місто з спеціальним статусом,\n",
            validate_full=True,
        )
