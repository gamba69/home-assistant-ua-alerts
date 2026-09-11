"""Per-location coordinator subscribed to the shared UA Alerts runtime."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from datetime import datetime
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
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
    ATTR_FULL_LEVEL_CODE,
    ATTR_LAST_ALERT_DELAY,
    ATTR_LAST_ALERT_DURATION,
    ATTR_LAST_ALERT_ENDED_AT,
    ATTR_LAST_ALERT_LEVEL,
    ATTR_LAST_ALERT_STARTED_AT,
    ATTR_LAST_THREAT_DELAY,
    ATTR_PARTIAL_LEVEL_CODE,
    ATTR_LOCATION_UID,
    ATTR_NEW_LEVEL,
    ATTR_OLD_LEVEL,
    ATTR_RECEIVED_AT,
    ATTR_SOURCE_UPDATED_AT,
    ATTR_THREAT_CODE,
    ATTR_THREAT_CODES,
    ATTR_THREAT_DETECTED_AT,
    ATTR_THREAT_LATENCY,
    ATTR_THREAT_LEVEL_CODE,
    ATTR_THREAT_SOURCE_MESSAGE,
    ATTR_THREAT_STARTED_AT,
    CONF_LOCATION_TITLE,
    CONF_LOCATION_TYPE,
    CONF_LOCATION_UID,
    DOMAIN,
    EVENT_ALERT_LEVEL_CHANGED,
    EVENT_ALERT_THREATS_CHANGED,
    EVENT_SOURCE_AVAILABILITY_CHANGED,
    HEALTH_DETAILS_REFRESH_SECONDS,
)
from .health import evaluate_data_health
from .latency_storage import LatencyStorage, RestoredLatencyMeasurements
from .models import (
    AlertHistoryTracker,
    AlertLatencyTracker,
    LocationDefinition,
    LocationState,
    ThreatLatencyTracker,
    evaluate_location,
)
from .runtime import UAAlertsRuntime

_LOGGER = logging.getLogger(__name__)

@dataclass(frozen=True, slots=True)
class _HealthDetails:
    """Low-churn snapshot exposed as attributes of the aggregate health entity."""

    code: str
    delay_reason: str | None
    source_response_time: float | None
    consecutive_errors: int
    http_status: int | None
    last_error: str | None
    alert_latency: float | None
    threat_latency: float | None
    sampled_at: datetime


class UAAlertsCoordinator(DataUpdateCoordinator[LocationState]):
    """Compute one territory from the shared runtime snapshot."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        runtime: UAAlertsRuntime,
        *,
        location_definition: LocationDefinition | None,
        descendant_definitions: tuple[LocationDefinition, ...],
        latency_storage: LatencyStorage,
        restored_latencies: RestoredLatencyMeasurements,
    ) -> None:
        self.entry = entry
        self.runtime = runtime
        self.location_uid = str(entry.data[CONF_LOCATION_UID])
        self.location_title = str(entry.data[CONF_LOCATION_TITLE])
        self.location_type = str(entry.data[CONF_LOCATION_TYPE])
        self.location_definition = location_definition
        self.descendant_definitions = descendant_definitions

        initial = evaluate_location(
            None,
            location_uid=self.location_uid,
            location_title=self.location_title,
            location_type=self.location_type,
            source_available=False,
            now=runtime.now(),
            location_definition=self.location_definition,
            descendant_definitions=self.descendant_definitions,
        )
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{self.location_uid}",
            config_entry=entry,
            update_interval=None,
        )
        self.data = initial

        self._started = False
        self._has_valid_baseline = False
        self._last_valid_level: str | None = None
        self._last_valid_threat_signature: tuple[tuple[str, str | None, datetime | None], ...] = ()
        self._last_processed_received_at: datetime | None = None
        self._last_source_available = initial.source_available
        self._availability_initialized = False

        # End-to-end alert latency is measured only on a clear -> active transition
        # and then frozen. Startup in the middle of an already-active alert is not
        # misreported as source/network latency.
        self._history_tracker = AlertHistoryTracker(
            active=restored_latencies.active_alert,
            measurement=restored_latencies.last_alert,
        )
        self._latency_tracker = AlertLatencyTracker(
            measurement=restored_latencies.alert
        )
        self._threat_latency_tracker = ThreatLatencyTracker(
            measurement=restored_latencies.threat
        )
        self._latency_storage = latency_storage
        self._latency_save_dirty = False
        self._latency_save_task: asyncio.Task[None] | None = None
        self._health_details: _HealthDetails | None = None

    async def async_register_runtime(self) -> None:
        """Register this entry with the shared runtime."""
        if self._started:
            return
        self._started = True
        await self.runtime.async_register(self.entry.entry_id, self._handle_runtime_update)

    async def async_wait_initial_cycle(self) -> None:
        """Wait for the first shared polling attempt and publish current state."""
        await self.runtime.async_wait_first_cycle()
        self._handle_runtime_update()

    async def async_start(self) -> None:
        """Register and wait for initial data; useful outside domain-managed setup."""
        await self.async_register_runtime()
        await self.async_wait_initial_cycle()

    async def async_shutdown(self) -> bool:
        """Unregister this coordinator and flush pending latency storage."""
        if not self._started:
            return False
        self._started = False
        is_last = await self.runtime.async_unregister(self.entry.entry_id)
        if self._latency_save_task is not None:
            await self._latency_save_task
        return is_last

    def _handle_runtime_update(self) -> None:
        state = evaluate_location(
            self.runtime.parsed_snapshot,
            location_uid=self.location_uid,
            location_title=self.location_title,
            location_type=self.location_type,
            source_available=self.runtime.source_available,
            now=self.runtime.now(),
            location_definition=self.location_definition,
            descendant_definitions=self.descendant_definitions,
        )
        state = self._process_snapshot_and_events(state)
        state = self._state_with_health(state)
        self.async_set_updated_data(state)

    def _state_with_last_latencies(self, state: LocationState) -> LocationState:
        """Attach the last completed alert and threat latency measurements."""
        history_measurement = self._history_tracker.measurement
        alert_measurement = self._latency_tracker.measurement
        threat_measurement = self._threat_latency_tracker.measurement
        updates: dict[str, Any] = {}
        if history_measurement is not None:
            updates.update(
                last_alert_started_at=history_measurement.alert_started_at,
                last_alert_ended_at=history_measurement.ended_at,
                last_alert_duration=history_measurement.seconds,
                last_alert_level=history_measurement.max_level,
            )
        if alert_measurement is not None:
            updates.update(
                latency_alert_started_at=alert_measurement.alert_started_at,
                alert_detected_at=alert_measurement.detected_at,
                alert_latency=alert_measurement.seconds,
                alert_latency_level=alert_measurement.level,
            )
        if threat_measurement is not None:
            updates.update(
                threat_latency_started_at=threat_measurement.threat_started_at,
                threat_detected_at=threat_measurement.detected_at,
                threat_latency=threat_measurement.seconds,
                threat_latency_code=threat_measurement.threat_type,
                threat_latency_level=threat_measurement.threat_level,
                threat_latency_source_message=threat_measurement.source_message,
            )
        return replace(state, **updates) if updates else state

    def _state_with_health(self, state: LocationState) -> LocationState:
        """Attach one useful aggregate health state without 3-second attribute churn."""
        now = self.runtime.now()
        evaluation = evaluate_data_health(
            source_available=state.source_available,
            data_valid=state.data_valid,
            consecutive_errors=self.runtime.consecutive_errors,
            http_response_time=self.runtime.http_response_time,
        )
        problem = state.data_error if not state.data_valid else self.runtime.last_error
        previous = self._health_details
        refresh_due = (
            previous is None
            or (now - previous.sampled_at).total_seconds() >= HEALTH_DETAILS_REFRESH_SECONDS
        )
        important_change = (
            previous is None
            or previous.code != evaluation.code
            or previous.delay_reason != evaluation.delay_reason
            or previous.last_error != problem
            or previous.alert_latency != state.alert_latency
            or previous.threat_latency != state.threat_latency
        )

        if refresh_due or important_change:
            self._health_details = _HealthDetails(
                code=evaluation.code,
                delay_reason=evaluation.delay_reason,
                source_response_time=(
                    round(self.runtime.http_response_time, 3)
                    if self.runtime.http_response_time is not None
                    else None
                ),
                consecutive_errors=self.runtime.consecutive_errors,
                http_status=self.runtime.http_status,
                last_error=problem,
                alert_latency=state.alert_latency,
                threat_latency=state.threat_latency,
                sampled_at=now,
            )

        details = self._health_details
        assert details is not None
        return replace(
            state,
            health_code=evaluation.code,
            health_delay_reason=evaluation.delay_reason,
            health_source_response_time=details.source_response_time,
            health_consecutive_errors=details.consecutive_errors,
            health_http_status=details.http_status,
            health_last_error=details.last_error,
        )

    def _process_snapshot_and_events(self, state: LocationState) -> LocationState:
        """Process one runtime update, measure latency, and emit transition events."""
        if self._availability_initialized and state.source_available != self._last_source_available:
            self._fire_event(
                EVENT_SOURCE_AVAILABILITY_CHANGED,
                old_level=self._last_valid_level,
                new_level=self._last_valid_level,
                state=self._state_with_last_latencies(state),
            )
        self._last_source_available = state.source_available
        self._availability_initialized = True

        is_new_snapshot = (
            state.received_at is not None
            and state.received_at != self._last_processed_received_at
        )
        if not is_new_snapshot:
            return self._state_with_last_latencies(state)
        self._last_processed_received_at = state.received_at

        if not state.data_valid or state.level is None:
            return self._state_with_last_latencies(state)

        previous_active_alert = self._history_tracker.active
        previous_history_measurement = self._history_tracker.measurement
        previous_alert_measurement = self._latency_tracker.measurement
        previous_threat_measurement = self._threat_latency_tracker.measurement
        self._history_tracker.observe(state)
        self._latency_tracker.observe(state)
        self._threat_latency_tracker.observe(state)
        if (
            self._history_tracker.active != previous_active_alert
            or self._history_tracker.measurement != previous_history_measurement
            or self._latency_tracker.measurement != previous_alert_measurement
            or self._threat_latency_tracker.measurement != previous_threat_measurement
        ):
            self._schedule_latency_save()
        state = self._state_with_last_latencies(state)

        threat_signature = tuple(threat.dedupe_key for threat in state.threats)
        if self._has_valid_baseline:
            if state.level != self._last_valid_level:
                self._fire_event(
                    EVENT_ALERT_LEVEL_CHANGED,
                    old_level=self._last_valid_level,
                    new_level=state.level,
                    state=state,
                )
            if threat_signature != self._last_valid_threat_signature:
                self._fire_event(
                    EVENT_ALERT_THREATS_CHANGED,
                    old_level=self._last_valid_level,
                    new_level=state.level,
                    state=state,
                )
        else:
            self._has_valid_baseline = True

        self._last_valid_level = state.level
        self._last_valid_threat_signature = threat_signature
        return state


    def _schedule_latency_save(self) -> None:
        """Coalesce rare measurement changes into serialized immediate writes."""
        self._latency_save_dirty = True
        if self._latency_save_task is not None and not self._latency_save_task.done():
            return
        self._latency_save_task = self.hass.async_create_background_task(
            self._async_save_latency_loop(),
            f"ua_alerts_save_latency_{self.location_uid}",
            eager_start=True,
        )

    async def _async_save_latency_loop(self) -> None:
        """Persist the newest measurement and repeat if it changes mid-write."""
        while self._latency_save_dirty:
            self._latency_save_dirty = False
            try:
                await self._latency_storage.async_save(
                    self._latency_tracker.measurement,
                    self._threat_latency_tracker.measurement,
                    active_alert=self._history_tracker.active,
                    last_alert=self._history_tracker.measurement,
                )
            except Exception:
                _LOGGER.exception(
                    "Could not save UA Alerts latency measurements for %s",
                    self.location_uid,
                )

    def _fire_event(
        self,
        event_type: str,
        *,
        old_level: str | None,
        new_level: str | None,
        state: LocationState,
    ) -> None:
        """Emit one integration event with stable technical values."""
        payload: dict[str, Any] = {
            ATTR_LOCATION_UID: self.location_uid,
            ATTR_OLD_LEVEL: old_level,
            ATTR_NEW_LEVEL: new_level,
            ATTR_THREAT_CODES: state.threat_codes_state,
            ATTR_ALERT_STARTED_AT: state.alert_started_at,
            ATTR_ALERT_DETECTED_AT: state.alert_detected_at,
            ATTR_ALERT_LATENCY: state.alert_latency,
            ATTR_ALERT_SCOPE: state.alert_scope,
            ATTR_ALERT_SOURCE_LOCATION_UID: state.alert_source_location_uid,
            ATTR_ALERT_SOURCE_LOCATION_TITLE: state.alert_source_location_title,
            ATTR_ALERT_SOURCE_LOCATION_TYPE: state.alert_source_location_type,
            ATTR_ACTIVE_ALERT_LOCATION_UIDS: list(state.active_alert_location_uids),
            ATTR_COVERAGE_CODE: state.coverage_code,
            ATTR_FULL_LEVEL_CODE: state.full_level_code,
            ATTR_PARTIAL_LEVEL_CODE: state.partial_level_code,
            ATTR_ACTIVE_FULL_ALERT_LOCATION_UIDS: list(
                state.active_full_alert_location_uids
            ),
            ATTR_ACTIVE_PARTIAL_ALERT_LOCATION_UIDS: list(
                state.active_partial_alert_location_uids
            ),
            ATTR_THREAT_CODE: state.threat_latency_code,
            ATTR_THREAT_LEVEL_CODE: state.threat_latency_level,
            ATTR_THREAT_STARTED_AT: state.threat_latency_started_at,
            ATTR_THREAT_DETECTED_AT: state.threat_detected_at,
            ATTR_THREAT_LATENCY: state.threat_latency,
            ATTR_THREAT_SOURCE_MESSAGE: state.threat_latency_source_message,
            ATTR_LAST_ALERT_STARTED_AT: state.last_alert_started_at,
            ATTR_LAST_ALERT_ENDED_AT: state.last_alert_ended_at,
            ATTR_LAST_ALERT_DURATION: state.last_alert_duration,
            ATTR_LAST_ALERT_LEVEL: state.last_alert_level,
            ATTR_LAST_ALERT_DELAY: state.alert_latency,
            ATTR_LAST_THREAT_DELAY: state.threat_latency,
            ATTR_SOURCE_UPDATED_AT: state.source_updated_at,
            ATTR_RECEIVED_AT: state.received_at,
        }
        self.hass.bus.async_fire(event_type, payload)
