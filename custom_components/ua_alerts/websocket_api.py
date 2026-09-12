"""WebSocket API for the UA Alerts device-page test dialog."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.components.websocket_api import ERR_NOT_FOUND
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant, callback

from .const import ALERT_LEVEL_CLEAR, ALERT_LEVEL_RED, ALERT_LEVEL_YELLOW, DOMAIN
from .display import THREAT_CODE_ORDER, level_label, normalize_language, threat_label

_TEST_LEVEL_OFF = "off"
_TEST_LEVELS = (
    _TEST_LEVEL_OFF,
    ALERT_LEVEL_CLEAR,
    ALERT_LEVEL_YELLOW,
    ALERT_LEVEL_RED,
)
_TEST_OFF_LABELS = {
    "en": "Off",
    "ru": "Выключено",
    "uk": "Вимкнено",
}


@callback
def async_register_websocket_handlers(hass: HomeAssistant) -> None:
    """Register UA Alerts testing commands."""
    websocket_api.async_register_command(hass, websocket_get_test_state)
    websocket_api.async_register_command(hass, websocket_set_test_state)


def _coordinator_for_entry(hass: HomeAssistant, entry_id: str):
    """Return the loaded UA Alerts coordinator for an entry, if available."""
    entry = hass.config_entries.async_get_entry(entry_id)
    if (
        entry is None
        or entry.domain != DOMAIN
        or entry.state is not ConfigEntryState.LOADED
    ):
        return None
    return getattr(entry, "runtime_data", None)


def _test_state(coordinator, language: str | None) -> dict[str, Any]:
    """Serialize the current test state and localized choices."""
    lang = normalize_language(language)
    return {
        "entry_id": coordinator.entry.entry_id,
        "location_uid": coordinator.location_uid,
        "location_title": coordinator.location_title,
        "active": coordinator.test_override_level is not None,
        "level": coordinator.test_override_level or _TEST_LEVEL_OFF,
        "threat_codes": list(coordinator.test_override_threat_codes),
        "level_options": [
            {"value": _TEST_LEVEL_OFF, "label": _TEST_OFF_LABELS[lang]},
            {
                "value": ALERT_LEVEL_CLEAR,
                "label": level_label(ALERT_LEVEL_CLEAR, lang),
            },
            {
                "value": ALERT_LEVEL_YELLOW,
                "label": level_label(ALERT_LEVEL_YELLOW, lang),
            },
            {
                "value": ALERT_LEVEL_RED,
                "label": level_label(ALERT_LEVEL_RED, lang),
            },
        ],
        "threat_options": [
            {"value": code, "label": threat_label(code, lang)}
            for code in THREAT_CODE_ORDER
        ],
    }


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "ua_alerts/test/get",
        vol.Required("entry_id"): str,
        vol.Optional("language"): str,
    }
)
@callback
def websocket_get_test_state(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return testing choices and current override for one territory."""
    coordinator = _coordinator_for_entry(hass, msg["entry_id"])
    if coordinator is None:
        connection.send_error(
            msg["id"],
            ERR_NOT_FOUND,
            "Loaded UA Alerts config entry not found",
        )
        return
    connection.send_result(msg["id"], _test_state(coordinator, msg.get("language")))


@websocket_api.require_admin
@websocket_api.websocket_command(
    {
        vol.Required("type"): "ua_alerts/test/set",
        vol.Required("entry_id"): str,
        vol.Required("level"): vol.In(_TEST_LEVELS),
        vol.Optional("threat_codes", default=[]): [vol.In(THREAT_CODE_ORDER)],
        vol.Optional("language"): str,
    }
)
@callback
def websocket_set_test_state(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Apply or clear a temporary test override for one territory."""
    coordinator = _coordinator_for_entry(hass, msg["entry_id"])
    if coordinator is None:
        connection.send_error(
            msg["id"],
            ERR_NOT_FOUND,
            "Loaded UA Alerts config entry not found",
        )
        return

    level = msg["level"]
    if level == _TEST_LEVEL_OFF:
        coordinator.clear_test_override()
    else:
        coordinator.set_test_override(level, tuple(msg["threat_codes"]))

    connection.send_result(msg["id"], _test_state(coordinator, msg.get("language")))
