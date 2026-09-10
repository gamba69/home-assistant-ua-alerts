"""Data-health evaluation for UA Alerts.

This module intentionally has no Home Assistant imports so the health semantics
can be unit-tested without a Home Assistant installation.
"""

from __future__ import annotations

from dataclasses import dataclass

from .const import (
    DATA_HEALTH_DATA_ERROR,
    DATA_HEALTH_DELAYED,
    DATA_HEALTH_NORMAL,
    DATA_HEALTH_SOURCE_ERROR,
    HEALTH_SLOW_RESPONSE_SECONDS,
)


@dataclass(frozen=True, slots=True)
class DataHealthEvaluation:
    """One aggregate health decision with a stable technical reason code."""

    code: str
    delay_reason: str | None = None


def evaluate_data_health(
    *,
    source_available: bool,
    data_valid: bool,
    consecutive_errors: int,
    http_response_time: float | None,
) -> DataHealthEvaluation:
    """Return the current aggregate data-health state.

    The dedicated alert/threat latency sensors are measurements, not health
    verdicts. Upstream publication delay is not distinguishable from normal
    source behavior, so those values deliberately do not affect health.
    """
    if consecutive_errors > 0:
        return DataHealthEvaluation(DATA_HEALTH_SOURCE_ERROR)
    if not source_available:
        return DataHealthEvaluation(DATA_HEALTH_SOURCE_ERROR)
    if not data_valid:
        return DataHealthEvaluation(DATA_HEALTH_DATA_ERROR)

    if (
        http_response_time is not None
        and http_response_time >= HEALTH_SLOW_RESPONSE_SECONDS
    ):
        return DataHealthEvaluation(DATA_HEALTH_DELAYED, "source_response")

    return DataHealthEvaluation(DATA_HEALTH_NORMAL)
