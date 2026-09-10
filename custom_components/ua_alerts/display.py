"""Human-readable labels for stable UA Alerts technical codes."""

from __future__ import annotations

from collections.abc import Iterable

from .const import ALERT_LEVEL_CLEAR, ALERT_LEVEL_RED, ALERT_LEVEL_YELLOW

_SUPPORTED_LANGUAGES = {"en", "ru", "uk"}

_LOCATION_TYPE_LABELS = {
    "en": {
        "oblast": "Oblast",
        "raion": "Raion",
        "city": "City",
        "hromada": "Hromada",
        "unknown": "Territory",
    },
    "ru": {
        "oblast": "Область",
        "raion": "Район",
        "city": "Город",
        "hromada": "Громада",
        "unknown": "Территория",
    },
    "uk": {
        "oblast": "Область",
        "raion": "Район",
        "city": "Місто",
        "hromada": "Громада",
        "unknown": "Територія",
    },
}

_LEVEL_LABELS = {
    "en": {
        ALERT_LEVEL_CLEAR: "Clear",
        ALERT_LEVEL_YELLOW: "Yellow",
        ALERT_LEVEL_RED: "Red",
    },
    "ru": {
        ALERT_LEVEL_CLEAR: "Нет тревоги",
        ALERT_LEVEL_YELLOW: "Жёлтый",
        ALERT_LEVEL_RED: "Красный",
    },
    "uk": {
        ALERT_LEVEL_CLEAR: "Немає тривоги",
        ALERT_LEVEL_YELLOW: "Жовтий",
        ALERT_LEVEL_RED: "Червоний",
    },
}

# Keep this list synchronized with the alerts.in.ua threat_type enum. Unknown
# future codes remain visible and are always preserved verbatim in attributes.
_THREAT_LABELS = {
    "en": {
        "tactic_aircraft_activity": "Tactical aviation",
        "strategic_aircraft_activity": "Strategic aviation",
        "mig31k_departure": "MiG-31K takeoff",
        "ballistic_missiles": "Ballistic missiles",
        "cruise_missiles": "Cruise missiles",
        "unspecified_missiles": "Missile threat",
        "drones": "UAVs",
        "guided_aerial_bombs": "Guided aerial bombs",
        "air_defense": "Air defence activity",
        "unknown": "Unknown threat",
    },
    "ru": {
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
    },
    "uk": {
        "tactic_aircraft_activity": "Тактична авіація",
        "strategic_aircraft_activity": "Стратегічна авіація",
        "mig31k_departure": "Виліт МіГ-31К",
        "ballistic_missiles": "Балістичні ракети",
        "cruise_missiles": "Крилаті ракети",
        "unspecified_missiles": "Ракетна загроза",
        "drones": "БпЛА",
        "guided_aerial_bombs": "Керовані авіабомби",
        "air_defense": "Робота ППО",
        "unknown": "Невідома загроза",
    },
}

_EMPTY_THREATS = {
    "en": {"clear": "No threats", "active": "Not specified"},
    "ru": {"clear": "Нет угроз", "active": "Не указаны"},
    "uk": {"clear": "Немає загроз", "active": "Не вказані"},
}

_UNKNOWN_THREAT_PREFIX = {
    "en": "Unknown threat",
    "ru": "Неизвестно",
    "uk": "Невідома загроза",
}

THREAT_CODE_ORDER = (
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


def threat_state_key(codes: Iterable[str]) -> str:
    """Return a stable snake_case state key that Home Assistant can localize.

    Unknown future threat codes are represented to the user as ``unknown`` while
    their exact source values remain available in ``threat_codes`` attributes.
    """
    raw = set(codes)
    if not raw:
        return "none"
    known = set(THREAT_CODE_ORDER)
    normalized = {code for code in raw if code in known}
    if raw - known:
        normalized.add("unknown")
    ordered = [code for code in THREAT_CODE_ORDER if code in normalized]
    return "_and_".join(ordered)


def normalize_language(language: str | None) -> str:
    """Map a Home Assistant language tag to a supported display language."""
    if not language:
        return "en"
    normalized = language.replace("_", "-").split("-", 1)[0].casefold()
    return normalized if normalized in _SUPPORTED_LANGUAGES else "en"


def location_type_label(code: str, language: str | None) -> str:
    """Return a human-readable location type while never exposing raw UI codes."""
    lang = normalize_language(language)
    return _LOCATION_TYPE_LABELS[lang].get(code, _LOCATION_TYPE_LABELS[lang]["unknown"])


def level_label(code: str | None, language: str | None) -> str:
    """Return a localized alert level label."""
    lang = normalize_language(language)
    if code is None:
        return "—"
    return _LEVEL_LABELS[lang].get(code, code)


def threat_label(code: str, language: str | None) -> str:
    """Return a localized threat label without exposing raw codes in the UI."""
    lang = normalize_language(language)
    label = _THREAT_LABELS[lang].get(code)
    if label is not None:
        return label
    return _UNKNOWN_THREAT_PREFIX[lang]


def threat_summary(
    codes: Iterable[str],
    language: str | None,
    *,
    alert_level: str | None,
) -> str:
    """Return the localized user-facing state for all current threats."""
    lang = normalize_language(language)
    code_list = tuple(codes)
    if not code_list:
        empty_key = "clear" if alert_level == ALERT_LEVEL_CLEAR else "active"
        return _EMPTY_THREATS[lang][empty_key]
    return ", ".join(threat_label(code, lang) for code in code_list)
