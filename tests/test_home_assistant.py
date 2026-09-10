"""Full Home Assistant contract tests.

These run in CI with pytest-homeassistant-custom-component and are skipped by the
lightweight local core-only environment when Home Assistant is unavailable.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

pytest.importorskip("homeassistant")
pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ua_alerts.const import DOMAIN, SOURCE_URL, VERSION
from custom_components.ua_alerts.diagnostics import async_get_config_entry_diagnostics
from custom_components.ua_alerts.models import LocationDefinition

pytestmark = pytest.mark.usefixtures("enable_custom_integrations")


class FakeResponse:
    def __init__(self, payload, status=200):
        self.payload = payload
        self.status = status
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        return False
    def raise_for_status(self):
        if self.status >= 400:
            raise RuntimeError(f"HTTP {self.status}")
    async def json(self, content_type=None):
        if isinstance(self.payload, Exception):
            raise self.payload
        return self.payload


class FakeSession:
    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.calls = 0
        self.last = payloads[-1] if payloads else {"raw": []}
    def get(self, url):
        self.calls += 1
        payload = self.payloads.pop(0) if self.payloads else self.last
        return FakeResponse(payload)
    def push(self, payload):
        self.payloads.append(payload)
        self.last = payload


def payload(level="red", uid="31", threats=None, started_at="2026-09-09T12:00:00+00:00"):
    alert = {
        "location_uid": uid,
        "location_title": "м. Київ" if uid == "31" else "Київська область",
        "location_type": "city" if uid == "31" else "oblast",
        "alert_type": "air_raid",
        "alert_level": level,
        "started_at": started_at,
        "updated_at": "2026-09-09T12:00:03+00:00",
    }
    if threats is not None:
        alert["threats"] = threats
    return {"raw": [alert], "cachedat": "2026-09-09 15:00:03"}


def entry(uid="31", title="м. Київ", typ="city"):
    return MockConfigEntry(
        domain=DOMAIN,
        title=title,
        unique_id=f"location_{uid}",
        data={"location_uid": uid, "location_title": title, "location_type": typ},
    )


async def setup_with_session(hass: HomeAssistant, config_entry, session):
    config_entry.add_to_hass(hass)
    with patch("homeassistant.helpers.aiohttp_client.async_get_clientsession", return_value=session):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()


async def test_config_flow_and_duplicate_guard(hass: HomeAssistant):
    catalog = (
        LocationDefinition("31", "м. Київ", "city"),
        LocationDefinition("14", "Київська область", "oblast"),
        LocationDefinition("75", "Бучанський район", "raion", oblast_uid="14", oblast_title="Київська область"),
        LocationDefinition(
            "699",
            "Білогородська територіальна громада",
            "hromada",
            oblast_uid="14",
            oblast_title="Київська область",
            raion_uid="75",
            raion_title="Бучанський район",
        ),
    )
    with (
        patch("custom_components.ua_alerts.config_flow.async_load_catalog", return_value=catalog),
        patch("custom_components.ua_alerts.config_flow.catalog_is_full", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is config_entries.ConfigFlowResultType.MENU
        assert result["step_id"] == "user"
        assert set(result["menu_options"]) == {"search", "tree"}
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "search"}
        )
        assert result["type"] is config_entries.ConfigFlowResultType.FORM
        assert result["step_id"] == "search"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"query": "Київ"}
        )
        assert result["step_id"] == "search_results"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"search_uid": "31"}
        )
        assert result["type"] is config_entries.ConfigFlowResultType.CREATE_ENTRY
        assert result["data"]["location_uid"] == "31"

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "search"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"query": "31"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"search_uid": "31"}
        )
        assert result["type"] is config_entries.ConfigFlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_hierarchical_hromada_config_flow(hass: HomeAssistant):
    catalog = (
        LocationDefinition("14", "Київська область", "oblast"),
        LocationDefinition("75", "Бучанський район", "raion", oblast_uid="14", oblast_title="Київська область"),
        LocationDefinition(
            "699",
            "Білогородська територіальна громада",
            "hromada",
            oblast_uid="14",
            oblast_title="Київська область",
            raion_uid="75",
            raion_title="Бучанський район",
        ),
    )
    with (
        patch("custom_components.ua_alerts.config_flow.async_load_catalog", return_value=catalog),
        patch("custom_components.ua_alerts.config_flow.catalog_is_full", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is config_entries.ConfigFlowResultType.MENU
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"next_step_id": "tree"}
        )
        assert result["step_id"] == "tree"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"region_uid": "14"}
        )
        assert result["step_id"] == "scope"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"scope": "hromada"}
        )
        assert result["step_id"] == "raion"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"raion_uid": "75"}
        )
        assert result["step_id"] == "hromada"
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"location_uid": "699"}
        )
        assert result["type"] is config_entries.ConfigFlowResultType.CREATE_ENTRY
        assert result["data"]["location_uid"] == "699"


async def test_entity_contract_and_states(hass: HomeAssistant):
    threats = [{"threat_type": "drones", "level": "yellow", "started_at": "2026-09-09T12:00:00+00:00", "source_message": "test"}]
    session = FakeSession([payload("red", threats=threats)])
    config_entry = entry()
    await setup_with_session(hass, config_entry, session)

    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, config_entry.entry_id)
    assert len(entries) == 7
    enabled = [item for item in entries if not item.disabled]
    assert len(enabled) == 7

    alert_id = registry.async_get_entity_id("sensor", DOMAIN, "ua_alerts_31_alert_level")
    threats_id = registry.async_get_entity_id("sensor", DOMAIN, "ua_alerts_31_threat_codes")
    air_id = registry.async_get_entity_id("binary_sensor", DOMAIN, "ua_alerts_31_air_alert")
    source_id = registry.async_get_entity_id("binary_sensor", DOMAIN, "ua_alerts_31_source_available")
    assert alert_id == "sensor.ua_31_level"
    assert threats_id == "sensor.ua_31_threats"
    assert air_id == "binary_sensor.ua_31_alert"
    assert source_id == "binary_sensor.ua_31_source"
    assert registry.async_get_entity_id(
        "sensor", DOMAIN, "ua_alerts_31_alert_latency"
    ) == "sensor.ua_31_alert_latency"
    assert registry.async_get_entity_id(
        "sensor", DOMAIN, "ua_alerts_31_threat_latency"
    ) == "sensor.ua_31_threat_latency"
    health_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "ua_alerts_31_data_health"
    )
    assert health_id == "sensor.ua_31_health"
    assert hass.states[alert_id].state == "red"
    assert hass.states[threats_id].state == "drones"
    assert hass.states[alert_id].attributes["level_code"] == "red"
    assert hass.states[threats_id].attributes["threat_codes"] == ["drones"]
    assert hass.states[threats_id].attributes["threat_codes_csv"] == "drones"
    assert hass.states[threats_id].attributes["threats"][0]["threat_type"] == "drones"
    assert hass.states[air_id].state == "on"
    assert hass.states[source_id].state == "on"
    assert hass.states[health_id].state == "normal"
    assert hass.states[health_id].attributes["consecutive_errors"] == 0
    assert hass.states[health_id].attributes["http_status"] == 200

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_device(
        identifiers={(DOMAIN, "31")}, connections=set()
    )
    assert device is not None
    assert device.name == "м. Київ"
    assert device.translation_key is None
    assert device.entry_type is dr.DeviceEntryType.SERVICE
    assert device.manufacturer == "UA Alerts"
    assert device.sw_version == VERSION
    assert device.configuration_url == SOURCE_URL
    assert device.model is None

    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_existing_013_device_name_is_migrated_to_plain_location_title(
    hass: HomeAssistant,
):
    session = FakeSession([payload("red")])
    config_entry = entry()
    config_entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    legacy = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "31")},
        name="City: м. Київ",
        manufacturer="UA Alerts",
    )
    assert legacy.name == "City: м. Київ"

    with patch(
        "homeassistant.helpers.aiohttp_client.async_get_clientsession",
        return_value=session,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    migrated = device_registry.async_get_device(
        identifiers={(DOMAIN, "31")}, connections=set()
    )
    assert migrated is not None
    assert migrated.id == legacy.id
    assert migrated.name == "м. Київ"
    assert migrated.translation_key is None
    assert migrated.entry_type is dr.DeviceEntryType.SERVICE
    assert migrated.sw_version == VERSION

    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_upgrade_shortens_untouched_legacy_entity_id(hass: HomeAssistant):
    session = FakeSession([payload("red")])
    config_entry = entry()
    config_entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "31")},
        name="м. Київ",
    )
    registry = er.async_get(hass)
    legacy = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "ua_alerts_31_alert_level",
        config_entry=config_entry,
        device_id=device.id,
        has_entity_name=True,
        object_id_base="Alert level",
        original_name="Alert level",
    )
    assert legacy.entity_id != "sensor.ua_31_level"
    assert registry.async_regenerate_entity_id(legacy) == legacy.entity_id

    with patch(
        "homeassistant.helpers.aiohttp_client.async_get_clientsession",
        return_value=session,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert registry.async_get_entity_id(
        "sensor", DOMAIN, "ua_alerts_31_alert_level"
    ) == "sensor.ua_31_level"
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_upgrade_preserves_manually_renamed_entity_id(hass: HomeAssistant):
    session = FakeSession([payload("red")])
    config_entry = entry()
    config_entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "31")},
        name="м. Київ",
    )
    registry = er.async_get(hass)
    legacy = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "ua_alerts_31_alert_level",
        config_entry=config_entry,
        device_id=device.id,
        has_entity_name=True,
        object_id_base="Alert level",
        original_name="Alert level",
    )
    custom_id = "sensor.kitchen_air_raid_level"
    registry.async_update_entity(legacy.entity_id, new_entity_id=custom_id)
    customized = registry.async_get(custom_id)
    assert customized is not None
    assert registry.async_regenerate_entity_id(customized) != custom_id

    with patch(
        "homeassistant.helpers.aiohttp_client.async_get_clientsession",
        return_value=session,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert registry.async_get_entity_id(
        "sensor", DOMAIN, "ua_alerts_31_alert_level"
    ) == custom_id
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_readded_entry_migrates_restored_deleted_legacy_threat_id(
    hass: HomeAssistant,
):
    session = FakeSession([payload("red")])
    config_entry = entry()
    config_entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "31")},
        name="м. Київ",
    )
    registry = er.async_get(hass)
    legacy = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "ua_alerts_31_threat_codes",
        config_entry=config_entry,
        device_id=device.id,
        has_entity_name=True,
        object_id_base="threat_codes",
        original_name="Threat codes",
    )
    legacy_id = "sensor.m_kiiv_threat_codes"
    if legacy.entity_id != legacy_id:
        registry.async_update_entity(legacy.entity_id, new_entity_id=legacy_id)
    registry.async_remove(legacy_id)

    assert registry.async_get_entity_id(
        "sensor", DOMAIN, "ua_alerts_31_threat_codes"
    ) is None
    assert (
        "sensor",
        DOMAIN,
        "ua_alerts_31_threat_codes",
    ) in registry.deleted_entities

    with patch(
        "homeassistant.helpers.aiohttp_client.async_get_clientsession",
        return_value=session,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert registry.async_get_entity_id(
        "sensor", DOMAIN, "ua_alerts_31_threat_codes"
    ) == "sensor.ua_31_threats"
    assert hass.states.get("sensor.ua_31_threats") is not None
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_readded_entry_preserves_custom_deleted_threat_id(hass: HomeAssistant):
    session = FakeSession([payload("red")])
    config_entry = entry()
    config_entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "31")},
        name="м. Київ",
    )
    registry = er.async_get(hass)
    original = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        "ua_alerts_31_threat_codes",
        config_entry=config_entry,
        device_id=device.id,
        has_entity_name=True,
        object_id_base="threat_codes",
        original_name="Threat codes",
    )
    custom_id = "sensor.my_air_threats"
    registry.async_update_entity(original.entity_id, new_entity_id=custom_id)
    registry.async_remove(custom_id)

    with patch(
        "homeassistant.helpers.aiohttp_client.async_get_clientsession",
        return_value=session,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert registry.async_get_entity_id(
        "sensor", DOMAIN, "ua_alerts_31_threat_codes"
    ) == custom_id
    assert hass.states.get(custom_id) is not None
    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_multi_entry_one_runtime_one_initial_request(hass: HomeAssistant):
    source = {"raw": [payload("red", "31")["raw"][0], payload("yellow", "14")["raw"][0]]}
    session = FakeSession([source])
    first = entry()
    second = entry("14", "Київська область", "oblast")
    first.add_to_hass(hass)
    second.add_to_hass(hass)
    with patch("homeassistant.helpers.aiohttp_client.async_get_clientsession", return_value=session):
        await asyncio.gather(
            hass.config_entries.async_setup(first.entry_id),
            hass.config_entries.async_setup(second.entry_id),
        )
        await hass.async_block_till_done()
    assert first.runtime_data.runtime is second.runtime_data.runtime
    assert first.runtime_data.runtime.registered_entry_count == 2
    assert session.calls == 1
    assert await hass.config_entries.async_unload(first.entry_id)
    assert second.runtime_data.runtime.registered_entry_count == 1
    assert await hass.config_entries.async_unload(second.entry_id)
    assert hass.data[DOMAIN].runtime is None


async def test_level_and_threat_change_events(hass: HomeAssistant):
    session = FakeSession([payload("red")])
    config_entry = entry()
    await setup_with_session(hass, config_entry, session)
    level_events = []
    threat_events = []
    hass.bus.async_listen("ua_alert_level_changed", lambda event: level_events.append(event.data))
    hass.bus.async_listen("ua_alert_threats_changed", lambda event: threat_events.append(event.data))

    session.push(payload("yellow", threats=[{"threat_type": "drones", "level": "yellow", "started_at": "2026-09-09T12:00:00+00:00"}]))
    await config_entry.runtime_data.runtime.async_fetch()
    await hass.async_block_till_done()
    assert level_events[-1]["old_level"] == "red"
    assert level_events[-1]["new_level"] == "yellow"
    assert threat_events[-1]["threat_codes"] == "drones"
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_diagnostics_exclude_raw_snapshot(hass: HomeAssistant):
    session = FakeSession([payload("red")])
    config_entry = entry()
    await setup_with_session(hass, config_entry, session)
    diagnostics = await async_get_config_entry_diagnostics(hass, config_entry)
    text = repr(diagnostics)
    assert "raw_snapshot" not in text
    assert "parsed_snapshot" not in text
    assert diagnostics["runtime"]["registered_entry_count"] == 1
    assert diagnostics["location"]["location_uid"] == "31"
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_stale_and_recovery_entity_availability(hass: HomeAssistant):
    session = FakeSession([payload("red")])
    config_entry = entry()
    await setup_with_session(hass, config_entry, session)
    runtime = config_entry.runtime_data.runtime
    base = runtime.last_successful_fetch
    current = base
    runtime._now_fn = lambda: current

    registry = er.async_get(hass)
    alert_id = registry.async_get_entity_id("sensor", DOMAIN, "ua_alerts_31_alert_level")
    source_id = registry.async_get_entity_id("binary_sensor", DOMAIN, "ua_alerts_31_source_available")
    health_id = registry.async_get_entity_id("sensor", DOMAIN, "ua_alerts_31_data_health")

    current = base + timedelta(seconds=16)
    session.push({"raw": None})
    assert not await runtime.async_fetch()
    await hass.async_block_till_done()
    assert hass.states[alert_id].state == "unavailable"
    assert hass.states[source_id].state == "off"
    assert hass.states[health_id].state == "source_error"

    current = base + timedelta(seconds=17)
    session.push(payload("yellow"))
    assert await runtime.async_fetch()
    await hass.async_block_till_done()
    assert hass.states[alert_id].state == "yellow"
    assert hass.states[source_id].state == "on"
    assert hass.states[health_id].state == "normal"
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_global_timing_options_update_live_runtime_and_all_entries(hass: HomeAssistant):
    session = FakeSession([payload("red")])
    first = entry()
    await setup_with_session(hass, first, session)
    runtime = first.runtime_data.runtime

    result = await hass.config_entries.options.async_init(first.entry_id)
    assert result["type"] is config_entries.ConfigFlowResultType.MENU
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "timing"}
    )
    assert result["type"] is config_entries.ConfigFlowResultType.FORM
    assert result["step_id"] == "timing"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"poll_interval": 5, "stale_after": 20}
    )
    assert result["type"] is config_entries.ConfigFlowResultType.CREATE_ENTRY
    assert first.options["poll_interval"] == 5
    assert first.options["stale_after"] == 20
    assert runtime.poll_interval == 5
    assert runtime.stale_after == 20
    await hass.config_entries.async_unload(first.entry_id)


async def test_alert_latency_is_end_to_end_first_observation_and_does_not_grow(
    hass: HomeAssistant,
):
    session = FakeSession([{"raw": [], "cachedat": "2026-09-09 15:00:10"}])
    config_entry = entry()
    await setup_with_session(hass, config_entry, session)
    runtime = config_entry.runtime_data.runtime

    registry = er.async_get(hass)
    latency_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "ua_alerts_31_alert_latency"
    )
    assert latency_id is not None
    assert hass.states[latency_id].state == "unavailable"

    current = datetime(2026, 9, 9, 12, 0, 14, tzinfo=UTC)
    runtime._now_fn = lambda: current
    session.push(payload("yellow", started_at="2026-09-09T12:00:11+00:00"))
    assert await runtime.async_fetch()
    await hass.async_block_till_done()

    assert float(hass.states[latency_id].state) == 3.0
    assert hass.states[latency_id].attributes["alert_started_at"] == "2026-09-09T12:00:11+00:00"
    assert hass.states[latency_id].attributes["alert_detected_at"] == "2026-09-09T12:00:14+00:00"
    assert hass.states[latency_id].attributes["level_code"] == "yellow"

    # Same active alert 5 minutes later: latency is a frozen observation, not age.
    current = datetime(2026, 9, 9, 12, 5, 14, tzinfo=UTC)
    session.push(payload("yellow", started_at="2026-09-09T12:00:11+00:00"))
    assert await runtime.async_fetch()
    await hass.async_block_till_done()
    assert float(hass.states[latency_id].state) == 3.0

    # Clear does not erase the last useful latency measurement.
    current = datetime(2026, 9, 9, 12, 6, 0, tzinfo=UTC)
    session.push({"raw": [], "cachedat": "2026-09-09 15:06:00"})
    assert await runtime.async_fetch()
    await hass.async_block_till_done()
    assert float(hass.states[latency_id].state) == 3.0

    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_upgrade_removes_obsolete_high_churn_diagnostic_entities(
    hass: HomeAssistant,
):
    session = FakeSession([{"raw": []}])
    config_entry = entry()
    config_entry.add_to_hass(hass)
    registry = er.async_get(hass)

    obsolete_keys = (
        "data_age",
        "event_time",
        "source_updated",
        "received_at",
        "source_processing_latency",
        "delivery_latency",
        "observed_latency",
    )
    for key in obsolete_keys:
        registry.async_get_or_create(
            "sensor",
            DOMAIN,
            f"ua_alerts_31_{key}",
            config_entry=config_entry,
        )

    with patch(
        "homeassistant.helpers.aiohttp_client.async_get_clientsession",
        return_value=session,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    for key in obsolete_keys:
        assert registry.async_get_entity_id(
            "sensor", DOMAIN, f"ua_alerts_31_{key}"
        ) is None

    assert registry.async_get_entity_id(
        "sensor", DOMAIN, "ua_alerts_31_alert_latency"
    ) is not None
    await hass.config_entries.async_unload(config_entry.entry_id)


async def test_hromada_inherits_parent_raion_alert(hass: HomeAssistant):
    session = FakeSession(
        [
            {
                "raw": [
                    {
                        "location_uid": "76",
                        "location_title": "Обухівський район",
                        "location_type": "raion",
                        "alert_type": "air_raid",
                        "alert_level": "yellow",
                        "started_at": "2026-09-09T12:00:00+00:00",
                        "updated_at": "2026-09-09T12:00:03+00:00",
                        "threats": [
                            {
                                "threat_type": "drones",
                                "level": "yellow",
                                "started_at": "2026-09-09T12:00:01+00:00",
                                "source_message": "raion threat",
                            }
                        ],
                    }
                ],
                "cachedat": "2026-09-09 15:00:03",
            }
        ]
    )
    config_entry = entry(
        uid="726",
        title="Кагарлицька територіальна громада",
        typ="hromada",
    )
    await setup_with_session(hass, config_entry, session)

    registry = er.async_get(hass)
    alert_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "ua_alerts_726_alert_level"
    )
    threats_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "ua_alerts_726_threat_codes"
    )
    assert alert_id == "sensor.ua_726_level"
    assert hass.states[alert_id].state == "yellow"
    assert hass.states[alert_id].attributes["alert_scope"] == "inherited"
    assert hass.states[alert_id].attributes["alert_source_location_uid"] == "76"
    assert (
        hass.states[alert_id].attributes["alert_source_location_title"]
        == "Обухівський район"
    )
    assert hass.states[alert_id].attributes["active_alert_location_uids"] == ["76"]
    assert hass.states[threats_id].attributes["threat_codes"] == ["drones"]

    assert await hass.config_entries.async_unload(config_entry.entry_id)


async def test_raion_partial_alert_has_coverage_sensor_and_raw_code_lists(
    hass: HomeAssistant,
):
    session = FakeSession(
        [
            {
                "raw": [
                    {
                        "location_uid": "726",
                        "location_title": "Кагарлицька територіальна громада",
                        "location_type": "hromada",
                        "alert_type": "air_raid",
                        "alert_level": "red",
                        "started_at": "2026-09-09T12:00:00+00:00",
                        "updated_at": "2026-09-09T12:00:03+00:00",
                    }
                ],
                "cachedat": "2026-09-09 15:00:03",
            }
        ]
    )
    config_entry = entry(uid="76", title="Обухівський район", typ="raion")
    await setup_with_session(hass, config_entry, session)

    registry = er.async_get(hass)
    entries = er.async_entries_for_config_entry(registry, config_entry.entry_id)
    assert len(entries) == 8

    alert_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "ua_alerts_76_alert_level"
    )
    coverage_id = registry.async_get_entity_id(
        "sensor", DOMAIN, "ua_alerts_76_alert_coverage"
    )
    assert alert_id == "sensor.ua_76_level"
    assert coverage_id == "sensor.ua_76_coverage"
    assert hass.states[alert_id].state == "red"
    assert hass.states[alert_id].attributes["level_code"] == "red"
    assert hass.states[alert_id].attributes["possible_level_codes"] == [
        "clear",
        "yellow",
        "red",
    ]

    coverage = hass.states[coverage_id]
    assert coverage.state == "partial"
    assert coverage.attributes["coverage_code"] == "partial"
    assert coverage.attributes["possible_coverage_codes"] == [
        "none",
        "full",
        "partial",
        "mixed",
    ]
    assert coverage.attributes["full_level_code"] == "clear"
    assert coverage.attributes["partial_level_code"] == "red"
    assert coverage.attributes["possible_level_codes"] == [
        "clear",
        "yellow",
        "red",
    ]
    assert coverage.attributes["active_full_alert_location_uids"] == []
    assert coverage.attributes["active_partial_alert_location_uids"] == ["726"]

    assert await hass.config_entries.async_unload(config_entry.entry_id)
