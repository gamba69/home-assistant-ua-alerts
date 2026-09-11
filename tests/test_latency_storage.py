from __future__ import annotations

from datetime import UTC, datetime

from ._load_core import load

models = load("models")
storage = load("latency_storage")


def test_alert_latency_roundtrip():
    measurement = models.AlertLatencyMeasurement(
        alert_started_at=datetime(2026, 9, 10, 5, 59, 32, tzinfo=UTC),
        detected_at=datetime(2026, 9, 10, 6, 0, 0, tzinfo=UTC),
        seconds=28.0,
        level="yellow",
    )
    assert storage._decode_alert(storage._encode_alert(measurement)) == measurement


def test_threat_latency_roundtrip_preserves_attributes():
    measurement = models.ThreatLatencyMeasurement(
        threat_type="drones",
        threat_level="red",
        threat_started_at=datetime(2026, 9, 10, 6, 10, 1, tzinfo=UTC),
        detected_at=datetime(2026, 9, 10, 6, 10, 17, tzinfo=UTC),
        seconds=16.0,
        source_message="test source message",
    )
    assert storage._decode_threat(storage._encode_threat(measurement)) == measurement


def test_malformed_persisted_values_are_ignored():
    assert storage._decode_alert({"seconds": -1}) is None
    assert storage._decode_threat({"threat_type": "drones", "seconds": "bad"}) is None


def test_naive_persisted_timestamps_are_normalized_to_utc():
    decoded = storage._decode_alert(
        {
            "alert_started_at": "2026-09-10T05:59:32",
            "detected_at": "2026-09-10T06:00:00",
            "seconds": 28,
            "level": "yellow",
        }
    )
    assert decoded is not None
    assert decoded.alert_started_at.tzinfo is UTC
    assert decoded.detected_at.tzinfo is UTC


def test_alert_history_roundtrip():
    active = models.ActiveAlertLifecycle(
        alert_started_at=datetime(2026, 9, 10, 7, 0, tzinfo=UTC),
        max_level="red",
    )
    completed = models.LastAlertMeasurement(
        alert_started_at=datetime(2026, 9, 10, 5, 0, tzinfo=UTC),
        ended_at=datetime(2026, 9, 10, 5, 42, tzinfo=UTC),
        seconds=2520.0,
        max_level="red",
    )
    assert storage._decode_active_alert(storage._encode_active_alert(active)) == active
    assert storage._decode_last_alert(storage._encode_last_alert(completed)) == completed
