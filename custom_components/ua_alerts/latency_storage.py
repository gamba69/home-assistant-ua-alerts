"""Persistent storage for the latest alert history and delay measurements."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from .const import (
    LATENCY_STORAGE_KEY_FORMAT,
    LATENCY_STORAGE_VERSION,
    VALID_ALERT_LEVELS,
)
from .models import (
    ActiveAlertLifecycle,
    AlertLatencyMeasurement,
    LastAlertMeasurement,
    ThreatLatencyMeasurement,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RestoredLatencyMeasurements:
    """Last saved history/delay values for one territory.

    The class name is kept for source compatibility with 0.1.10-0.1.19.
    """

    alert: AlertLatencyMeasurement | None = None
    threat: ThreatLatencyMeasurement | None = None
    active_alert: ActiveAlertLifecycle | None = None
    last_alert: LastAlertMeasurement | None = None


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _decode_alert(value: Any) -> AlertLatencyMeasurement | None:
    if not isinstance(value, dict):
        return None
    started_at = _parse_datetime(value.get("alert_started_at"))
    detected_at = _parse_datetime(value.get("detected_at"))
    seconds = value.get("seconds")
    level = value.get("level")
    if (
        started_at is None
        or detected_at is None
        or not isinstance(seconds, (int, float))
        or isinstance(seconds, bool)
        or float(seconds) < 0
        or not isinstance(level, str)
    ):
        return None
    return AlertLatencyMeasurement(
        alert_started_at=started_at,
        detected_at=detected_at,
        seconds=float(seconds),
        level=level,
    )


def _decode_threat(value: Any) -> ThreatLatencyMeasurement | None:
    if not isinstance(value, dict):
        return None
    started_at = _parse_datetime(value.get("threat_started_at"))
    detected_at = _parse_datetime(value.get("detected_at"))
    seconds = value.get("seconds")
    threat_type = value.get("threat_type")
    threat_level = value.get("threat_level")
    source_message = value.get("source_message")
    if (
        started_at is None
        or detected_at is None
        or not isinstance(seconds, (int, float))
        or isinstance(seconds, bool)
        or float(seconds) < 0
        or not isinstance(threat_type, str)
        or (threat_level is not None and not isinstance(threat_level, str))
        or (source_message is not None and not isinstance(source_message, str))
    ):
        return None
    return ThreatLatencyMeasurement(
        threat_type=threat_type,
        threat_level=threat_level,
        threat_started_at=started_at,
        detected_at=detected_at,
        seconds=float(seconds),
        source_message=source_message,
    )


def _decode_active_alert(value: Any) -> ActiveAlertLifecycle | None:
    if not isinstance(value, dict):
        return None
    started_at = _parse_datetime(value.get("alert_started_at"))
    max_level = value.get("max_level")
    if started_at is None or max_level not in VALID_ALERT_LEVELS:
        return None
    return ActiveAlertLifecycle(
        alert_started_at=started_at,
        max_level=max_level,
    )


def _decode_last_alert(value: Any) -> LastAlertMeasurement | None:
    if not isinstance(value, dict):
        return None
    started_at = _parse_datetime(value.get("alert_started_at"))
    ended_at = _parse_datetime(value.get("ended_at"))
    seconds = value.get("seconds")
    max_level = value.get("max_level")
    if (
        started_at is None
        or ended_at is None
        or ended_at < started_at
        or not isinstance(seconds, (int, float))
        or isinstance(seconds, bool)
        or float(seconds) < 0
        or max_level not in VALID_ALERT_LEVELS
    ):
        return None
    return LastAlertMeasurement(
        alert_started_at=started_at,
        ended_at=ended_at,
        seconds=float(seconds),
        max_level=max_level,
    )


def _encode_alert(value: AlertLatencyMeasurement | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "alert_started_at": value.alert_started_at.isoformat(),
        "detected_at": value.detected_at.isoformat(),
        "seconds": value.seconds,
        "level": value.level,
    }


def _encode_threat(value: ThreatLatencyMeasurement | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "threat_type": value.threat_type,
        "threat_level": value.threat_level,
        "threat_started_at": value.threat_started_at.isoformat(),
        "detected_at": value.detected_at.isoformat(),
        "seconds": value.seconds,
        "source_message": value.source_message,
    }


def _encode_active_alert(value: ActiveAlertLifecycle | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "alert_started_at": value.alert_started_at.isoformat(),
        "max_level": value.max_level,
    }


def _encode_last_alert(value: LastAlertMeasurement | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "alert_started_at": value.alert_started_at.isoformat(),
        "ended_at": value.ended_at.isoformat(),
        "seconds": value.seconds,
        "max_level": value.max_level,
    }


class LatencyStorage:
    """Store the latest alert history/delay values for one stable UID."""

    def __init__(self, hass: HomeAssistant, location_uid: str) -> None:
        from homeassistant.helpers.storage import Store

        # Keep the 0.1.10 storage key/version so existing delay measurements
        # are restored without a storage migration.
        self._store = Store[dict[str, Any]](
            hass,
            LATENCY_STORAGE_VERSION,
            LATENCY_STORAGE_KEY_FORMAT.format(location_uid=location_uid),
            private=True,
        )

    async def async_load(self) -> RestoredLatencyMeasurements:
        """Load saved values defensively; malformed fields are ignored."""
        try:
            data = await self._store.async_load()
        except Exception:
            _LOGGER.exception("Could not load UA Alerts history storage")
            return RestoredLatencyMeasurements()

        if not isinstance(data, dict):
            return RestoredLatencyMeasurements()
        return RestoredLatencyMeasurements(
            alert=_decode_alert(data.get("alert")),
            threat=_decode_threat(data.get("threat")),
            active_alert=_decode_active_alert(data.get("active_alert")),
            last_alert=_decode_last_alert(data.get("last_alert")),
        )

    async def async_save(
        self,
        alert: AlertLatencyMeasurement | None,
        threat: ThreatLatencyMeasurement | None,
        *,
        active_alert: ActiveAlertLifecycle | None = None,
        last_alert: LastAlertMeasurement | None = None,
    ) -> None:
        """Persist meaningful alert-history changes immediately."""
        await self._store.async_save(
            {
                "alert": _encode_alert(alert),
                "threat": _encode_threat(threat),
                "active_alert": _encode_active_alert(active_alert),
                "last_alert": _encode_last_alert(last_alert),
            }
        )
