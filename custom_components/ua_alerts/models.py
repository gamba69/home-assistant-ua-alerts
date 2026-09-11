"""Pure data models and parsing for UA Alerts.

This module intentionally has no Home Assistant imports so the source-data model
can be tested independently from Home Assistant.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Iterable

from .const import (
    ALERT_COVERAGE_FULL,
    ALERT_COVERAGE_MIXED,
    ALERT_COVERAGE_NONE,
    ALERT_COVERAGE_PARTIAL,
    ALERT_LEVEL_CLEAR,
    ALERT_LEVEL_PRIORITY,
    ALERT_TYPE_AIR_RAID,
    THREAT_CODES_NONE,
    VALID_ALERT_LEVELS,
)


class SnapshotValidationError(ValueError):
    """Raised when the shared source snapshot has an invalid top-level shape."""


@dataclass(frozen=True, slots=True)
class Threat:
    """One threat attached to an active air-raid alert."""

    threat_type: str
    level: str | None
    started_at: datetime | None
    source_message: str | None

    @property
    def dedupe_key(self) -> tuple[str, str | None, datetime | None]:
        """Return the de-duplication key mandated by the specification."""
        return (self.threat_type, self.level, self.started_at)

    @property
    def instance_key(self) -> tuple[str, datetime | None]:
        """Return a stable threat-instance key for latency tracking.

        A threat level may change while the same threat instance remains active.
        Such a level-only update is not a new threat start and therefore must not
        create a new latency measurement.
        """
        return (self.threat_type, self.started_at)

    def as_attribute_dict(self) -> dict[str, Any]:
        """Return a Home Assistant attribute-safe representation."""
        return {
            "threat_type": self.threat_type,
            "level": self.level,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "source_message": self.source_message,
        }


@dataclass(frozen=True, slots=True)
class ParsedAlert:
    """Relevant source fields from one raw alert record."""

    location_uid: str | None
    location_title: str | None
    location_type: str | None
    alert_type: str | None
    alert_level: str | None
    started_at: datetime | None
    updated_at: datetime | None
    threats: tuple[Threat, ...]
    source_index: int


@dataclass(frozen=True, slots=True)
class ParsedSnapshot:
    """One globally parsed source snapshot."""

    received_at: datetime
    cachedat: Any
    alerts: tuple[ParsedAlert, ...]




@dataclass(frozen=True, slots=True)
class ActiveAlertLifecycle:
    """One fully observed alert currently in progress."""

    alert_started_at: datetime
    max_level: str


@dataclass(frozen=True, slots=True)
class LastAlertMeasurement:
    """One fully observed completed alert."""

    alert_started_at: datetime
    ended_at: datetime
    seconds: float
    max_level: str


@dataclass(slots=True)
class AlertHistoryTracker:
    """Track the latest fully observed alert lifecycle.

    A first snapshot that is already active only establishes a baseline. It
    cannot produce a trustworthy last-alert level because HA did not observe
    the beginning of that alert. A restored active lifecycle is different:
    its start and maximum level were already observed before the restart, so
    tracking continues normally.
    """

    has_valid_baseline: bool = False
    last_level: str | None = None
    active: ActiveAlertLifecycle | None = None
    measurement: LastAlertMeasurement | None = None

    def observe(self, state: "LocationState") -> LastAlertMeasurement | None:
        """Observe one valid snapshot and return the latest completed alert."""
        if (
            not state.data_valid
            or state.level is None
            or state.received_at is None
        ):
            return self.measurement

        if not self.has_valid_baseline:
            self.has_valid_baseline = True
            if self.active is not None:
                if state.level == ALERT_LEVEL_CLEAR:
                    self._finish(state.received_at)
                else:
                    self._update_max(state.level)
            self.last_level = state.level
            return self.measurement

        if self.active is not None:
            if state.level == ALERT_LEVEL_CLEAR:
                self._finish(state.received_at)
            else:
                self._update_max(state.level)
        elif (
            self.last_level == ALERT_LEVEL_CLEAR
            and state.level != ALERT_LEVEL_CLEAR
            and state.alert_started_at is not None
        ):
            self.active = ActiveAlertLifecycle(
                alert_started_at=state.alert_started_at,
                max_level=state.level,
            )

        self.last_level = state.level
        return self.measurement

    def _update_max(self, level: str) -> None:
        active = self.active
        if active is None:
            return
        if ALERT_LEVEL_PRIORITY.get(level, 0) <= ALERT_LEVEL_PRIORITY.get(
            active.max_level, 0
        ):
            return
        self.active = ActiveAlertLifecycle(
            alert_started_at=active.alert_started_at,
            max_level=level,
        )

    def _finish(self, ended_at: datetime) -> None:
        active = self.active
        self.active = None
        if active is None:
            return
        seconds = (ended_at - active.alert_started_at).total_seconds()
        if seconds < 0:
            return
        self.measurement = LastAlertMeasurement(
            alert_started_at=active.alert_started_at,
            ended_at=ended_at,
            seconds=seconds,
            max_level=active.max_level,
        )


@dataclass(frozen=True, slots=True)
class AlertLatencyMeasurement:
    """One frozen end-to-end alert latency measurement."""

    alert_started_at: datetime
    detected_at: datetime
    seconds: float
    level: str


@dataclass(slots=True)
class AlertLatencyTracker:
    """Track clear -> active transitions and freeze their end-to-end latency."""

    has_valid_baseline: bool = False
    last_level: str | None = None
    measurement: AlertLatencyMeasurement | None = None

    def observe(self, state: "LocationState") -> AlertLatencyMeasurement | None:
        """Observe one new valid snapshot state and return the last measurement.

        An integration startup while an alert is already active is deliberately not
        measured: without a prior clear state HA cannot know when it actually first
        observed that alert.
        """
        if not state.data_valid or state.level is None:
            return self.measurement

        if (
            self.has_valid_baseline
            and self.last_level == ALERT_LEVEL_CLEAR
            and state.level != ALERT_LEVEL_CLEAR
            and state.alert_started_at is not None
            and state.received_at is not None
        ):
            seconds = (state.received_at - state.alert_started_at).total_seconds()
            if seconds >= 0:
                self.measurement = AlertLatencyMeasurement(
                    alert_started_at=state.alert_started_at,
                    detected_at=state.received_at,
                    seconds=seconds,
                    level=state.level,
                )

        self.has_valid_baseline = True
        self.last_level = state.level
        return self.measurement


@dataclass(frozen=True, slots=True)
class ThreatLatencyMeasurement:
    """One frozen end-to-end threat latency measurement."""

    threat_type: str
    threat_level: str | None
    threat_started_at: datetime
    detected_at: datetime
    seconds: float
    source_message: str | None


@dataclass(slots=True)
class ThreatLatencyTracker:
    """Track newly appearing threat instances and freeze the latest latency.

    Existing threats present on the first valid snapshot after integration startup
    establish a baseline and are not measured. After that, each threat instance is
    measured once when Home Assistant first observes it. If several new threats
    arrive in the same snapshot, the one with the latest source ``started_at`` is
    exposed as the latest measurement.
    """

    has_valid_baseline: bool = False
    last_level: str | None = None
    seen_instances: set[tuple[str, datetime | None]] = field(default_factory=set)
    measurement: ThreatLatencyMeasurement | None = None

    def observe(self, state: "LocationState") -> ThreatLatencyMeasurement | None:
        """Observe one valid location snapshot and return the last measurement."""
        if not state.data_valid or state.level is None or state.received_at is None:
            return self.measurement

        current_instances = {threat.instance_key for threat in state.threats}

        # First valid state only establishes what HA already sees. This prevents
        # startup in the middle of an existing alert from producing a huge fake
        # threat latency. New threats appearing after startup are still measured.
        if not self.has_valid_baseline:
            self.has_valid_baseline = True
            self.last_level = state.level
            if state.level != ALERT_LEVEL_CLEAR:
                self.seen_instances.update(current_instances)
            return self.measurement

        if state.level == ALERT_LEVEL_CLEAR:
            # End of alert lifecycle. Keep the last measurement for diagnostics but
            # reset seen instances so threats in the next alert can be measured.
            self.seen_instances.clear()
            self.last_level = state.level
            return self.measurement

        candidates: list[tuple[datetime, Threat, float]] = []
        for threat in state.threats:
            if threat.instance_key in self.seen_instances:
                continue
            if threat.started_at is None:
                continue
            seconds = (state.received_at - threat.started_at).total_seconds()
            if seconds < 0:
                continue
            candidates.append((threat.started_at, threat, seconds))

        # Mark every currently visible threat instance as seen, including entries
        # without a valid timestamp. If a later snapshot supplies a timestamp, its
        # instance key changes from (type, None) to (type, timestamp) and it can then
        # be measured correctly.
        self.seen_instances.update(current_instances)

        if candidates:
            _, threat, seconds = max(
                candidates, key=lambda item: (item[0], item[1].threat_type)
            )
            self.measurement = ThreatLatencyMeasurement(
                threat_type=threat.threat_type,
                threat_level=threat.level,
                threat_started_at=threat.started_at,
                detected_at=state.received_at,
                seconds=seconds,
                source_message=threat.source_message,
            )

        self.last_level = state.level
        return self.measurement


@dataclass(frozen=True, slots=True)
class LocationState:
    """Computed state for one configured territory."""

    location_uid: str
    location_title: str
    location_type: str
    source_available: bool
    data_valid: bool
    data_error: str | None
    level: str | None
    threats: tuple[Threat, ...] = field(default_factory=tuple)
    threat_codes: tuple[str, ...] = field(default_factory=tuple)
    alert_started_at: datetime | None = None
    alert_scope: str | None = None
    alert_source_location_uid: str | None = None
    alert_source_location_title: str | None = None
    alert_source_location_type: str | None = None
    active_alert_location_uids: tuple[str, ...] = field(default_factory=tuple)
    coverage_code: str | None = None
    full_level_code: str | None = None
    partial_level_code: str | None = None
    active_full_alert_location_uids: tuple[str, ...] = field(default_factory=tuple)
    active_partial_alert_location_uids: tuple[str, ...] = field(default_factory=tuple)
    last_alert_started_at: datetime | None = None
    last_alert_ended_at: datetime | None = None
    last_alert_duration: float | None = None
    last_alert_level: str | None = None
    latency_alert_started_at: datetime | None = None
    alert_detected_at: datetime | None = None
    alert_latency: float | None = None
    alert_latency_level: str | None = None
    threat_latency_started_at: datetime | None = None
    threat_detected_at: datetime | None = None
    threat_latency: float | None = None
    threat_latency_code: str | None = None
    threat_latency_level: str | None = None
    threat_latency_source_message: str | None = None
    source_updated_at: datetime | None = None
    received_at: datetime | None = None
    health_code: str | None = None
    health_delay_reason: str | None = None
    health_source_response_time: float | None = None
    health_consecutive_errors: int = 0
    health_http_status: int | None = None
    health_last_error: str | None = None

    @property
    def threat_codes_state(self) -> str:
        """Return the user-facing string state for threat codes."""
        return ",".join(self.threat_codes) if self.threat_codes else THREAT_CODES_NONE

    @property
    def operational_available(self) -> bool:
        """Return availability for alert-level, air-alert and threat-code entities."""
        return self.source_available and self.data_valid and self.level is not None


@dataclass(frozen=True, slots=True)
class LocationDefinition:
    """One selectable location from the bundled/cached location catalog."""

    location_uid: str
    location_title: str
    location_type: str
    oblast_uid: str | None = None
    oblast_title: str | None = None
    raion_uid: str | None = None
    raion_title: str | None = None


def utcnow() -> datetime:
    """Return an aware UTC timestamp."""
    return datetime.now(UTC)


def parse_datetime(value: Any) -> datetime | None:
    """Parse a source datetime only when it is trustworthy and timezone-aware."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def validate_payload(payload: Any) -> tuple[list[dict[str, Any]], Any]:
    """Validate the global snapshot shape and return raw records plus cachedat."""
    if not isinstance(payload, dict):
        raise SnapshotValidationError("response is not a JSON object")
    raw = payload.get("raw")
    if not isinstance(raw, list):
        raise SnapshotValidationError("response.raw is not a list")
    for index, item in enumerate(raw):
        if not isinstance(item, dict):
            raise SnapshotValidationError(f"response.raw[{index}] is not an object")
    return raw, payload.get("cachedat")


def _parse_threat(item: Any) -> Threat | None:
    """Parse one threat record, skipping structurally unusable entries."""
    if not isinstance(item, dict):
        return None
    threat_type = item.get("threat_type")
    if not isinstance(threat_type, str) or not threat_type.strip():
        return None
    level = item.get("level")
    if not isinstance(level, str):
        level = None
    source_message = item.get("source_message")
    if not isinstance(source_message, str):
        source_message = None
    return Threat(
        threat_type=threat_type.strip(),
        level=level,
        started_at=parse_datetime(item.get("started_at")),
        source_message=source_message,
    )


def parse_snapshot(
    raw: list[dict[str, Any]],
    *,
    received_at: datetime,
    cachedat: Any = None,
) -> ParsedSnapshot:
    """Parse the raw list exactly once for all config entries."""
    alerts: list[ParsedAlert] = []
    for index, item in enumerate(raw):
        uid = item.get("location_uid")
        if uid is not None:
            uid = str(uid)

        threats_raw = item.get("threats", [])
        threats: list[Threat] = []
        if isinstance(threats_raw, list):
            for threat_raw in threats_raw:
                parsed_threat = _parse_threat(threat_raw)
                if parsed_threat is not None:
                    threats.append(parsed_threat)

        alerts.append(
            ParsedAlert(
                location_uid=uid,
                location_title=item.get("location_title")
                if isinstance(item.get("location_title"), str)
                else None,
                location_type=item.get("location_type")
                if isinstance(item.get("location_type"), str)
                else None,
                alert_type=item.get("alert_type")
                if isinstance(item.get("alert_type"), str)
                else None,
                alert_level=item.get("alert_level")
                if isinstance(item.get("alert_level"), str)
                else None,
                started_at=parse_datetime(item.get("started_at")),
                updated_at=parse_datetime(item.get("updated_at")),
                threats=tuple(threats),
                source_index=index,
            )
        )

    return ParsedSnapshot(
        received_at=received_at,
        cachedat=cachedat,
        alerts=tuple(alerts),
    )


def _dedupe_and_sort_threats(alerts: Iterable[ParsedAlert]) -> tuple[Threat, ...]:
    """Merge threats, de-duplicate and keep deterministic stable ordering."""
    deduped: dict[tuple[str, str | None, datetime | None], Threat] = {}
    for alert in alerts:
        for threat in alert.threats:
            deduped.setdefault(threat.dedupe_key, threat)

    def sort_key(threat: Threat) -> tuple[str, str, str]:
        return (
            threat.started_at.isoformat() if threat.started_at else "",
            threat.threat_type,
            threat.level or "",
        )

    return tuple(sorted(deduped.values(), key=sort_key))


def _applicable_location_chain(
    *,
    location_uid: str,
    location_title: str,
    location_type: str,
    location_definition: LocationDefinition | None,
) -> tuple[tuple[str, str, str, int], ...]:
    """Return target + administrative ancestors, nearest first.

    Parent-scope alert rows apply to the whole selected territory. These rows are
    the configured territory itself plus any administrative ancestors whose alert
    scope contains it.
    """
    chain: list[tuple[str, str, str, int]] = [
        (location_uid, location_title, location_type, 0)
    ]
    definition = location_definition
    if definition is None or definition.location_uid != location_uid:
        return tuple(chain)

    if definition.location_type == "hromada" and definition.raion_uid:
        chain.append(
            (
                definition.raion_uid,
                definition.raion_title or definition.raion_uid,
                "raion",
                1,
            )
        )
    if definition.location_type in {"hromada", "raion"} and definition.oblast_uid:
        chain.append(
            (
                definition.oblast_uid,
                definition.oblast_title or definition.oblast_uid,
                "oblast",
                2 if definition.location_type == "hromada" else 1,
            )
        )
    return tuple(chain)


def descendant_locations_for(
    location_definition: LocationDefinition | None,
    catalog: Iterable[LocationDefinition],
) -> tuple[LocationDefinition, ...]:
    """Return catalog descendants used to aggregate partial alert coverage.

    A selected raion aggregates alerts from its hromadas. A selected oblast
    aggregates alerts from both its raions and hromadas. Hromadas and standalone
    special-status cities have no alert-coverage descendants.
    """
    if location_definition is None:
        return ()

    location_uid = location_definition.location_uid
    if location_definition.location_type == "raion":
        result = [
            item
            for item in catalog
            if item.location_type == "hromada" and item.raion_uid == location_uid
        ]
    elif location_definition.location_type == "oblast":
        result = [
            item
            for item in catalog
            if item.location_uid != location_uid
            and item.location_type in {"raion", "hromada"}
            and item.oblast_uid == location_uid
        ]
    else:
        return ()

    return tuple(
        sorted(
            result,
            key=lambda item: (
                0 if item.location_type == "raion" else 1,
                item.location_title.casefold(),
                item.location_uid,
            ),
        )
    )


def _descendant_location_scope(
    descendants: Iterable[LocationDefinition],
) -> tuple[tuple[str, str, str, int], ...]:
    """Return partial-coverage descendants with deterministic depth/order."""
    scope: list[tuple[str, str, str, int]] = []
    for item in descendants:
        depth = 1 if item.location_type == "raion" else 2
        scope.append(
            (item.location_uid, item.location_title, item.location_type, depth)
        )
    return tuple(scope)


def _max_level(alerts: Iterable[ParsedAlert]) -> str:
    """Return the highest valid active level, or clear if no rows are active."""
    levels = [
        alert.alert_level
        for alert in alerts
        if alert.alert_level in VALID_ALERT_LEVELS
    ]
    if not levels:
        return ALERT_LEVEL_CLEAR
    return max(levels, key=lambda value: ALERT_LEVEL_PRIORITY[value])


def evaluate_location(
    snapshot: ParsedSnapshot | None,
    *,
    location_uid: str,
    location_title: str,
    location_type: str,
    source_available: bool,
    now: datetime,
    location_definition: LocationDefinition | None = None,
    descendant_definitions: Iterable[LocationDefinition] = (),
) -> LocationState:
    """Compute one territory from the shared parsed snapshot.

    Parent alerts propagate downward as full coverage. For selected raions and
    oblasts, child alert rows are also aggregated upward as *partial* coverage.
    A child alert therefore affects the selected area's maximum alert level but
    never masquerades as a full-territory alert.
    """
    if snapshot is None:
        return LocationState(
            location_uid=location_uid,
            location_title=location_title,
            location_type=location_type,
            source_available=False,
            data_valid=False,
            data_error="no successful snapshot yet",
            level=None,
        )

    full_chain = _applicable_location_chain(
        location_uid=location_uid,
        location_title=location_title,
        location_type=location_type,
        location_definition=location_definition,
    )
    partial_scope = _descendant_location_scope(descendant_definitions)

    full_scope_by_uid = {
        uid: (title, item_type, depth)
        for uid, title, item_type, depth in full_chain
    }
    partial_scope_by_uid = {
        uid: (title, item_type, depth)
        for uid, title, item_type, depth in partial_scope
        if uid not in full_scope_by_uid
    }
    full_uids = set(full_scope_by_uid)
    partial_uids = set(partial_scope_by_uid)
    all_uids = full_uids | partial_uids

    matching = tuple(
        alert
        for alert in snapshot.alerts
        if alert.location_uid in all_uids
        and alert.alert_type == ALERT_TYPE_AIR_RAID
    )
    full_matching = tuple(
        alert for alert in matching if alert.location_uid in full_uids
    )
    partial_matching = tuple(
        alert for alert in matching if alert.location_uid in partial_uids
    )

    if not matching:
        return LocationState(
            location_uid=location_uid,
            location_title=location_title,
            location_type=location_type,
            source_available=source_available,
            data_valid=True,
            data_error=None,
            level=ALERT_LEVEL_CLEAR,
            coverage_code=ALERT_COVERAGE_NONE,
            full_level_code=ALERT_LEVEL_CLEAR,
            partial_level_code=ALERT_LEVEL_CLEAR,
            received_at=snapshot.received_at,
        )

    invalid_levels = sorted(
        {
            str(alert.alert_level)
            for alert in matching
            if alert.alert_level not in VALID_ALERT_LEVELS
        }
    )

    threats = _dedupe_and_sort_threats(matching)
    threat_codes = tuple(sorted({threat.threat_type for threat in threats}))
    updated_times = [
        alert.updated_at for alert in matching if alert.updated_at is not None
    ]
    source_updated_at = max(updated_times) if updated_times else None

    alert_started_times = [
        alert.started_at for alert in matching if alert.started_at is not None
    ]
    alert_started_at = min(alert_started_times) if alert_started_times else None

    active_full_alert_location_uids = tuple(
        uid
        for uid, _title, _item_type, _depth in full_chain
        if any(alert.location_uid == uid for alert in full_matching)
    )
    active_partial_alert_location_uids = tuple(
        uid
        for uid, _title, _item_type, _depth in partial_scope
        if any(alert.location_uid == uid for alert in partial_matching)
    )
    active_alert_location_uids = (
        active_full_alert_location_uids + active_partial_alert_location_uids
    )

    if invalid_levels:
        return LocationState(
            location_uid=location_uid,
            location_title=location_title,
            location_type=location_type,
            source_available=source_available,
            data_valid=False,
            data_error=f"unknown alert_level: {', '.join(invalid_levels)}",
            level=None,
            threats=threats,
            threat_codes=threat_codes,
            alert_started_at=alert_started_at,
            active_alert_location_uids=active_alert_location_uids,
            active_full_alert_location_uids=active_full_alert_location_uids,
            active_partial_alert_location_uids=active_partial_alert_location_uids,
            source_updated_at=source_updated_at,
            received_at=snapshot.received_at,
        )

    full_level = _max_level(full_matching)
    partial_level = _max_level(partial_matching)
    level = max(
        (full_level, partial_level),
        key=lambda value: 0
        if value == ALERT_LEVEL_CLEAR
        else ALERT_LEVEL_PRIORITY[value],
    )

    if level == ALERT_LEVEL_CLEAR:
        coverage_code = ALERT_COVERAGE_NONE
    elif full_level == ALERT_LEVEL_CLEAR:
        coverage_code = ALERT_COVERAGE_PARTIAL
    elif (
        partial_level != ALERT_LEVEL_CLEAR
        and ALERT_LEVEL_PRIORITY[partial_level] > ALERT_LEVEL_PRIORITY[full_level]
    ):
        coverage_code = ALERT_COVERAGE_MIXED
    else:
        coverage_code = ALERT_COVERAGE_FULL

    # Attribute the effective level to the most representative row carrying the
    # winning level. Full-territory rows win ties over child/partial rows; among
    # equal scopes, the closest administrative row wins.
    def decisive_key(alert: ParsedAlert) -> tuple[int, int, int]:
        uid = alert.location_uid or ""
        if uid in full_scope_by_uid:
            return (0, full_scope_by_uid[uid][2], alert.source_index)
        return (1, partial_scope_by_uid.get(uid, ("", "", 999))[2], alert.source_index)

    decisive = min(
        (alert for alert in matching if alert.alert_level == level),
        key=decisive_key,
    )
    decisive_uid = decisive.location_uid or ""
    if decisive_uid in full_scope_by_uid:
        decisive_title, decisive_type, decisive_depth = full_scope_by_uid[decisive_uid]
        alert_scope = "direct" if decisive_depth == 0 else "inherited"
    else:
        decisive_title, decisive_type, _decisive_depth = partial_scope_by_uid.get(
            decisive_uid,
            (decisive.location_title or "", decisive.location_type or "unknown", 999),
        )
        alert_scope = "partial"

    return LocationState(
        location_uid=location_uid,
        location_title=location_title,
        location_type=location_type,
        source_available=source_available,
        data_valid=True,
        data_error=None,
        level=level,
        threats=threats,
        threat_codes=threat_codes,
        alert_started_at=alert_started_at,
        alert_scope=alert_scope,
        alert_source_location_uid=decisive.location_uid,
        alert_source_location_title=decisive_title,
        alert_source_location_type=decisive_type,
        active_alert_location_uids=active_alert_location_uids,
        coverage_code=coverage_code,
        full_level_code=full_level,
        partial_level_code=partial_level,
        active_full_alert_location_uids=active_full_alert_location_uids,
        active_partial_alert_location_uids=active_partial_alert_location_uids,
        source_updated_at=source_updated_at,
        received_at=snapshot.received_at,
    )
