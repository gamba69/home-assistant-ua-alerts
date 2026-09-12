from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "ua_alerts"


def _version_from_const() -> str:
    source = (INTEGRATION / "const.py").read_text(encoding="utf-8")
    match = re.search(r'^VERSION = "([^"]+)"$', source, re.MULTILINE)
    assert match is not None
    return match.group(1)


def test_device_page_test_dialog_contract():
    init_source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
    frontend_source = (INTEGRATION / "frontend.py").read_text(encoding="utf-8")
    websocket_source = (INTEGRATION / "websocket_api.py").read_text(encoding="utf-8")
    js_source = (
        INTEGRATION / "frontend" / "ua-alerts-device-test.js"
    ).read_text(encoding="utf-8")

    assert "async_setup_frontend" in init_source
    assert "async_register_websocket_handlers" in init_source
    assert "add_extra_js_url" in frontend_source
    assert "async_register_static_paths" in frontend_source
    assert "async_when_setup" in frontend_source
    assert '"ua_alerts/test/get"' in websocket_source
    assert '"ua_alerts/test/set"' in websocket_source
    assert "@websocket_api.require_admin" in websocket_source
    assert "set_test_override" in websocket_source
    assert "clear_test_override" in websocket_source
    assert 'action: "Тестирование тревоги"' in js_source
    assert 'action: "Тестування тривоги"' in js_source
    assert 'type: "ua_alerts/test/get"' in js_source
    assert 'type: "ua_alerts/test/set"' in js_source
    assert 'input type="checkbox" name="threat"' in js_source
    assert "`${base.label || MANUFACTURER} · ${territoryTitle}`" in js_source
    assert "`${stringsFor(hass).action} · ${territoryTitle}`" in js_source
    assert "page._deviceActions = [testAction, ...actions]" in js_source


def test_release_version_is_synchronized_everywhere():
    version = _version_from_const()
    assert version == "0.1.24"

    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["version"] == version
    assert manifest["dependencies"] == ["http", "websocket_api"]
    assert manifest["after_dependencies"] == ["frontend"]
    assert "frontend" not in manifest["dependencies"]

    root_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert f"**Current release:** `{version}`" in root_readme

    markers = {
        "en": f"Current release: **{version}**",
        "ru": f"Текущий релиз: **{version}**",
        "uk": f"Поточний реліз: **{version}**",
    }
    for lang, marker in markers.items():
        readme = (ROOT / "docs" / lang / "README.md").read_text(encoding="utf-8")
        changelog = (ROOT / "docs" / lang / "CHANGELOG.md").read_text(
            encoding="utf-8"
        )
        assert marker in readme
        assert f"## {version}" in changelog
