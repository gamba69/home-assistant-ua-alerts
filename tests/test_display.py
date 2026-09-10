from __future__ import annotations

from ._load_core import load

display = load("display")


def test_all_current_threat_codes_have_ru_uk_en_labels():
    codes = (
        "tactic_aircraft_activity",
        "strategic_aircraft_activity",
        "mig31k_departure",
        "ballistic_missiles",
        "cruise_missiles",
        "unspecified_missiles",
        "drones",
        "guided_aerial_bombs",
        "air_defense",
        "unknown",
    )
    for lang in ("en", "ru", "uk"):
        for code in codes:
            assert display.threat_label(code, lang) != code


def test_threat_summary_is_localized_and_unknown_code_is_not_lost():
    assert display.threat_summary(("drones",), "ru", alert_level="yellow") == "БПЛА"
    assert display.threat_summary(("drones",), "uk", alert_level="yellow") == "БпЛА"
    assert display.threat_summary(("drones",), "en", alert_level="yellow") == "UAVs"
    assert display.threat_summary(("future_code",), "ru", alert_level="yellow") == "Неизвестно"


def test_empty_threat_summary_distinguishes_clear_from_active_without_details():
    assert display.threat_summary((), "ru", alert_level="clear") == "Нет угроз"
    assert display.threat_summary((), "ru", alert_level="yellow") == "Не указаны"


def test_location_type_labels_are_localized():
    assert display.location_type_label("city", "ru") == "Город"
    assert display.location_type_label("city", "uk") == "Місто"
    assert display.location_type_label("city", "en") == "City"
    assert display.location_type_label("future_type", "ru") == "Территория"


def test_language_tags_are_normalized():
    assert display.normalize_language("ru-RU") == "ru"
    assert display.normalize_language("uk_UA") == "uk"
    assert display.normalize_language("de") == "en"


def test_threat_state_key_is_stable_and_frontend_translatable():
    assert display.threat_state_key([]) == "none"
    assert display.threat_state_key(["drones"]) == "drones"
    assert display.threat_state_key(["drones", "cruise_missiles"]) == "cruise_missiles_and_drones"
    assert display.threat_state_key(["future_code"]) == "unknown"
    assert display.threat_state_key(["drones", "future_code"]) == "drones_and_unknown"


def test_russian_threat_labels_are_maximally_compact():
    expected = {
        "tactic_aircraft_activity": "Тактическая",
        "strategic_aircraft_activity": "Стратегическая",
        "mig31k_departure": "МиГ-31К",
        "ballistic_missiles": "Баллистика",
        "cruise_missiles": "Крылатые",
        "unspecified_missiles": "Ракеты",
        "drones": "БПЛА",
        "guided_aerial_bombs": "КАБ",
        "air_defense": "ПВО",
        "unknown": "Неизвестно",
    }
    for code, label in expected.items():
        assert display.threat_label(code, "ru") == label
    assert display.threat_summary(
        ("tactic_aircraft_activity", "ballistic_missiles", "drones"),
        "ru",
        alert_level="yellow",
    ) == "Тактическая, Баллистика, БПЛА"
