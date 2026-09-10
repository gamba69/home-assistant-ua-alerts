from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from ._load_core import load

models = load("models")


def dt(seconds: int = 0) -> datetime:
    return datetime(2026, 9, 9, 12, 0, tzinfo=UTC) + timedelta(seconds=seconds)


def snapshot(raw, received=20):
    return models.parse_snapshot(raw, received_at=dt(received), cachedat="cache")


def evaluate(
    raw,
    uid="31",
    received=20,
    now=20,
    available=True,
    *,
    title="м. Київ",
    typ="city",
    location_definition=None,
    descendant_definitions=(),
):
    return models.evaluate_location(
        snapshot(raw, received),
        location_uid=uid,
        location_title=title,
        location_type=typ,
        source_available=available,
        now=dt(now),
        location_definition=location_definition,
        descendant_definitions=descendant_definitions,
    )


def alert(
    level="yellow",
    *,
    uid="31",
    started=5,
    updated=10,
    threats=None,
    alert_type="air_raid",
):
    item = {
        "location_uid": uid,
        "location_title": "м. Київ",
        "location_type": "city",
        "alert_type": alert_type,
        "alert_level": level,
        "started_at": dt(started).isoformat(),
        "updated_at": dt(updated).isoformat(),
    }
    if threats is not None:
        item["threats"] = threats
    return item


def threat(kind="drones", *, level="yellow", started=5, message="msg"):
    return {
        "threat_type": kind,
        "level": level,
        "started_at": dt(started).isoformat(),
        "source_message": message,
    }


def test_validate_payload_requires_object_and_raw_list():
    for invalid in (None, [], "x", 1):
        with pytest.raises(models.SnapshotValidationError):
            models.validate_payload(invalid)
    with pytest.raises(models.SnapshotValidationError):
        models.validate_payload({})
    with pytest.raises(models.SnapshotValidationError):
        models.validate_payload({"raw": {}})
    with pytest.raises(models.SnapshotValidationError):
        models.validate_payload({"raw": ["not-object"]})


def test_valid_empty_raw_means_clear():
    state = evaluate([])
    assert state.level == "clear"
    assert state.threat_codes_state == "none"
    assert state.threats == ()
    assert state.alert_started_at is None
    assert state.source_updated_at is None
    assert state.received_at == dt(20)
    assert state.operational_available


@pytest.mark.parametrize("level", ["yellow", "red"])
def test_single_level(level):
    state = evaluate([alert(level)])
    assert state.level == level
    assert state.alert_started_at == dt(5)


def test_red_wins_over_yellow_across_matching_records():
    state = evaluate([
        alert("yellow", started=6, updated=8),
        alert("red", started=5, updated=10),
    ])
    assert state.level == "red"
    assert state.alert_started_at == dt(5)
    assert state.source_updated_at == dt(10)


def test_non_air_raid_records_do_not_affect_air_raid_level():
    state = evaluate([alert("red", alert_type="artillery_shelling")])
    assert state.level == "clear"


def test_other_uid_does_not_affect_location():
    state = evaluate([alert("red", uid="14")])
    assert state.level == "clear"


def test_unknown_alert_level_invalidates_only_evaluated_uid():
    snap = snapshot([alert("purple", uid="31"), alert("red", uid="14")])
    kyiv = models.evaluate_location(
        snap,
        location_uid="31",
        location_title="м. Київ",
        location_type="city",
        source_available=True,
        now=dt(20),
    )
    oblast = models.evaluate_location(
        snap,
        location_uid="14",
        location_title="Київська область",
        location_type="oblast",
        source_available=True,
        now=dt(20),
    )
    assert not kyiv.data_valid
    assert kyiv.level is None
    assert "purple" in kyiv.data_error
    assert oblast.data_valid
    assert oblast.level == "red"


def test_unknown_threat_type_is_preserved():
    state = evaluate([alert("yellow", threats=[threat("future_new_type")])])
    assert state.threat_codes == ("future_new_type",)
    assert state.threats[0].source_message == "msg"


def test_threat_dedupe_key_ignores_source_message():
    first = threat("drones", message="first")
    second = threat("drones", message="changed text")
    state = evaluate([alert("yellow", threats=[first]), alert("yellow", threats=[second])])
    assert len(state.threats) == 1
    assert state.threats[0].source_message == "first"


def test_threats_have_stable_sort_and_unique_codes():
    state = evaluate([
        alert(
            "red",
            threats=[
                threat("cruise_missiles", started=9),
                threat("drones", started=4),
                threat("drones", started=4),
            ],
        )
    ])
    assert [item.threat_type for item in state.threats] == ["drones", "cruise_missiles"]
    assert state.threat_codes == ("cruise_missiles", "drones")
    assert state.threat_codes_state == "cruise_missiles,drones"


def test_alert_started_at_comes_from_alert_not_threat():
    state = evaluate([
        alert("yellow", started=3, threats=[threat("drones", started=8)])
    ])
    assert state.alert_started_at == dt(3)
    assert state.threats[0].started_at == dt(8)


def test_naive_or_invalid_source_datetime_is_ignored():
    assert models.parse_datetime("2026-09-09T12:00:00") is None
    assert models.parse_datetime("not-a-date") is None
    assert models.parse_datetime(None) is None


def test_no_snapshot_is_unavailable_not_clear():
    state = models.evaluate_location(
        None,
        location_uid="31",
        location_title="м. Київ",
        location_type="city",
        source_available=False,
        now=dt(),
    )
    assert state.level is None
    assert not state.data_valid
    assert not state.operational_available


def test_stale_snapshot_retains_last_computed_level_but_operational_entities_unavailable():
    state = evaluate([alert("red")], available=False)
    assert state.level == "red"
    assert not state.source_available
    assert not state.operational_available


def test_missing_alert_level_is_location_data_error_not_clear():
    item = alert("yellow")
    item.pop("alert_level")
    state = evaluate([item])
    assert not state.data_valid
    assert state.level is None
    assert not state.operational_available


def test_threat_without_type_is_ignored_without_inventing_a_code():
    state = evaluate([
        alert("yellow", threats=[{"level": "red", "started_at": dt(5).isoformat()}])
    ])
    assert state.threats == ()
    assert state.threat_codes_state == "none"


def test_non_list_threat_container_does_not_break_other_fields():
    item = alert("yellow")
    item["threats"] = {"threat_type": "drones"}
    state = evaluate([item])
    assert state.data_valid
    assert state.level == "yellow"
    assert state.threats == ()


def test_mixed_valid_and_missing_alert_level_invalidates_uid():
    missing = alert("yellow")
    missing.pop("alert_level")
    state = evaluate([alert("red"), missing])
    assert state.level is None
    assert not state.data_valid


def test_latest_source_updated_time_is_used_across_records():
    state = evaluate([
        alert("yellow", updated=7),
        alert("yellow", updated=13),
    ], received=20)
    assert state.source_updated_at == dt(13)


def test_threat_attribute_serialization_is_json_safe():
    state = evaluate([alert("yellow", threats=[threat(started=5)])])
    attrs = state.threats[0].as_attribute_dict()
    assert attrs["started_at"] == dt(5).isoformat()
    assert isinstance(attrs["started_at"], str)


def test_latency_tracker_measures_clear_to_alert_once_and_freezes():
    tracker = models.AlertLatencyTracker()

    clear = evaluate([], received=10)
    assert tracker.observe(clear) is None

    first_active = evaluate([alert("yellow", started=11)], received=14)
    measurement = tracker.observe(first_active)
    assert measurement is not None
    assert measurement.alert_started_at == dt(11)
    assert measurement.detected_at == dt(14)
    assert measurement.seconds == 3
    assert measurement.level == "yellow"

    # The alert is still active in later polling cycles. The latency must not grow.
    later_active = evaluate([alert("yellow", started=11, updated=30)], received=40)
    assert tracker.observe(later_active) == measurement
    assert tracker.measurement.seconds == 3


def test_latency_tracker_does_not_call_startup_during_existing_alert_latency():
    tracker = models.AlertLatencyTracker()
    active_at_startup = evaluate([alert("yellow", started=0)], received=100)
    assert tracker.observe(active_at_startup) is None


def test_latency_tracker_measures_next_alert_after_startup_during_active_alert():
    tracker = models.AlertLatencyTracker()
    tracker.observe(evaluate([alert("yellow", started=0)], received=100))
    tracker.observe(evaluate([], received=110))
    measurement = tracker.observe(evaluate([alert("red", started=111)], received=114))
    assert measurement is not None
    assert measurement.seconds == 3
    assert measurement.level == "red"


def test_latency_tracker_rejects_negative_clock_anomaly():
    tracker = models.AlertLatencyTracker()
    tracker.observe(evaluate([], received=10))
    measurement = tracker.observe(evaluate([alert("yellow", started=20)], received=15))
    assert measurement is None


def test_threat_latency_tracker_measures_new_threat_and_freezes():
    tracker = models.ThreatLatencyTracker()

    # Clear establishes a valid baseline.
    assert tracker.observe(evaluate([], received=10)) is None

    first = evaluate(
        [alert("yellow", started=11, threats=[threat("drones", started=12)])],
        received=14,
    )
    measurement = tracker.observe(first)
    assert measurement is not None
    assert measurement.threat_type == "drones"
    assert measurement.threat_level == "yellow"
    assert measurement.threat_started_at == dt(12)
    assert measurement.detected_at == dt(14)
    assert measurement.seconds == 2
    assert measurement.source_message == "msg"

    # Polling the same still-active threat must never make the latency grow.
    later = evaluate(
        [alert("yellow", started=11, updated=40, threats=[threat("drones", started=12)])],
        received=50,
    )
    assert tracker.observe(later) == measurement
    assert tracker.measurement.seconds == 2


def test_threat_latency_tracker_startup_active_does_not_measure_existing_but_measures_new():
    tracker = models.ThreatLatencyTracker()

    startup = evaluate(
        [alert("yellow", started=0, threats=[threat("drones", started=2)])],
        received=100,
    )
    assert tracker.observe(startup) is None

    changed = evaluate(
        [
            alert(
                "yellow",
                started=0,
                threats=[
                    threat("drones", started=2),
                    threat("cruise_missiles", started=103),
                ],
            )
        ],
        received=105,
    )
    measurement = tracker.observe(changed)
    assert measurement is not None
    assert measurement.threat_type == "cruise_missiles"
    assert measurement.seconds == 2


def test_threat_latency_tracker_uses_latest_new_threat_when_snapshot_adds_multiple():
    tracker = models.ThreatLatencyTracker()
    tracker.observe(evaluate([], received=10))

    state = evaluate(
        [
            alert(
                "red",
                started=11,
                threats=[
                    threat("drones", started=12),
                    threat("ballistic_missiles", started=14),
                    threat("cruise_missiles", started=13),
                ],
            )
        ],
        received=16,
    )
    measurement = tracker.observe(state)
    assert measurement is not None
    assert measurement.threat_type == "ballistic_missiles"
    assert measurement.threat_started_at == dt(14)
    assert measurement.seconds == 2


def test_threat_latency_tracker_level_only_change_is_not_new_threat():
    tracker = models.ThreatLatencyTracker()
    tracker.observe(evaluate([], received=10))
    first = tracker.observe(
        evaluate(
            [alert("yellow", started=11, threats=[threat("drones", level="yellow", started=12)])],
            received=14,
        )
    )
    assert first is not None
    assert first.seconds == 2

    # Same threat_type + same started_at with a new level is one threat instance.
    changed_level = evaluate(
        [alert("red", started=11, threats=[threat("drones", level="red", started=12)])],
        received=40,
    )
    assert tracker.observe(changed_level) == first
    assert tracker.measurement.seconds == 2


def test_threat_latency_tracker_does_not_remeasure_same_instance_after_temporary_disappearance():
    tracker = models.ThreatLatencyTracker()
    tracker.observe(evaluate([], received=10))
    measured = tracker.observe(
        evaluate(
            [alert("yellow", started=11, threats=[threat("drones", started=12)])],
            received=14,
        )
    )
    assert measured is not None

    tracker.observe(evaluate([alert("yellow", started=11, threats=[])], received=20))
    reappeared = tracker.observe(
        evaluate(
            [alert("yellow", started=11, threats=[threat("drones", started=12)])],
            received=30,
        )
    )
    assert reappeared == measured
    assert reappeared.seconds == 2


def test_threat_latency_tracker_resets_instances_after_clear_for_next_alert():
    tracker = models.ThreatLatencyTracker()
    tracker.observe(evaluate([], received=10))
    first = tracker.observe(
        evaluate(
            [alert("yellow", started=11, threats=[threat("drones", started=12)])],
            received=14,
        )
    )
    assert first is not None and first.seconds == 2

    tracker.observe(evaluate([], received=20))
    second = tracker.observe(
        evaluate(
            [alert("yellow", started=21, threats=[threat("drones", started=22)])],
            received=25,
        )
    )
    assert second is not None
    assert second.threat_started_at == dt(22)
    assert second.detected_at == dt(25)
    assert second.seconds == 3


def test_threat_latency_tracker_requires_valid_nonfuture_started_at():
    tracker = models.ThreatLatencyTracker()
    tracker.observe(evaluate([], received=10))

    no_time = evaluate(
        [
            alert(
                "yellow",
                started=11,
                threats=[
                    {
                        "threat_type": "drones",
                        "level": "yellow",
                        "source_message": "no timestamp",
                    }
                ],
            )
        ],
        received=14,
    )
    assert tracker.observe(no_time) is None

    future = evaluate(
        [alert("yellow", started=11, threats=[threat("cruise_missiles", started=30)])],
        received=20,
    )
    assert tracker.observe(future) is None



def kaharlyk_definition():
    return models.LocationDefinition(
        "726",
        "Кагарлицька територіальна громада",
        "hromada",
        oblast_uid="14",
        oblast_title="Київська область",
        raion_uid="76",
        raion_title="Обухівський район",
    )


def obukhiv_definition():
    return models.LocationDefinition(
        "76",
        "Обухівський район",
        "raion",
        oblast_uid="14",
        oblast_title="Київська область",
    )


def test_hromada_inherits_raion_wide_alert():
    state = evaluate(
        [alert("yellow", uid="76", started=4)],
        uid="726",
        title="Кагарлицька територіальна громада",
        typ="hromada",
        location_definition=kaharlyk_definition(),
    )
    assert state.level == "yellow"
    assert state.alert_scope == "inherited"
    assert state.alert_source_location_uid == "76"
    assert state.alert_source_location_title == "Обухівський район"
    assert state.alert_source_location_type == "raion"
    assert state.active_alert_location_uids == ("76",)
    assert state.alert_started_at == dt(4)


def test_hromada_direct_red_overrides_inherited_yellow():
    state = evaluate(
        [
            alert("yellow", uid="76", started=3),
            alert("red", uid="726", started=8),
        ],
        uid="726",
        title="Кагарлицька територіальна громада",
        typ="hromada",
        location_definition=kaharlyk_definition(),
    )
    assert state.level == "red"
    assert state.alert_scope == "direct"
    assert state.alert_source_location_uid == "726"
    assert state.active_alert_location_uids == ("726", "76")
    # The effective alert lifecycle started when the inherited raion alert began.
    assert state.alert_started_at == dt(3)


def test_hromada_inherits_oblast_alert_and_merges_parent_threats():
    state = evaluate(
        [
            alert(
                "yellow",
                uid="14",
                started=2,
                threats=[threat("drones", started=5, message="oblast")],
            ),
            alert(
                "yellow",
                uid="76",
                started=4,
                threats=[threat("cruise_missiles", started=6, message="raion")],
            ),
            alert(
                "yellow",
                uid="726",
                started=7,
                threats=[threat("drones", started=5, message="duplicate")],
            ),
        ],
        uid="726",
        title="Кагарлицька територіальна громада",
        typ="hromada",
        location_definition=kaharlyk_definition(),
    )
    assert state.level == "yellow"
    # All levels tie, so the closest/direct source is used for attribution.
    assert state.alert_scope == "direct"
    assert state.alert_source_location_uid == "726"
    assert state.active_alert_location_uids == ("726", "76", "14")
    assert state.threat_codes == ("cruise_missiles", "drones")
    assert len(state.threats) == 2
    assert state.alert_started_at == dt(2)


def test_child_alert_aggregates_up_to_raion_as_partial_not_full():
    state = evaluate(
        [alert("red", uid="726", started=5)],
        uid="76",
        title="Обухівський район",
        typ="raion",
        location_definition=obukhiv_definition(),
        descendant_definitions=(kaharlyk_definition(),),
    )
    assert state.level == "red"
    assert state.alert_scope == "partial"
    assert state.alert_source_location_uid == "726"
    assert state.coverage_code == "partial"
    assert state.full_level_code == "clear"
    assert state.partial_level_code == "red"
    assert state.active_full_alert_location_uids == ()
    assert state.active_partial_alert_location_uids == ("726",)
    assert state.active_alert_location_uids == ("726",)


def test_raion_full_yellow_plus_child_red_is_mixed():
    state = evaluate(
        [
            alert("yellow", uid="76", started=3),
            alert("red", uid="726", started=8),
        ],
        uid="76",
        title="Обухівський район",
        typ="raion",
        location_definition=obukhiv_definition(),
        descendant_definitions=(kaharlyk_definition(),),
    )
    assert state.level == "red"
    assert state.coverage_code == "mixed"
    assert state.full_level_code == "yellow"
    assert state.partial_level_code == "red"
    assert state.alert_scope == "partial"
    assert state.alert_source_location_uid == "726"
    assert state.active_full_alert_location_uids == ("76",)
    assert state.active_partial_alert_location_uids == ("726",)


def test_raion_full_red_is_not_downgraded_by_child_yellow():
    state = evaluate(
        [
            alert("red", uid="76", started=3),
            alert("yellow", uid="726", started=8),
        ],
        uid="76",
        title="Обухівський район",
        typ="raion",
        location_definition=obukhiv_definition(),
        descendant_definitions=(kaharlyk_definition(),),
    )
    assert state.level == "red"
    assert state.coverage_code == "full"
    assert state.full_level_code == "red"
    assert state.partial_level_code == "yellow"
    assert state.alert_scope == "direct"
    assert state.alert_source_location_uid == "76"


def test_raion_inherited_oblast_yellow_plus_child_red_is_mixed():
    state = evaluate(
        [
            alert("yellow", uid="14", started=2),
            alert("red", uid="726", started=8),
        ],
        uid="76",
        title="Обухівський район",
        typ="raion",
        location_definition=obukhiv_definition(),
        descendant_definitions=(kaharlyk_definition(),),
    )
    assert state.level == "red"
    assert state.coverage_code == "mixed"
    assert state.full_level_code == "yellow"
    assert state.partial_level_code == "red"
    assert state.alert_scope == "partial"


def test_descendant_lookup_for_raion_and_oblast():
    kyiv = models.LocationDefinition("14", "Київська область", "oblast")
    other = models.LocationDefinition(
        "9999",
        "Інша громада",
        "hromada",
        oblast_uid="1",
        oblast_title="Інша область",
        raion_uid="999",
        raion_title="Інший район",
    )
    catalog = (kyiv, obukhiv_definition(), kaharlyk_definition(), other)

    assert models.descendant_locations_for(obukhiv_definition(), catalog) == (
        kaharlyk_definition(),
    )
    oblast_descendants = models.descendant_locations_for(kyiv, catalog)
    assert {item.location_uid for item in oblast_descendants} == {"76", "726"}


def test_oblast_child_raion_alert_is_partial():
    kyiv = models.LocationDefinition("14", "Київська область", "oblast")
    descendants = (obukhiv_definition(), kaharlyk_definition())
    state = evaluate(
        [alert("yellow", uid="76", started=5)],
        uid="14",
        title="Київська область",
        typ="oblast",
        location_definition=kyiv,
        descendant_definitions=descendants,
    )
    assert state.level == "yellow"
    assert state.coverage_code == "partial"
    assert state.full_level_code == "clear"
    assert state.partial_level_code == "yellow"
    assert state.alert_scope == "partial"
    assert state.alert_source_location_uid == "76"


def test_partial_child_threats_are_aggregated_for_raion():
    state = evaluate(
        [
            alert(
                "yellow",
                uid="726",
                started=5,
                threats=[threat("drones", started=6, message="child")],
            )
        ],
        uid="76",
        title="Обухівський район",
        typ="raion",
        location_definition=obukhiv_definition(),
        descendant_definitions=(kaharlyk_definition(),),
    )
    assert state.coverage_code == "partial"
    assert state.threat_codes == ("drones",)
    assert state.threats[0].source_message == "child"


def test_invalid_ancestor_level_invalidates_descendant():
    state = evaluate(
        [alert("purple", uid="76", started=5)],
        uid="726",
        title="Кагарлицька територіальна громада",
        typ="hromada",
        location_definition=kaharlyk_definition(),
    )
    assert state.level is None
    assert not state.data_valid
    assert state.active_alert_location_uids == ("76",)
    assert "purple" in state.data_error


def test_inherited_alert_uses_parent_started_at_for_alert_latency():
    tracker = models.AlertLatencyTracker()
    clear = evaluate(
        [],
        uid="726",
        received=10,
        title="Кагарлицька територіальна громада",
        typ="hromada",
        location_definition=kaharlyk_definition(),
    )
    assert tracker.observe(clear) is None
    inherited = evaluate(
        [alert("yellow", uid="76", started=11)],
        uid="726",
        received=14,
        title="Кагарлицька територіальна громада",
        typ="hromada",
        location_definition=kaharlyk_definition(),
    )
    measurement = tracker.observe(inherited)
    assert measurement is not None
    assert measurement.alert_started_at == dt(11)
    assert measurement.seconds == 3
