from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "custom_components" / "ua_alerts"


def _integration_version_from_const() -> str:
    """Return the integration version declared by the Python package."""
    source = (INTEGRATION / "const.py").read_text(encoding="utf-8")
    match = re.search(r'^VERSION = "([^"]+)"$', source, re.MULTILINE)
    assert match is not None
    return match.group(1)


def test_manifest_contract():
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["domain"] == "ua_alerts"
    assert manifest["version"] == _integration_version_from_const()
    assert re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"])
    assert manifest["config_flow"] is True
    assert manifest["iot_class"] == "cloud_polling"


def test_hacs_contract():
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert hacs["name"] == "UA Alerts"
    assert hacs["country"] == "UA"
    assert hacs["render_readme"] is True


def test_public_repository_documentation_contract():
    assert (ROOT / "LICENSE").is_file()
    assert "MIT License" in (ROOT / "LICENSE").read_text(encoding="utf-8")
    for root_doc in ("README.md", "CHANGELOG.md", "ARCHITECTURE.md", "TESTING.md"):
        assert (ROOT / root_doc).is_file()
    for lang in ("en", "ru", "uk"):
        for doc in ("README.md", "CHANGELOG.md", "ARCHITECTURE.md", "TESTING.md"):
            assert (ROOT / "docs" / lang / doc).is_file()



def test_location_catalog_has_unique_uids_and_required_examples():
    items = json.loads((INTEGRATION / "locations.json").read_text(encoding="utf-8"))
    by_uid = {item["location_uid"]: item for item in items}
    assert len(items) == len(by_uid)
    assert by_uid["31"]["location_title"] == "м. Київ"
    assert by_uid["31"]["location_type"] == "city"
    assert by_uid["14"]["location_title"] == "Київська область"
    assert by_uid["75"]["location_title"] == "Бучанський район"
    assert all(item["location_type"] in {"oblast", "raion", "city", "hromada", "unknown"} for item in items)


def test_exact_entity_contract_no_extras():
    sensor_source = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
    binary_source = (INTEGRATION / "binary_sensor.py").read_text(encoding="utf-8")
    for key in ("alert_level", "alert_coverage", "threat_codes", "last_alert_duration", "last_alert_level", "last_alert_delay", "last_threat_delay", "data_health"):
        assert f'key="{key}"' in sensor_source
    for removed in (
        "data_age", "event_time", "source_updated", "received_at",
        "source_processing_latency", "delivery_latency", "observed_latency",
    ):
        assert f'key="{removed}"' not in sensor_source
    assert len(re.findall(r'UAAlertsSensorDescription\(\s*key="', sensor_source)) == 8
    for key in ("air_alert", "source_available"):
        assert f'key="{key}"' in binary_source
    assert len(re.findall(r'UAAlertsBinarySensorDescription\(\s*key="', binary_source)) == 2


def test_three_translation_catalogues_have_same_top_level_sections():
    docs = [json.loads((INTEGRATION / "translations" / f"{lang}.json").read_text(encoding="utf-8")) for lang in ("en", "ru", "uk")]
    for data in docs:
        assert set(data) == {"title", "config", "entity", "options", "selector"}
        assert set(data["entity"]) == {"sensor", "binary_sensor"}


def test_hacs_targets_current_home_assistant_series():
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert hacs["homeassistant"] == "2026.9.0"


def test_repository_has_readme_and_hacs_validation_workflows():
    assert (ROOT / "README.md").is_file()
    assert (ROOT / ".github" / "workflows" / "tests.yaml").is_file()
    assert (ROOT / ".github" / "workflows" / "hacs.yaml").is_file()
    assert (ROOT / ".github" / "workflows" / "hassfest.yaml").is_file()


def test_ci_targets_python_314_and_current_ha_test_stack():
    workflow = (ROOT / ".github" / "workflows" / "tests.yaml").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements_test.txt").read_text(encoding="utf-8")
    assert 'python-version: "3.14"' in workflow
    assert "cache-dependency-path: requirements_test.txt" in workflow
    assert "homeassistant==2026.9.1" in requirements
    assert "pytest-homeassistant-custom-component==0.13.364" in requirements


def test_config_flow_uses_searchable_dropdown_selector():
    source = (INTEGRATION / "config_flow.py").read_text(encoding="utf-8")
    assert "SelectSelectorMode.DROPDOWN" in source


def test_local_brand_icon_meets_hacs_shape_contract():
    import struct

    def png_size(path: Path) -> tuple[int, int]:
        data = path.read_bytes()
        assert data[:8] == b"\x89PNG\r\n\x1a\n"
        assert data[12:16] == b"IHDR"
        return struct.unpack(">II", data[16:24])

    icon = INTEGRATION / "brand" / "icon.png"
    icon_2x = INTEGRATION / "brand" / "icon@2x.png"
    assert icon.is_file()
    assert icon_2x.is_file()
    assert png_size(icon) == (256, 256)
    assert png_size(icon_2x) == (512, 512)


def test_hacs_validation_has_no_ignored_checks():
    for name in ("hacs.yaml", "hassfest.yaml"):
        workflow = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
        assert "ignore:" not in workflow


def test_translation_catalogues_include_hierarchical_flow_and_global_options():
    for lang in ("en", "ru", "uk"):
        data = json.loads((INTEGRATION / "translations" / f"{lang}.json").read_text(encoding="utf-8"))
        steps = data["config"]["step"]
        assert {"user", "search", "search_results", "tree", "scope", "raion", "hromada", "fallback"}.issubset(steps)
        assert set(data["selector"]["territory_scope"]["options"]) == {"oblast", "raion", "hromada"}
        option_steps = data["options"]["step"]
        assert {"init", "timing", "refresh_catalog_failed"}.issubset(option_steps)
        assert set(option_steps["timing"]["data"]) == {"poll_interval", "stale_after"}
        assert set(option_steps["init"]["menu_options"]) == {"timing", "refresh_catalog"}


def test_config_flow_uses_hierarchy_and_domain_wide_options():
    source = (INTEGRATION / "config_flow.py").read_text(encoding="utf-8")
    assert "async_step_search" in source
    assert "async_step_search_results" in source
    assert "async_step_tree" in source
    assert "async_step_scope" in source
    assert "async_step_raion" in source
    assert "async_step_hromada" in source
    assert 'translation_key="territory_scope"' in source
    assert "async_get_options_flow" in source
    assert "runtime.async_update_timing" in source


def test_catalog_refresh_is_not_part_of_alert_polling_runtime():
    catalog_source = (INTEGRATION / "catalog.py").read_text(encoding="utf-8")
    runtime_source = (INTEGRATION / "runtime.py").read_text(encoding="utf-8")
    assert "CATALOG_URL" in catalog_source
    assert "CATALOG_REFRESH_SECONDS" not in catalog_source
    assert "async_refresh_catalog" in catalog_source
    assert "session.get(CATALOG_URL)" not in catalog_source.split("async def async_load_catalog", 1)[1].split("async def async_refresh_catalog", 1)[0]
    assert "CATALOG_URL" not in runtime_source


def test_user_facing_threats_keep_technical_codes_in_attributes():
    source = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
    display = (INTEGRATION / "display.py").read_text(encoding="utf-8")
    assert "threat_state_key" in source
    assert "hass.config.language" not in source
    assert "ATTR_LEVEL_CODE" in source
    assert "ATTR_THREAT_CODES" in source
    assert "ATTR_THREAT_CODES_CSV" in source
    for code in (
        "tactic_aircraft_activity", "strategic_aircraft_activity", "mig31k_departure",
        "ballistic_missiles", "cruise_missiles", "unspecified_missiles", "drones",
        "guided_aerial_bombs", "air_defense", "unknown"
    ):
        assert code in display


def test_device_name_is_raw_catalog_title_and_service_metadata_is_useful():
    source = (INTEGRATION / "entity.py").read_text(encoding="utf-8")
    const_source = (INTEGRATION / "const.py").read_text(encoding="utf-8")
    manifest = json.loads((INTEGRATION / "manifest.json").read_text(encoding="utf-8"))

    # Do not translate/freeze a device name in the backend language.
    assert "name=coordinator.location_title" in source
    assert "translation_key=None" in source
    assert "translation_placeholders=None" in source
    assert "territory_city" not in source

    # A configured territory is represented as a cloud service, not hardware.
    assert "entry_type=DeviceEntryType.SERVICE" in source
    assert 'manufacturer="UA Alerts"' in source
    assert "sw_version=VERSION" in source
    assert "configuration_url=SOURCE_URL" in source
    assert "model=None" in source
    assert "model_id=None" in source
    assert "hw_version=None" in source
    assert "serial_number=None" in source

    # One version source for both the manifest and the device info card.
    assert manifest["version"] == _integration_version_from_const()


def test_device_translations_removed_because_device_name_is_locale_neutral():
    for language in ("en", "ru", "uk"):
        translations = json.loads(
            (INTEGRATION / "translations" / f"{language}.json").read_text(encoding="utf-8")
        )
        assert "device" not in translations
        threat_states = translations["entity"]["sensor"]["threat_codes"]["state"]
        assert "drones" in threat_states
        assert "cruise_missiles_and_drones" in threat_states


def test_catalog_refresh_is_explicit_in_both_setup_and_options():
    source = (INTEGRATION / "config_flow.py").read_text(encoding="utf-8")
    assert "async_step_catalog_setup" in source
    assert "async_step_refresh_catalog_setup" in source
    assert "async_step_refresh_catalog" in source
    assert 'menu_options=["timing", "refresh_catalog"]' in source


def test_last_alert_state_sensor_contract():
    sensor_source = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
    coordinator_source = (INTEGRATION / "coordinator.py").read_text(encoding="utf-8")
    models_source = (INTEGRATION / "models.py").read_text(encoding="utf-8")

    for key in (
        "last_alert_duration", "last_alert_level",
        "last_alert_delay", "last_threat_delay",
    ):
        assert f'key="{key}"' in sensor_source
    assert 'key="alert_latency"' not in sensor_source
    assert 'key="threat_latency"' not in sensor_source
    assert "AlertHistoryTracker" in coordinator_source
    assert "ActiveAlertLifecycle" in models_source
    assert "LastAlertMeasurement" in models_source
    assert "EntityCategory.DIAGNOSTIC" in sensor_source  # data_health only


def test_translation_catalogues_have_last_alert_state_names():
    expected = {
        "en": (
            "Last alert duration", "Last alert level",
            "Last alert delay", "Last threat delay",
        ),
        "ru": (
            "Длительность последней тревоги", "Уровень последней тревоги",
            "Задержка последней тревоги", "Задержка последней угрозы",
        ),
        "uk": (
            "Тривалість останньої тривоги", "Рівень останньої тривоги",
            "Затримка останньої тривоги", "Затримка останньої загрози",
        ),
    }
    for lang, names in expected.items():
        data = json.loads(
            (INTEGRATION / "translations" / f"{lang}.json").read_text(encoding="utf-8")
        )
        sensors = data["entity"]["sensor"]
        keys = (
            "last_alert_duration", "last_alert_level",
            "last_alert_delay", "last_threat_delay",
        )
        assert tuple(sensors[key]["name"] for key in keys) == names
        assert "alert_latency" not in sensors
        assert "threat_latency" not in sensors


def test_bundled_catalog_is_full_and_preserves_current_hierarchy():
    items = json.loads((INTEGRATION / "locations.json").read_text(encoding="utf-8"))
    by_uid = {item["location_uid"]: item for item in items}

    assert len(items) == 1607
    assert len(by_uid) == 1607
    counts = {}
    for item in items:
        counts[item["location_type"]] = counts.get(item["location_type"], 0) + 1
    assert counts == {"city": 2, "oblast": 25, "hromada": 1458, "raion": 122} or counts == {"city": 2, "oblast": 25, "raion": 122, "hromada": 1458}

    assert by_uid["31"]["location_title"] == "м. Київ"
    assert by_uid["30"]["location_title"] == "м. Севастополь"
    assert by_uid["29"]["location_title"] == "Автономна Республіка Крим"
    assert by_uid["76"]["location_title"] == "Обухівський район"
    assert by_uid["726"]["location_title"] == "Кагарлицька територіальна громада"
    assert by_uid["726"]["oblast_uid"] == "14"
    assert by_uid["726"]["raion_uid"] == "76"
    assert by_uid["699"]["oblast_uid"] == "14"
    assert by_uid["699"]["raion_uid"] == "75"
    assert by_uid["1611"]["location_type"] == "hromada"


def test_bundled_catalog_has_current_renamed_districts():
    items = json.loads((INTEGRATION / "locations.json").read_text(encoding="utf-8"))
    by_uid = {item["location_uid"]: item for item in items}
    expected = {
        "38": "Володимирський район",
        "43": "Самарівський район",
        "60": "Звягельський район",
        "84": "Сіверськодонецький район",
        "92": "Шептицький район",
        "127": "Берестинський район",
    }
    assert {uid: by_uid[uid]["location_title"] for uid in expected} == expected


def test_config_flow_offers_independent_search_and_tree_paths():
    source = (INTEGRATION / "config_flow.py").read_text(encoding="utf-8")
    assert 'menu_options=["search", "tree"]' in source
    assert "async_step_search" in source
    assert "async_step_search_results" in source
    assert "async_step_tree" in source
    assert "search_catalog(self._catalog, query)" in source


def test_release_update_script_writes_full_hierarchy_snapshot():
    source = (ROOT / "scripts" / "update_locations.py").read_text(encoding="utf-8")
    assert "parse_catalog_csv" in source
    assert "validate_full=True" in source
    assert "asdict" in source


def test_short_entity_id_contract_and_unique_ids_stay_stable():
    entity_source = (INTEGRATION / "entity.py").read_text(encoding="utf-8")
    ids_source = (INTEGRATION / "entity_ids.py").read_text(encoding="utf-8")
    init_source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")

    # Entity IDs are deliberately short and based only on stable territory UID.
    for key, suffix in {
        "alert_level": "level",
        "alert_coverage": "coverage",
        "threat_codes": "threats",
        "last_alert_duration": "last_alert_duration",
        "last_alert_level": "last_alert_level",
        "last_alert_delay": "last_alert_delay",
        "last_threat_delay": "last_threat_delay",
        "data_health": "health",
        "air_alert": "alert",
        "source_available": "source",
    }.items():
        assert f'"{key}":' in ids_source
        assert f'"{suffix}"' in ids_source

    assert "def suggested_object_id" in entity_source
    assert "short_object_id(self.coordinator.location_uid, self._key)" in entity_source

    # Internal unique IDs stay unchanged for registry continuity.
    assert 'self._attr_unique_id = f"{DOMAIN}_{coordinator.location_uid}_{key}"' in entity_source

    # Existing automatic IDs are migrated, but user-renamed IDs are preserved.
    assert "async_regenerate_entity_id" in init_source
    assert "new_entity_id=target_entity_id" in init_source
    assert "legacy_default_entity_id" in init_source

    # Deleted registry entries restore their old entity_id during platform setup,
    # therefore migration must also run after forwarded platforms have loaded.
    forward_pos = init_source.index("async_forward_entry_setups(entry, PLATFORMS)")
    post_migrate_pos = init_source.index(
        "_async_migrate_default_entity_ids(hass, entry)", forward_pos
    )
    assert post_migrate_pos > forward_pos


def test_data_health_sensor_is_one_aggregate_diagnostic_entity():
    sensor_source = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
    coordinator_source = (INTEGRATION / "coordinator.py").read_text(encoding="utf-8")
    health_source = (INTEGRATION / "health.py").read_text(encoding="utf-8")

    assert 'key="data_health"' in sensor_source
    assert 'translation_key="data_health"' in sensor_source
    assert "EntityCategory.DIAGNOSTIC" in sensor_source
    assert "return True" in sensor_source  # remains visible during source/data failure
    assert "evaluate_data_health" in coordinator_source
    assert "HEALTH_DETAILS_REFRESH_SECONDS" in coordinator_source
    assert '"source_response"' in health_source
    assert '"alert_latency"' not in health_source
    assert '"threat_latency"' not in health_source


def test_data_health_translations_are_frontend_enum_states():
    expected = {
        "en": ("Data status", "Normal", "Delayed", "Source error", "Data error"),
        "ru": ("Состояние данных", "Норма", "Задержка", "Ошибка источника", "Ошибка данных"),
        "uk": ("Стан даних", "Норма", "Затримка", "Помилка джерела", "Помилка даних"),
    }
    for lang, (name, normal, delayed, source_error, data_error) in expected.items():
        data = json.loads(
            (INTEGRATION / "translations" / f"{lang}.json").read_text(encoding="utf-8")
        )
        item = data["entity"]["sensor"]["data_health"]
        assert item["name"] == name
        assert item["state"] == {
            "normal": normal,
            "delayed": delayed,
            "source_error": source_error,
            "data_error": data_error,
        }


def test_latency_measurements_are_persisted_per_location_uid():
    init_source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
    coordinator_source = (INTEGRATION / "coordinator.py").read_text(encoding="utf-8")
    storage_source = (INTEGRATION / "latency_storage.py").read_text(encoding="utf-8")

    assert "LatencyStorage(hass, location_uid)" in init_source
    assert "await latency_storage.async_load()" in init_source
    assert "measurement=restored_latencies.alert" in coordinator_source
    assert "measurement=restored_latencies.threat" in coordinator_source
    assert "_schedule_latency_save" in coordinator_source
    assert "await self._latency_storage.async_save" in coordinator_source
    assert "homeassistant.helpers.storage import Store" in storage_source
    assert "LATENCY_STORAGE_KEY_FORMAT" in storage_source


def test_health_does_not_classify_end_to_end_latency_as_delayed():
    coordinator_source = (INTEGRATION / "coordinator.py").read_text(encoding="utf-8")
    health_source = (INTEGRATION / "health.py").read_text(encoding="utf-8")

    health_call = coordinator_source.split("evaluation = evaluate_data_health(", 1)[1].split(")", 1)[0]
    assert "alert_latency" not in health_call
    assert "threat_latency" not in health_call
    assert "Upstream publication delay" in health_source


def test_alert_level_exposes_possible_machine_codes():
    sensor_source = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
    const_source = (INTEGRATION / "const.py").read_text(encoding="utf-8")
    assert 'ATTR_POSSIBLE_LEVEL_CODES = "possible_level_codes"' in const_source
    assert "ATTR_POSSIBLE_LEVEL_CODES" in sensor_source
    assert "ALERT_LEVEL_CLEAR" in sensor_source
    assert "ALERT_LEVEL_YELLOW" in sensor_source
    assert "ALERT_LEVEL_RED" in sensor_source


def test_alert_coverage_sensor_is_for_raion_and_oblast_only():
    sensor_source = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
    init_source = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
    ids_source = (INTEGRATION / "entity_ids.py").read_text(encoding="utf-8")
    models_source = (INTEGRATION / "models.py").read_text(encoding="utf-8")

    assert 'key="alert_coverage"' in sensor_source
    assert 'translation_key="alert_coverage"' in sensor_source
    assert 'coordinator.location_type in {"oblast", "raion"}' in sensor_source
    assert '"alert_coverage": ("sensor", "coverage")' in ids_source
    assert "descendant_locations_for(location_definition, catalog)" in init_source
    assert "ALERT_COVERAGE_PARTIAL" in models_source
    assert "ALERT_COVERAGE_MIXED" in models_source


def test_alert_coverage_translations_are_frontend_enum_states():
    expected = {
        "en": ("Alert coverage", "No alert", "Full", "Partial", "Mixed"),
        "ru": ("Охват тревоги", "Нет тревоги", "Полный", "Частичный", "Смешанный"),
        "uk": ("Охоплення тривоги", "Немає тривоги", "Повне", "Часткове", "Змішане"),
    }
    for lang, (name, none, full, partial, mixed) in expected.items():
        data = json.loads(
            (INTEGRATION / "translations" / f"{lang}.json").read_text(encoding="utf-8")
        )
        item = data["entity"]["sensor"]["alert_coverage"]
        assert item["name"] == name
        assert item["state"] == {
            "none": none,
            "full": full,
            "partial": partial,
            "mixed": mixed,
        }


def test_alert_coverage_exposes_machine_codes_and_components():
    sensor_source = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
    for name in (
        "ATTR_COVERAGE_CODE",
        "ATTR_POSSIBLE_COVERAGE_CODES",
        "ATTR_FULL_LEVEL_CODE",
        "ATTR_PARTIAL_LEVEL_CODE",
        "ATTR_POSSIBLE_LEVEL_CODES",
        "ATTR_ACTIVE_FULL_ALERT_LOCATION_UIDS",
        "ATTR_ACTIVE_PARTIAL_ALERT_LOCATION_UIDS",
    ):
        assert name in sensor_source


def test_russian_frontend_threat_states_use_compact_labels():
    data = json.loads((INTEGRATION / "translations" / "ru.json").read_text(encoding="utf-8"))
    states = data["entity"]["sensor"]["threat_codes"]["state"]
    assert states["tactic_aircraft_activity"] == "Тактическая"
    assert states["strategic_aircraft_activity"] == "Стратегическая"
    assert states["mig31k_departure"] == "МиГ-31К"
    assert states["ballistic_missiles"] == "Баллистика"
    assert states["cruise_missiles"] == "Крылатые"
    assert states["unspecified_missiles"] == "Ракеты"
    assert states["drones"] == "БПЛА"
    assert states["guided_aerial_bombs"] == "КАБ"
    assert states["air_defense"] == "ПВО"
    assert states["unknown"] == "Неизвестно"
    assert states["tactic_aircraft_activity_and_ballistic_missiles_and_drones"] == "Тактическая, Баллистика, БПЛА"


def test_threat_sensor_exposes_all_possible_machine_codes():
    sensor_source = (INTEGRATION / "sensor.py").read_text(encoding="utf-8")
    const_source = (INTEGRATION / "const.py").read_text(encoding="utf-8")
    assert 'ATTR_POSSIBLE_THREAT_CODES = "possible_threat_codes"' in const_source
    assert "ATTR_POSSIBLE_THREAT_CODES: list(THREAT_CODE_ORDER)" in sensor_source


def test_possible_threat_code_order_matches_current_alerts_enum():
    import ast

    source = (INTEGRATION / "display.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    value = next(
        ast.literal_eval(node.value)
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "THREAT_CODE_ORDER" for target in node.targets)
    )
    assert value == (
        "tactic_aircraft_activity",
        "strategic_aircraft_activity",
        "mig31k_departure",
        "ballistic_missiles",
        "cruise_missiles",
        "unspecified_missiles",
        "drones",
        "guided_aerial_bombs",
        "air_defense",
        "unknown",
    )
