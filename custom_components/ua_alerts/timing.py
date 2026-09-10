"""Pure timing settings model and validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .const import (
    DEFAULT_POLL_INTERVAL_SECONDS,
    DEFAULT_STALE_AFTER_SECONDS,
    MAX_POLL_INTERVAL_SECONDS,
    MAX_STALE_AFTER_SECONDS,
    MIN_POLL_INTERVAL_SECONDS,
    MIN_STALE_AFTER_SECONDS,
    OPT_POLL_INTERVAL,
    OPT_STALE_AFTER,
)


@dataclass(frozen=True, slots=True)
class UAAlertsSettings:
    """Domain-wide timing settings."""

    poll_interval: float = DEFAULT_POLL_INTERVAL_SECONDS
    stale_after: float = DEFAULT_STALE_AFTER_SECONDS

    def as_options(self) -> dict[str, float]:
        return {
            OPT_POLL_INTERVAL: self.poll_interval,
            OPT_STALE_AFTER: self.stale_after,
        }


def validate_settings(poll_interval: Any, stale_after: Any) -> UAAlertsSettings:
    """Validate and normalize timing settings."""
    try:
        poll = float(poll_interval)
        stale = float(stale_after)
    except (TypeError, ValueError) as err:
        raise ValueError("timing values must be numeric") from err

    if not MIN_POLL_INTERVAL_SECONDS <= poll <= MAX_POLL_INTERVAL_SECONDS:
        raise ValueError(
            f"poll interval must be between {MIN_POLL_INTERVAL_SECONDS:g} and "
            f"{MAX_POLL_INTERVAL_SECONDS:g} seconds"
        )
    if not MIN_STALE_AFTER_SECONDS <= stale <= MAX_STALE_AFTER_SECONDS:
        raise ValueError(
            f"stale timeout must be between {MIN_STALE_AFTER_SECONDS:g} and "
            f"{MAX_STALE_AFTER_SECONDS:g} seconds"
        )
    if stale < poll * 2:
        raise ValueError("stale timeout must be at least twice the poll interval")
    return UAAlertsSettings(poll_interval=poll, stale_after=stale)
