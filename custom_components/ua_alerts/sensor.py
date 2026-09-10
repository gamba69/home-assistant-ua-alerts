"""Sensor platform for UA Alerts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ALERT_COVERAGE_OPTIONS,
    ALERT_LEVEL_CLEAR,
    ALERT_LEVEL_RED,
    ALERT_LEVEL_YELLOW,
    ATTR_ACTIVE_ALERT_LOCATION_UIDS,
    ATTR_ACTIVE_FULL_ALERT_LOCATION_UIDS,
    ATTR_ACTIVE_PARTIAL_ALERT_LOCATION_UIDS,
    ATTR_ALERT_DETECTED_AT,
    ATTR_ALERT_LATENCY,
    ATTR_ALERT_SCOPE,
    ATTR_ALERT_SOURCE_LOCATION_TITLE,
    ATTR_ALERT_SOURCE_LOCATION_TYPE,
    ATTR_ALERT_SOURCE_LOCATION_UID,
    ATTR_ALERT_STARTED_AT,
    ATTR_COVERAGE_CODE,
    ATTR_CONSECUTIVE_ERRORS,
    ATTR_HEALTH_DELAY_REASON,
    ATTR_HTTP_STATUS,
    ATTR_LAST_ERROR,
    ATTR_FULL_LEVEL_CODE,
    ATTR_LEVEL_CODE,
    ATTR_PARTIAL_LEVEL_CODE,
    ATTR_POSSIBLE_COVERAGE_CODES,
    ATTR_POSSIBLE_LEVEL_CODES,
    ATTR_SOURCE_RESPONSE_TIME,
    ATTR_THREATS,
    ATTR_THREAT_CODE,
    ATTR_THREAT_CODES,
    ATTR_POSSIBLE_THREAT_CODES,
    ATTR_THREAT_CODES_CSV,
    ATTR_THREAT_DETECTED_AT,
    ATTR_THREAT_LATENCY,
    ATTR_THREAT_LEVEL_CODE,
    ATTR_THREAT_SOURCE_MESSAGE,
    ATTR_THREAT_STARTED_AT,
    DATA_HEALTH_OPTIONS,
)
from .coordinator import UAAlertsCoordinator
from .display import THREAT_CODE_ORDER, threat_state_key
from .entity import UAAlertsEntity
from .models import LocationState


@dataclass(frozen=True, kw_only=True)
class UAAlertsSensorDescription(SensorEntityDescription):
    """Describe a UA Alerts sensor."""

    value_fn: Callable[[LocationState], Any]
    operational: bool = False


SENSORS: tuple[UAAlertsSensorDescription, ...] = (
    UAAlertsSensorDescription(
        key="alert_level",
        translation_key="alert_level",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda state: state.level,
        operational=True,
    ),
    UAAlertsSensorDescription(
        key="alert_coverage",
        translation_key="alert_coverage",
        device_class=SensorDeviceClass.ENUM,
        value_fn=lambda state: state.coverage_code,
        operational=True,
    ),
    UAAlertsSensorDescription(
        key="threat_codes",
        translation_key="threat_codes",
        value_fn=lambda state: state.threat_codes_state,
        operational=True,
    ),
    UAAlertsSensorDescription(
        key="alert_latency",
        translation_key="alert_latency",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        value_fn=lambda state: state.alert_latency,
    ),
    UAAlertsSensorDescription(
        key="threat_latency",
        translation_key="threat_latency",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        value_fn=lambda state: state.threat_latency,
    ),
    UAAlertsSensorDescription(
        key="data_health",
        translation_key="data_health",
        device_class=SensorDeviceClass.ENUM,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda state: state.health_code,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensors for one territory."""
    coordinator: UAAlertsCoordinator = entry.runtime_data
    descriptions = (
        description
        for description in SENSORS
        if description.key != "alert_coverage"
        or coordinator.location_type in {"oblast", "raion"}
    )
    async_add_entities(UAAlertsSensor(coordinator, description) for description in descriptions)


class UAAlertsSensor(UAAlertsEntity, SensorEntity):
    """One UA Alerts sensor."""

    entity_description: UAAlertsSensorDescription

    def __init__(
        self,
        coordinator: UAAlertsCoordinator,
        description: UAAlertsSensorDescription,
    ) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description
        if description.key == "alert_level":
            self._attr_options = [ALERT_LEVEL_CLEAR, ALERT_LEVEL_YELLOW, ALERT_LEVEL_RED]
        elif description.key == "alert_coverage":
            self._attr_options = list(ALERT_COVERAGE_OPTIONS)
        elif description.key == "data_health":
            self._attr_options = list(DATA_HEALTH_OPTIONS)

    @property
    def available(self) -> bool:
        state = self.coordinator.data
        if self.entity_description.key == "data_health":
            # The health entity must remain available precisely when operational
            # data becomes unavailable or invalid.
            return True
        if self.entity_description.operational:
            return state.operational_available
        return self.entity_description.value_fn(state) is not None

    @property
    def native_value(self) -> Any:
        state = self.coordinator.data
        if self.entity_description.key == "threat_codes":
            return threat_state_key(state.threat_codes)
        return self.entity_description.value_fn(state)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        state = self.coordinator.data
        if self.entity_description.key == "alert_level":
            return {
                ATTR_LEVEL_CODE: state.level,
                ATTR_POSSIBLE_LEVEL_CODES: [
                    ALERT_LEVEL_CLEAR,
                    ALERT_LEVEL_YELLOW,
                    ALERT_LEVEL_RED,
                ],
                ATTR_ALERT_SCOPE: state.alert_scope,
                ATTR_ALERT_SOURCE_LOCATION_UID: state.alert_source_location_uid,
                ATTR_ALERT_SOURCE_LOCATION_TITLE: state.alert_source_location_title,
                ATTR_ALERT_SOURCE_LOCATION_TYPE: state.alert_source_location_type,
                ATTR_ACTIVE_ALERT_LOCATION_UIDS: list(state.active_alert_location_uids),
            }
        if self.entity_description.key == "alert_coverage":
            return {
                ATTR_COVERAGE_CODE: state.coverage_code,
                ATTR_POSSIBLE_COVERAGE_CODES: list(ALERT_COVERAGE_OPTIONS),
                ATTR_FULL_LEVEL_CODE: state.full_level_code,
                ATTR_PARTIAL_LEVEL_CODE: state.partial_level_code,
                ATTR_POSSIBLE_LEVEL_CODES: [
                    ALERT_LEVEL_CLEAR,
                    ALERT_LEVEL_YELLOW,
                    ALERT_LEVEL_RED,
                ],
                ATTR_ACTIVE_FULL_ALERT_LOCATION_UIDS: list(
                    state.active_full_alert_location_uids
                ),
                ATTR_ACTIVE_PARTIAL_ALERT_LOCATION_UIDS: list(
                    state.active_partial_alert_location_uids
                ),
            }
        if self.entity_description.key == "threat_codes":
            return {
                ATTR_THREAT_CODES: list(state.threat_codes),
                ATTR_THREAT_CODES_CSV: state.threat_codes_state,
                ATTR_POSSIBLE_THREAT_CODES: list(THREAT_CODE_ORDER),
                ATTR_THREATS: [threat.as_attribute_dict() for threat in state.threats],
            }
        if self.entity_description.key == "alert_latency":
            return {
                ATTR_ALERT_STARTED_AT: (
                    state.latency_alert_started_at.isoformat()
                    if state.latency_alert_started_at
                    else None
                ),
                ATTR_ALERT_DETECTED_AT: (
                    state.alert_detected_at.isoformat() if state.alert_detected_at else None
                ),
                ATTR_LEVEL_CODE: state.alert_latency_level,
            }
        if self.entity_description.key == "threat_latency":
            return {
                ATTR_THREAT_CODE: state.threat_latency_code,
                ATTR_THREAT_LEVEL_CODE: state.threat_latency_level,
                ATTR_THREAT_STARTED_AT: (
                    state.threat_latency_started_at.isoformat()
                    if state.threat_latency_started_at
                    else None
                ),
                ATTR_THREAT_DETECTED_AT: (
                    state.threat_detected_at.isoformat()
                    if state.threat_detected_at
                    else None
                ),
                ATTR_THREAT_SOURCE_MESSAGE: state.threat_latency_source_message,
            }
        if self.entity_description.key == "data_health":
            return {
                ATTR_ALERT_LATENCY: state.alert_latency,
                ATTR_THREAT_LATENCY: state.threat_latency,
                ATTR_SOURCE_RESPONSE_TIME: state.health_source_response_time,
                ATTR_CONSECUTIVE_ERRORS: state.health_consecutive_errors,
                ATTR_HTTP_STATUS: state.health_http_status,
                ATTR_LAST_ERROR: state.health_last_error,
                ATTR_HEALTH_DELAY_REASON: state.health_delay_reason,
            }
        return None
