"""Diagnostics for UA Alerts."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .coordinator import UAAlertsCoordinator


def _iso(value: Any) -> Any:
    return value.isoformat() if hasattr(value, "isoformat") else value


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics without exposing the full raw snapshot."""
    coordinator: UAAlertsCoordinator = entry.runtime_data
    runtime = coordinator.runtime
    state = coordinator.data

    return {
        "runtime": {
            "status": runtime.status,
            "registered_entries": list(runtime.registered_entries),
            "registered_entry_count": runtime.registered_entry_count,
            "last_request": _iso(runtime.last_request),
            "last_successful_fetch": _iso(runtime.last_successful_fetch),
            "cachedat": runtime.cachedat,
            "http_status": runtime.http_status,
            "http_response_time": runtime.http_response_time,
            "consecutive_errors": runtime.consecutive_errors,
            "last_error": runtime.last_error,
            "errors": [item.as_dict() for item in runtime.errors],
        },
        "location": {
            "location_uid": state.location_uid,
            "location_title": state.location_title,
            "location_type": state.location_type,
            "level": state.level,
            "alert_scope": state.alert_scope,
            "alert_source_location_uid": state.alert_source_location_uid,
            "alert_source_location_title": state.alert_source_location_title,
            "alert_source_location_type": state.alert_source_location_type,
            "active_alert_location_uids": list(state.active_alert_location_uids),
            "coverage_code": state.coverage_code,
            "full_level_code": state.full_level_code,
            "partial_level_code": state.partial_level_code,
            "active_full_alert_location_uids": list(state.active_full_alert_location_uids),
            "active_partial_alert_location_uids": list(state.active_partial_alert_location_uids),
            "threats": [threat.as_attribute_dict() for threat in state.threats],
            "source_available": state.source_available,
            "data_valid": state.data_valid,
            "data_error": state.data_error,
            "current_alert_started_at": _iso(state.alert_started_at),
            "source_updated_at": _iso(state.source_updated_at),
            "snapshot_received_at": _iso(state.received_at),
            "last_alert_started_at": _iso(state.last_alert_started_at),
            "last_alert_ended_at": _iso(state.last_alert_ended_at),
            "last_alert_duration": state.last_alert_duration,
            "last_alert_level": state.last_alert_level,
            "last_alert_delay": state.alert_latency,
            "delay_alert_started_at": _iso(state.latency_alert_started_at),
            "delay_alert_detected_at": _iso(state.alert_detected_at),
            "delay_alert_level": state.alert_latency_level,
            "last_threat_delay": state.threat_latency,
            "delay_threat_code": state.threat_latency_code,
            "delay_threat_level": state.threat_latency_level,
            "delay_threat_started_at": _iso(state.threat_latency_started_at),
            "delay_threat_detected_at": _iso(state.threat_detected_at),
            "delay_threat_source_message": state.threat_latency_source_message,
        },
    }
