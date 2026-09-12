"""Base entity for UA Alerts."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, VERSION
from .coordinator import UAAlertsCoordinator
from .entity_ids import short_object_id


class UAAlertsEntity(CoordinatorEntity[UAAlertsCoordinator]):
    """Base entity attached to one configured territory."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: UAAlertsCoordinator, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        self._attr_unique_id = f"{DOMAIN}_{coordinator.location_uid}_{key}"

        # A territory is a logical cloud service, not a hardware model.
        # Use the catalog title verbatim as the device name so it is stable and
        # independent of the Home Assistant backend language. Territory titles
        # already carry their human-readable type ("м.", "область", "район",
        # "територіальна громада") where relevant.
        #
        # translation_key/translation_placeholders are explicitly set to None to
        # migrate devices created by <= 0.1.3, where the translated device name
        # could be frozen in the backend language (for example "City: м. Київ").
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.location_uid)},
            entry_type=DeviceEntryType.SERVICE,
            name=coordinator.location_title,
            translation_key=None,
            translation_placeholders=None,
            manufacturer="UA Alerts",
            sw_version=VERSION,
            configuration_url=(
                f"homeassistant://config/integrations/integration/{DOMAIN}"
                f"#config_entry={coordinator.entry.entry_id}"
            ),
            # Explicitly clear legacy metadata from previous builds.
            model=None,
            model_id=None,
            hw_version=None,
            serial_number=None,
        )

    @property
    def suggested_object_id(self) -> str:
        """Suggest a short, stable entity id independent of territory title."""
        return short_object_id(self.coordinator.location_uid, self._key)
