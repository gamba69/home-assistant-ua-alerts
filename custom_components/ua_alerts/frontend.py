"""Register the small UA Alerts device-page frontend helper."""

from __future__ import annotations

from pathlib import Path

from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant

from .const import VERSION

_FRONTEND_URL_BASE = "/ua_alerts/frontend"
_DEVICE_TEST_MODULE = "ua-alerts-device-test.js"


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Serve and load the UA Alerts device-page helper module."""
    frontend_dir = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                _FRONTEND_URL_BASE,
                str(frontend_dir),
                cache_headers=True,
            )
        ]
    )
    add_extra_js_url(
        hass,
        f"{_FRONTEND_URL_BASE}/{_DEVICE_TEST_MODULE}?v={VERSION}",
    )
