"""Number platform for UA Alerts global timing settings."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    MAX_POLL_INTERVAL_SECONDS,
    MAX_STALE_AFTER_SECONDS,
    MIN_POLL_INTERVAL_SECONDS,
    MIN_STALE_AFTER_SECONDS,
    OPT_POLL_INTERVAL,
    OPT_STALE_AFTER,
)
from .coordinator import UAAlertsCoordinator
from .entity import UAAlertsEntity
from .settings import async_apply_settings
from .timing import validate_settings


NUMBERS: tuple[NumberEntityDescription, ...] = (
    NumberEntityDescription(
        key=OPT_POLL_INTERVAL,
        translation_key=OPT_POLL_INTERVAL,
        entity_category=EntityCategory.CONFIG,
    ),
    NumberEntityDescription(
        key=OPT_STALE_AFTER,
        translation_key=OPT_STALE_AFTER,
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up editable global timing numbers on one territory device."""
    coordinator: UAAlertsCoordinator = entry.runtime_data
    async_add_entities(
        UAAlertsNumber(coordinator, description) for description in NUMBERS
    )


class UAAlertsNumber(UAAlertsEntity, NumberEntity):
    """One domain-wide timing setting exposed on a territory device."""

    _attr_native_step = 1.0
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS

    entity_description: NumberEntityDescription

    def __init__(
        self,
        coordinator: UAAlertsCoordinator,
        description: NumberEntityDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float:
        """Return the current shared runtime value."""
        if self.entity_description.key == OPT_POLL_INTERVAL:
            return self.coordinator.runtime.poll_interval
        return self.coordinator.runtime.stale_after

    @property
    def native_min_value(self) -> float:
        """Return the minimum valid value given the paired setting."""
        if self.entity_description.key == OPT_POLL_INTERVAL:
            return MIN_POLL_INTERVAL_SECONDS
        return max(
            MIN_STALE_AFTER_SECONDS,
            self.coordinator.runtime.poll_interval * 2,
        )

    @property
    def native_max_value(self) -> float:
        """Return the maximum valid value given the paired setting."""
        if self.entity_description.key == OPT_POLL_INTERVAL:
            return min(
                MAX_POLL_INTERVAL_SECONDS,
                self.coordinator.runtime.stale_after / 2,
            )
        return MAX_STALE_AFTER_SECONDS

    async def async_set_native_value(self, value: float) -> None:
        """Update one shared setting and propagate it to every territory."""
        runtime = self.coordinator.runtime
        if self.entity_description.key == OPT_POLL_INTERVAL:
            settings = validate_settings(value, runtime.stale_after)
        else:
            settings = validate_settings(runtime.poll_interval, value)
        await async_apply_settings(self.hass, settings)
