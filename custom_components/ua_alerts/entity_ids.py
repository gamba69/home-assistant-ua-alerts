"""Stable short entity-id suggestions for UA Alerts."""

from __future__ import annotations

# Keep unique IDs verbose and stable. Only the user-facing Home Assistant
# entity_id object part is shortened.
ENTITY_ID_SPECS: dict[str, tuple[str, str]] = {
    "alert_level": ("sensor", "level"),
    "alert_coverage": ("sensor", "coverage"),
    "threat_codes": ("sensor", "threats"),
    "alert_latency": ("sensor", "alert_latency"),
    "threat_latency": ("sensor", "threat_latency"),
    "data_health": ("sensor", "health"),
    "air_alert": ("binary_sensor", "alert"),
    "source_available": ("binary_sensor", "source"),
}


def short_object_id(location_uid: str, key: str) -> str:
    """Return the stable short object id suggested to Home Assistant."""
    try:
        _, suffix = ENTITY_ID_SPECS[key]
    except KeyError as err:
        raise ValueError(f"Unknown UA Alerts entity key: {key}") from err
    return f"ua_{location_uid}_{suffix}"


def short_entity_id(location_uid: str, key: str) -> str:
    """Return the complete short entity id for a known UA Alerts entity."""
    try:
        domain, _ = ENTITY_ID_SPECS[key]
    except KeyError as err:
        raise ValueError(f"Unknown UA Alerts entity key: {key}") from err
    return f"{domain}.{short_object_id(location_uid, key)}"


def legacy_default_entity_id(location_slug: str, key: str) -> str:
    """Return the pre-0.1.8 automatically generated entity id.

    Before UID-based ``suggested_object_id`` values were introduced, Home
    Assistant generated entity IDs from the device/location name plus the
    entity description key.  Deleted registry entries preserve that old ID and
    can restore it when the same unique_id is created again.
    """
    try:
        domain, _ = ENTITY_ID_SPECS[key]
    except KeyError as err:
        raise ValueError(f"Unknown UA Alerts entity key: {key}") from err
    return f"{domain}.{location_slug}_{key}"

