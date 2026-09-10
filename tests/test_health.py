from __future__ import annotations

from ._load_core import load

health = load("health")


def evaluate(**overrides):
    values = dict(
        source_available=True,
        data_valid=True,
        consecutive_errors=0,
        http_response_time=0.2,
    )
    values.update(overrides)
    return health.evaluate_data_health(**values)


def test_normal_health():
    result = evaluate()
    assert result.code == "normal"
    assert result.delay_reason is None


def test_source_error_has_highest_priority():
    assert evaluate(source_available=False, data_valid=False).code == "source_error"
    assert evaluate(consecutive_errors=1).code == "source_error"


def test_data_error_when_transport_is_healthy():
    assert evaluate(data_valid=False).code == "data_error"


def test_slow_source_response_is_delayed():
    result = evaluate(http_response_time=1.5)
    assert result.code == "delayed"
    assert result.delay_reason == "source_response"


def test_event_latency_is_not_a_health_input():
    """A 28 s alert/threat latency is a measurement, not a failure verdict."""
    params = health.evaluate_data_health.__annotations__
    assert "alert_latency" not in params
    assert "threat_latency" not in params
