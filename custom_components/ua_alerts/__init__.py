"""UA Alerts integration."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

from .catalog import async_load_catalog
from .const import CONF_LOCATION_TITLE, CONF_LOCATION_TYPE, CONF_LOCATION_UID, DOMAIN
from .coordinator import UAAlertsCoordinator
from .entity_ids import ENTITY_ID_SPECS, legacy_default_entity_id, short_entity_id
from .frontend import async_setup_frontend
from .latency_storage import LatencyStorage, RestoredLatencyMeasurements
from .models import LocationDefinition, descendant_locations_for
from .runtime import UAAlertsRuntime
from .settings import async_get_settings
from .websocket_api import async_register_websocket_handlers

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

_LEGACY_DIAGNOSTIC_SENSOR_KEYS = (
    "data_age",
    "event_time",
    "source_updated",
    "received_at",
    "source_processing_latency",
    "delivery_latency",
    "observed_latency",
    "source_response_time",
)


def _async_remove_legacy_diagnostic_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove obsolete high-churn diagnostic entities from <= 0.1.4."""
    registry = er.async_get(hass)
    location_uid = str(entry.data[CONF_LOCATION_UID])
    for key in _LEGACY_DIAGNOSTIC_SENSOR_KEYS:
        unique_id = f"{DOMAIN}_{location_uid}_{key}"
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, unique_id)
        if entity_id is not None:
            registry.async_remove(entity_id)

def _async_migrate_last_lag_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Migrate legacy latency/delay entities to their 0.1.23 Last ... lag names."""
    registry = er.async_get(hass)
    location_uid = str(entry.data[CONF_LOCATION_UID])
    location_slug = slugify(str(entry.data[CONF_LOCATION_TITLE]))
    migrations = (
        ("alert_latency", "last_alert_lag"),
        ("last_alert_delay", "last_alert_lag"),
        ("threat_latency", "last_threat_lag"),
        ("last_threat_delay", "last_threat_lag"),
    )
    for old_key, new_key in migrations:
        old_unique_id = f"{DOMAIN}_{location_uid}_{old_key}"
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, old_unique_id)
        if entity_id is None:
            continue

        new_unique_id = f"{DOMAIN}_{location_uid}_{new_key}"
        if registry.async_get_entity_id("sensor", DOMAIN, new_unique_id) is not None:
            _LOGGER.warning(
                "Cannot migrate %s because %s already exists",
                old_unique_id,
                new_unique_id,
            )
            continue

        automatic_ids = {
            f"sensor.ua_{location_uid}_{old_key}",
            f"sensor.{location_slug}_{old_key}",
        }
        update: dict[str, str] = {"new_unique_id": new_unique_id}
        if entity_id in automatic_ids:
            target = f"sensor.ua_{location_uid}_{new_key}"
            if registry.async_get(target) is None:
                update["new_entity_id"] = target

        registry.async_update_entity(entity_id, **update)


def _async_migrate_default_entity_ids(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Shorten legacy automatically generated entity IDs.

    Home Assistant keeps entity IDs in the entity registry, so changing the
    integration's suggestion only affects newly created entities. Existing
    entries are renamed when their current ID still matches what HA itself would
    generate from the stored registry metadata, or when it exactly matches the
    pre-0.1.8 automatic location-prefixed pattern restored from a deleted-entry
    tombstone. Other customized IDs are left untouched.
    """
    registry = er.async_get(hass)
    location_uid = str(entry.data[CONF_LOCATION_UID])
    location_slug = slugify(str(entry.data[CONF_LOCATION_TITLE]))

    for key, (entity_domain, _suffix) in ENTITY_ID_SPECS.items():
        unique_id = f"{DOMAIN}_{location_uid}_{key}"
        current_entity_id = registry.async_get_entity_id(
            entity_domain, DOMAIN, unique_id
        )
        if current_entity_id is None:
            continue

        registry_entry = registry.async_get(current_entity_id)
        if registry_entry is None:
            continue

        target_entity_id = short_entity_id(location_uid, key)
        if target_entity_id == current_entity_id:
            continue

        # Preserve manually renamed entity IDs. For an untouched *active* registry
        # entry, regenerating from the stored naming metadata yields the current
        # ID. There is one important exception: when a Config Entry was removed,
        # Home Assistant stores a DeletedRegistryEntry containing the old
        # entity_id but not suggested_object_id/object_id_base. Re-adding the same
        # unique_id restores that legacy entity_id first, then applies our current
        # naming metadata. At that point async_regenerate_entity_id() correctly
        # returns the new UID-based ID and therefore makes the restored old
        # automatic ID look indistinguishable from a user customization.
        #
        # Recognize the exact pre-0.1.8 automatic pattern as a migration-safe
        # legacy ID. Arbitrary user IDs remain untouched.
        known_legacy_default = legacy_default_entity_id(location_slug, key)
        if (
            current_entity_id != known_legacy_default
            and registry.async_regenerate_entity_id(registry_entry) != current_entity_id
        ):
            _LOGGER.debug(
                "Preserving customized entity id %s for %s",
                current_entity_id,
                unique_id,
            )
            continue

        try:
            registry.async_update_entity(
                current_entity_id, new_entity_id=target_entity_id
            )
        except ValueError:
            # Never steal an ID from another entity. A new entity would receive
            # HA's normal numeric suffix; an existing one is safer left intact.
            _LOGGER.warning(
                "Could not migrate %s to %s because the target entity id is in use",
                current_entity_id,
                target_entity_id,
            )


PLATFORMS: tuple[Platform, ...] = (
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
)


@dataclass(slots=True)
class UAAlertsDomainData:
    """Domain-scoped singleton container."""

    runtime: UAAlertsRuntime | None = None
    runtime_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up domain-level data."""
    hass.data.setdefault(DOMAIN, UAAlertsDomainData())
    async_register_websocket_handlers(hass)
    await async_setup_frontend(hass)
    return True


async def _async_prepare_coordinator(
    hass: HomeAssistant,
    entry: ConfigEntry,
    *,
    location_definition: LocationDefinition | None,
    descendant_definitions: tuple[LocationDefinition, ...],
    latency_storage: LatencyStorage,
    restored_latencies: RestoredLatencyMeasurements,
) -> UAAlertsCoordinator:
    """Atomically get/create the singleton runtime and register this entry.

    Registering while holding the domain lock prevents a last-entry unload from
    dropping the domain reference between runtime lookup and entry registration.
    No network I/O is awaited while this lock is held.
    """
    domain_data: UAAlertsDomainData = hass.data.setdefault(DOMAIN, UAAlertsDomainData())
    settings = await async_get_settings(hass)
    async with domain_data.runtime_lock:
        if domain_data.runtime is None:
            domain_data.runtime = UAAlertsRuntime(
                hass,
                poll_interval=settings.poll_interval,
                stale_after=settings.stale_after,
            )
        coordinator = UAAlertsCoordinator(
            hass,
            entry,
            domain_data.runtime,
            location_definition=location_definition,
            descendant_definitions=descendant_definitions,
            latency_storage=latency_storage,
            restored_latencies=restored_latencies,
        )
        entry.runtime_data = coordinator
        await coordinator.async_register_runtime()
        return coordinator


async def _async_remove_runtime_if_unused(
    hass: HomeAssistant,
    runtime: UAAlertsRuntime,
) -> None:
    domain_data: UAAlertsDomainData = hass.data[DOMAIN]
    async with domain_data.runtime_lock:
        if domain_data.runtime is runtime and runtime.registered_entry_count == 0:
            domain_data.runtime = None


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up one configured territory."""
    _async_remove_legacy_diagnostic_entities(hass, entry)
    _async_migrate_last_lag_entities(hass, entry)
    _async_migrate_default_entity_ids(hass, entry)
    settings = await async_get_settings(hass)
    if dict(entry.options) != settings.as_options():
        hass.config_entries.async_update_entry(entry, options=settings.as_options())

    location_uid = str(entry.data[CONF_LOCATION_UID])
    catalog = await async_load_catalog(hass)
    location_definition = next(
        (item for item in catalog if item.location_uid == location_uid),
        None,
    )
    if location_definition is None:
        # Preserve exact-UID behavior for a legacy/custom entry whose territory is
        # absent from the currently available catalog. Hierarchical inheritance is
        # enabled automatically as soon as the catalog can resolve the territory.
        location_definition = LocationDefinition(
            location_uid=location_uid,
            location_title=str(entry.data[CONF_LOCATION_TITLE]),
            location_type=str(entry.data[CONF_LOCATION_TYPE]),
        )

    descendant_definitions = descendant_locations_for(location_definition, catalog)

    latency_storage = LatencyStorage(hass, location_uid)
    restored_latencies = await latency_storage.async_load()

    coordinator = await _async_prepare_coordinator(
        hass,
        entry,
        location_definition=location_definition,
        descendant_definitions=descendant_definitions,
        latency_storage=latency_storage,
        restored_latencies=restored_latencies,
    )
    runtime = coordinator.runtime

    try:
        await coordinator.async_wait_initial_cycle()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        # A removed Config Entry leaves entity-registry tombstones. Home Assistant
        # restores their old entity_id only while the platforms are being set up,
        # so the pre-platform migration above cannot see them. Run the same safe
        # migration once more after entity creation to catch restored legacy IDs
        # such as sensor.m_kiiv_threat_codes -> sensor.ua_31_threats.
        _async_migrate_default_entity_ids(hass, entry)
    except Exception:
        _LOGGER.exception("Failed to set up UA Alerts entry %s", entry.entry_id)
        await coordinator.async_shutdown()
        await _async_remove_runtime_if_unused(hass, runtime)
        raise
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload one configured territory."""
    coordinator: UAAlertsCoordinator = entry.runtime_data
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if not unload_ok:
        return False

    runtime = coordinator.runtime
    await coordinator.async_shutdown()
    await _async_remove_runtime_if_unused(hass, runtime)
    return True
