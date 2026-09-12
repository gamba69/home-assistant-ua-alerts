"""Global persisted settings for UA Alerts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    DEFAULT_POLL_INTERVAL_SECONDS,
    DEFAULT_STALE_AFTER_SECONDS,
    DOMAIN,
    OPT_POLL_INTERVAL,
    OPT_STALE_AFTER,
)
from .timing import UAAlertsSettings, validate_settings

_STORAGE_KEY = f"{DOMAIN}.settings"
_STORAGE_VERSION = 1
_DATA_KEY = f"{DOMAIN}_global_settings"


@dataclass(slots=True)
class _SettingsState:
    store: Store[dict[str, Any]]
    loaded: bool = False
    settings: UAAlertsSettings = UAAlertsSettings()


def _state(hass: HomeAssistant) -> _SettingsState:
    state = hass.data.get(_DATA_KEY)
    if state is None:
        state = _SettingsState(Store(hass, _STORAGE_VERSION, _STORAGE_KEY))
        hass.data[_DATA_KEY] = state
    return state


async def async_get_settings(hass: HomeAssistant) -> UAAlertsSettings:
    state = _state(hass)
    if state.loaded:
        return state.settings

    raw = await state.store.async_load()
    if isinstance(raw, dict):
        try:
            state.settings = validate_settings(
                raw.get(OPT_POLL_INTERVAL, DEFAULT_POLL_INTERVAL_SECONDS),
                raw.get(OPT_STALE_AFTER, DEFAULT_STALE_AFTER_SECONDS),
            )
        except ValueError:
            state.settings = UAAlertsSettings()
    state.loaded = True
    return state.settings


async def async_set_settings(hass: HomeAssistant, settings: UAAlertsSettings) -> None:
    state = _state(hass)
    state.settings = settings
    state.loaded = True
    await state.store.async_save(settings.as_options())


async def async_apply_settings(
    hass: HomeAssistant,
    settings: UAAlertsSettings,
    *,
    skip_entry_id: str | None = None,
) -> None:
    """Persist and apply domain-wide timing settings everywhere."""
    await async_set_settings(hass, settings)
    options = settings.as_options()
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id == skip_entry_id:
            continue
        if dict(entry.options) != options:
            hass.config_entries.async_update_entry(entry, options=options)

    domain_data = hass.data.get(DOMAIN)
    runtime = getattr(domain_data, "runtime", None)
    if runtime is not None:
        await runtime.async_update_timing(
            poll_interval=settings.poll_interval,
            stale_after=settings.stale_after,
        )
