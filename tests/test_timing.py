from __future__ import annotations

import pytest

from ._load_core import load

timing = load("timing")


def test_default_timing_is_3_and_15_seconds():
    settings = timing.UAAlertsSettings()
    assert settings.poll_interval == 3
    assert settings.stale_after == 15


def test_timing_accepts_valid_global_values():
    settings = timing.validate_settings(5, 20)
    assert settings.poll_interval == 5
    assert settings.stale_after == 20


@pytest.mark.parametrize(
    ("poll", "stale"),
    [
        (2, 15),
        (61, 122),
        (3, 5),
        (10, 19),
        ("bad", 15),
    ],
)
def test_timing_rejects_invalid_values(poll, stale):
    with pytest.raises(ValueError):
        timing.validate_settings(poll, stale)
