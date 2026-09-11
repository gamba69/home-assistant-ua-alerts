from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from ._load_core import load

models = load("models")


def state(level: str, received_at: datetime, started_at: datetime | None = None):
    return models.LocationState(
        location_uid="31",
        location_title="м. Київ",
        location_type="city",
        source_available=True,
        data_valid=True,
        data_error=None,
        level=level,
        alert_started_at=started_at,
        received_at=received_at,
    )


def test_last_alert_uses_full_lifecycle_and_maximum_level():
    tracker = models.AlertHistoryTracker()
    t0 = datetime(2026, 9, 11, 10, 0, tzinfo=UTC)
    tracker.observe(state("clear", t0))
    tracker.observe(state("yellow", t0.replace(minute=1), t0.replace(minute=0, second=30)))
    tracker.observe(state("red", t0.replace(minute=2), t0.replace(minute=0, second=30)))
    tracker.observe(state("yellow", t0.replace(minute=3), t0.replace(minute=0, second=30)))
    result = tracker.observe(state("clear", t0.replace(minute=4)))
    assert result is not None
    assert result.max_level == "red"
    assert result.alert_started_at == t0.replace(second=30)
    assert result.ended_at == t0.replace(minute=4)
    assert result.seconds == 210.0


def test_invalid_snapshot_never_closes_active_alert():
    tracker = models.AlertHistoryTracker()
    t0 = datetime(2026, 9, 11, 10, 0, tzinfo=UTC)
    tracker.observe(state("clear", t0))
    tracker.observe(state("yellow", t0.replace(minute=1), t0.replace(second=30)))
    invalid = replace(
        state("clear", t0.replace(minute=2)),
        source_available=False,
        data_valid=False,
    )
    tracker.observe(invalid)
    assert tracker.active is not None
    assert tracker.measurement is None


def test_startup_during_existing_alert_does_not_fabricate_last_alert():
    tracker = models.AlertHistoryTracker()
    t0 = datetime(2026, 9, 11, 10, 0, tzinfo=UTC)
    tracker.observe(state("red", t0, t0.replace(hour=9)))
    tracker.observe(state("clear", t0.replace(minute=5)))
    assert tracker.measurement is None


def test_restored_active_alert_continues_across_restart():
    t0 = datetime(2026, 9, 11, 10, 0, tzinfo=UTC)
    tracker = models.AlertHistoryTracker(
        active=models.ActiveAlertLifecycle(
            alert_started_at=t0.replace(hour=9, minute=45),
            max_level="yellow",
        )
    )
    tracker.observe(state("red", t0, t0.replace(hour=9, minute=45)))
    result = tracker.observe(state("clear", t0.replace(minute=15)))
    assert result is not None
    assert result.max_level == "red"
    assert result.seconds == 1800.0
