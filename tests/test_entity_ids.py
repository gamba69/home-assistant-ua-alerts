from __future__ import annotations

import pytest

from ._load_core import load

entity_ids = load("entity_ids")


def test_short_entity_ids():
    expected = {
        "alert_level": "sensor.ua_31_level",
        "alert_coverage": "sensor.ua_31_coverage",
        "threat_codes": "sensor.ua_31_threats",
        "last_alert_duration": "sensor.ua_31_last_alert_duration",
        "last_alert_level": "sensor.ua_31_last_alert_level",
        "last_alert_delay": "sensor.ua_31_last_alert_delay",
        "last_threat_delay": "sensor.ua_31_last_threat_delay",
        "data_health": "sensor.ua_31_health",
        "air_alert": "binary_sensor.ua_31_alert",
        "source_available": "binary_sensor.ua_31_source",
        "poll_interval": "number.ua_31_poll",
        "stale_after": "number.ua_31_stale",
    }
    for key, entity_id in expected.items():
        assert entity_ids.short_entity_id("31", key) == entity_id


def test_short_ids_do_not_depend_on_location_title():
    assert entity_ids.short_object_id("726", "alert_level") == "ua_726_level"
    assert entity_ids.short_entity_id("726", "threat_codes") == "sensor.ua_726_threats"


def test_unknown_entity_key_is_rejected():
    with pytest.raises(ValueError):
        entity_ids.short_entity_id("31", "not_a_real_entity")


def test_pre_0_1_8_legacy_default_entity_id():
    assert (
        entity_ids.legacy_default_entity_id("m_kiiv", "threat_codes")
        == "sensor.m_kiiv_threat_codes"
    )
    assert (
        entity_ids.legacy_default_entity_id(
            "kaharlytska_terytorialna_hromada", "air_alert"
        )
        == "binary_sensor.kaharlytska_terytorialna_hromada_air_alert"
    )


def test_unknown_legacy_entity_key_is_rejected():
    with pytest.raises(ValueError):
        entity_ids.legacy_default_entity_id("m_kiiv", "not_a_real_entity")

