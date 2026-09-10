"""Persistent storage for the last meaningful latency measurements."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import logging
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from .const import DOMAIN, LATENCY_STORAGE_KEY_FORMAT, LATENCY_STORAGE_VERSION
from .models import AlertLatencyMeasurement, ThreatLatencyMeasurement

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RestoredLatencyMeasurements:
    """Last saved measurements for one territory."""

    alert: AlertLatencyMeasurement | None = None
    threat: ThreatLatencyMeasurement | None = None


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


class LatencyStorage:
    """Store the last alert/threat latency values for one stable location UID."""

    def __init__(self, hass: HomeAssistant, location_uid: str) -> None:
        from homeassistant.helpers.storage import Store

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
            _LOGGER.exception("Could not load UA Alerts latency storage")
            return RestoredLatencyMeasurements()

        if not isinstance(data, dict):
            return RestoredLatencyMeasurements()
        return RestoredLatencyMeasurements(
            alert=_decode_alert(data.get("alert")),
            threat=_decode_threat(data.get("threat")),
        )

    async def async_save(
        self,
        alert: AlertLatencyMeasurement | None,
        threat: ThreatLatencyMeasurement | None,
    ) -> None:
        """Persist the latest measurements immediately.

        Writes are intentionally immediate rather than poll-driven or delayed:
        meaningful latency measurements are rare and should survive an HA restart
        that happens soon after the alert/threat was detected.
        """
        await self._store.async_save(
            {
                "alert": _encode_alert(alert),
                "threat": _encode_threat(threat),
            }
        )
