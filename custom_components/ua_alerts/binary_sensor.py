"""Binary sensor platform for UA Alerts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ALERT_LEVEL_RED, ALERT_LEVEL_YELLOW
from .coordinator import UAAlertsCoordinator
from .entity import UAAlertsEntity
from .models import LocationState


@dataclass(frozen=True, kw_only=True)
class UAAlertsBinarySensorDescription(BinarySensorEntityDescription):
    """Describe a UA Alerts binary sensor."""

    value_fn: Callable[[LocationState], bool]
    source_availability_sensor: bool = False


BINARY_SENSORS: tuple[UAAlertsBinarySensorDescription, ...] = (
    UAAlertsBinarySensorDescription(
        key="air_alert",
        translation_key="air_alert",
        value_fn=lambda state: state.level in (ALERT_LEVEL_YELLOW, ALERT_LEVEL_RED),
    ),
    UAAlertsBinarySensorDescription(
        key="source_available",
        translation_key="source_available",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda state: state.source_available,
        source_availability_sensor=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensors for one territory."""
    coordinator: UAAlertsCoordinator = entry.runtime_data
    async_add_entities(
        UAAlertsBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class UAAlertsBinarySensor(UAAlertsEntity, BinarySensorEntity):
    """One UA Alerts binary sensor."""

    entity_description: UAAlertsBinarySensorDescription

    def __init__(
        self,
        coordinator: UAAlertsCoordinator,
        description: UAAlertsBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def available(self) -> bool:
        if self.entity_description.source_availability_sensor:
            return True
        return self.coordinator.data.operational_available

    @property
    def is_on(self) -> bool:
        return self.entity_description.value_fn(self.coordinator.data)
