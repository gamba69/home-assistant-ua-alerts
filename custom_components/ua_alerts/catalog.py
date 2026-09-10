"""Location catalog storage for UA Alerts.

The alert runtime never refreshes this catalog. Network access happens only when
an explicit user action calls :func:`async_refresh_catalog`.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from datetime import UTC, datetime
from functools import lru_cache
import json
import logging
from pathlib import Path
from typing import Any

import aiohttp

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .catalog_parser import catalog_is_full, parse_catalog_csv
from .const import (
    CATALOG_REQUEST_TIMEOUT_SECONDS,
    CATALOG_URL,
    CONF_LOCATION_TITLE,
    CONF_LOCATION_TYPE,
    CONF_LOCATION_UID,
    DOMAIN,
)
from .models import LocationDefinition

_LOGGER = logging.getLogger(__name__)
_LOCATIONS_FILE = Path(__file__).with_name("locations.json")
_STORAGE_KEY = f"{DOMAIN}.location_catalog"
_STORAGE_VERSION = 1
_DATA_KEY = f"{DOMAIN}_location_catalog"


class CatalogRefreshError(RuntimeError):
    """Raised when an explicit location-catalog refresh fails."""


@lru_cache(maxsize=1)
def load_bundled_locations() -> tuple[LocationDefinition, ...]:
    """Load the catalog snapshot shipped with the integration package."""
    with _LOCATIONS_FILE.open("r", encoding="utf-8") as file_handle:
        return _decode_items(json.load(file_handle))


def _clean_optional(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _decode_items(payload: Any) -> tuple[LocationDefinition, ...]:
    if not isinstance(payload, list):
        return ()
    result: list[LocationDefinition] = []
    seen: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        uid = str(item.get(CONF_LOCATION_UID, "")).strip()
        title = str(item.get(CONF_LOCATION_TITLE, "")).strip()
        location_type = str(item.get(CONF_LOCATION_TYPE, "unknown")).strip() or "unknown"
        if not uid or not title or uid in seen:
            continue
        seen.add(uid)
        result.append(
            LocationDefinition(
                uid,
                title,
                location_type,
                oblast_uid=_clean_optional(item.get("oblast_uid")),
                oblast_title=_clean_optional(item.get("oblast_title")),
                raion_uid=_clean_optional(item.get("raion_uid")),
                raion_title=_clean_optional(item.get("raion_title")),
            )
        )
    return tuple(result)


def _catalog_state(hass: HomeAssistant) -> dict[str, Any]:
    state = hass.data.setdefault(_DATA_KEY, {})
    if "store" not in state:
        state["store"] = Store(hass, _STORAGE_VERSION, _STORAGE_KEY)
    return state


async def async_load_catalog(hass: HomeAssistant) -> tuple[LocationDefinition, ...]:
    """Load a catalog without performing any network request.

    A manually refreshed full catalog stored in ``.storage`` wins. If none has
    ever been saved, the package snapshot is used. There is deliberately no TTL
    and no automatic catalog refresh.
    """
    state = _catalog_state(hass)
    memory_items = state.get("items")
    if isinstance(memory_items, tuple) and memory_items:
        return memory_items

    stored = await state["store"].async_load()
    if isinstance(stored, dict):
        items = _decode_items(stored.get("items"))
        if catalog_is_full(items):
            state["items"] = items
            state["fetched_at"] = stored.get("fetched_at")
            state["source"] = "manual_cache"
            return items

    items = load_bundled_locations()
    state["items"] = items
    state["fetched_at"] = None
    state["source"] = "bundled"
    return items


async def async_refresh_catalog(hass: HomeAssistant) -> tuple[LocationDefinition, ...]:
    """Explicitly download, validate, and persist the official catalog.

    This function is called only from a user-initiated configuration action.
    Failures never replace a previously valid catalog.
    """
    state = _catalog_state(hass)
    now = datetime.now(UTC)

    try:
        session = async_get_clientsession(hass)
        async with asyncio.timeout(CATALOG_REQUEST_TIMEOUT_SECONDS):
            async with session.get(CATALOG_URL) as response:
                response.raise_for_status()
                text = await response.text()
        items = parse_catalog_csv(text)
    except (TimeoutError, aiohttp.ClientError, ValueError, UnicodeError) as err:
        _LOGGER.warning("Unable to refresh UA Alerts location catalog: %s", err)
        raise CatalogRefreshError(str(err)) from err

    await state["store"].async_save(
        {
            "fetched_at": now.isoformat(),
            "items": [asdict(item) for item in items],
        }
    )
    state["items"] = items
    state["fetched_at"] = now.isoformat()
    state["source"] = "manual_cache"
    return items
