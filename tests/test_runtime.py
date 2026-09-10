from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from ._load_core import load

runtime_mod = load("runtime")


class MutableClock:
    def __init__(self):
        self.value = datetime(2026, 9, 9, 12, 0, tzinfo=UTC)
    def __call__(self):
        return self.value
    def advance(self, seconds):
        self.value += timedelta(seconds=seconds)


class FakeResponse:
    def __init__(self, payload, *, status=200, delay=0):
        self.payload = payload
        self.status = status
        self.delay = delay
    async def __aenter__(self):
        if self.delay:
            await asyncio.sleep(self.delay)
        return self
    async def __aexit__(self, *args):
        return False
    def raise_for_status(self):
        if self.status >= 400:
            import aiohttp
            raise aiohttp.ClientResponseError(None, (), status=self.status)
    async def json(self, content_type=None):
        return self.payload


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0
        self.active = 0
        self.max_active = 0
    def get(self, url):
        self.calls += 1
        response = self.responses.pop(0) if self.responses else FakeResponse({"raw": []})
        session = self
        class Context:
            async def __aenter__(self_inner):
                session.active += 1
                session.max_active = max(session.max_active, session.active)
                try:
                    return await response.__aenter__()
                except Exception:
                    session.active -= 1
                    raise
            async def __aexit__(self_inner, *args):
                try:
                    return await response.__aexit__(*args)
                finally:
                    session.active -= 1
        return Context()


def make_runtime(session, clock=None, **kwargs):
    return runtime_mod.UAAlertsRuntime(
        None, session=session, now_fn=clock or MutableClock(),
        poll_interval=kwargs.pop("poll_interval", 3600),
        request_timeout=kwargs.pop("request_timeout", 1),
        stale_after=kwargs.pop("stale_after", 15), **kwargs
    )


@pytest.mark.asyncio
async def test_successful_fetch_replaces_snapshot_and_resets_errors():
    clock = MutableClock()
    session = FakeSession([FakeResponse({"raw": [], "cachedat": 123})])
    runtime = make_runtime(session, clock)
    runtime.consecutive_errors = 4
    assert await runtime.async_fetch()
    assert session.calls == 1
    assert runtime.cachedat == 123
    assert runtime.parsed_snapshot is not None
    assert runtime.last_successful_fetch == clock.value
    assert runtime.consecutive_errors == 0
    assert runtime.last_error is None


@pytest.mark.asyncio
async def test_invalid_snapshot_does_not_replace_last_good_snapshot():
    clock = MutableClock()
    session = FakeSession([
        FakeResponse({"raw": [{"location_uid": "31", "alert_type": "air_raid", "alert_level": "red"}]}),
        FakeResponse({"raw": "broken"}),
    ])
    runtime = make_runtime(session, clock)
    assert await runtime.async_fetch()
    previous = runtime.parsed_snapshot
    previous_success = runtime.last_successful_fetch
    clock.advance(3)
    assert not await runtime.async_fetch()
    assert runtime.parsed_snapshot is previous
    assert runtime.last_successful_fetch == previous_success
    assert runtime.consecutive_errors == 1


@pytest.mark.asyncio
async def test_callbacks_notified_on_success_and_failure():
    session = FakeSession([FakeResponse({"raw": []}), FakeResponse({"raw": None})])
    runtime = make_runtime(session)
    calls = []
    runtime._callbacks["one"] = lambda: calls.append("one")
    assert await runtime.async_fetch()
    assert not await runtime.async_fetch()
    assert calls == ["one", "one"]


@pytest.mark.asyncio
async def test_parallel_fetches_are_serialized_by_request_lock():
    session = FakeSession([
        FakeResponse({"raw": []}, delay=0.03),
        FakeResponse({"raw": []}, delay=0.03),
    ])
    runtime = make_runtime(session)
    results = await asyncio.gather(runtime.async_fetch(), runtime.async_fetch())
    assert results == [True, True]
    assert session.calls == 2
    assert session.max_active == 1


@pytest.mark.asyncio
async def test_ten_entries_share_one_polling_task():
    session = FakeSession([FakeResponse({"raw": []})])
    runtime = make_runtime(session, poll_interval=3600)
    callbacks = []
    for index in range(10):
        await runtime.async_register(str(index), lambda i=index: callbacks.append(i))
    task = runtime.poll_task
    assert task is not None
    assert runtime.registered_entry_count == 10
    await runtime.async_wait_first_cycle()
    assert runtime.poll_task is task
    assert session.calls == 1
    for index in range(9):
        assert not await runtime.async_unregister(str(index))
        assert runtime.poll_task is task
    assert await runtime.async_unregister("9")
    assert runtime.poll_task is None


@pytest.mark.asyncio
async def test_register_race_creates_only_one_loop():
    session = FakeSession([FakeResponse({"raw": []})])
    runtime = make_runtime(session, poll_interval=3600)
    await asyncio.gather(*(
        runtime.async_register(str(i), lambda: None) for i in range(20)
    ))
    await runtime.async_wait_first_cycle()
    assert runtime.registered_entry_count == 20
    assert session.calls == 1
    task = runtime.poll_task
    assert task is not None and not task.done()
    await asyncio.gather(*(runtime.async_unregister(str(i)) for i in range(20)))
    assert runtime.poll_task is None


@pytest.mark.asyncio
async def test_stale_after_failed_cycles_and_first_success_recovers():
    clock = MutableClock()
    session = FakeSession([
        FakeResponse({"raw": []}),
        FakeResponse({"bad": []}),
        FakeResponse({"raw": []}),
    ])
    runtime = make_runtime(session, clock, stale_after=15)
    assert await runtime.async_fetch()
    assert runtime.source_available
    clock.advance(15)
    assert not await runtime.async_fetch()
    assert not runtime.source_available
    assert runtime.parsed_snapshot is not None
    clock.advance(1)
    assert await runtime.async_fetch()
    assert runtime.source_available
    assert runtime.consecutive_errors == 0


@pytest.mark.asyncio
async def test_error_history_is_bounded():
    session = FakeSession([FakeResponse({"broken": True}) for _ in range(25)])
    runtime = make_runtime(session)
    for _ in range(25):
        assert not await runtime.async_fetch()
    assert runtime.consecutive_errors == 25
    assert len(runtime.errors) == 20


@pytest.mark.asyncio
async def test_first_cycle_event_is_set_even_on_poll_failure():
    session = FakeSession([FakeResponse({"raw": None})])
    runtime = make_runtime(session, poll_interval=3600)
    await runtime.async_register("one", lambda: None)
    await asyncio.wait_for(runtime.async_wait_first_cycle(), timeout=1)
    assert runtime.consecutive_errors == 1
    await runtime.async_unregister("one")


@pytest.mark.asyncio
async def test_snapshot_is_parsed_once_even_with_many_entries(monkeypatch):
    session = FakeSession([FakeResponse({"raw": []})])
    runtime = make_runtime(session)
    real_parse = runtime_mod.parse_snapshot
    count = 0
    def counted(*args, **kwargs):
        nonlocal count
        count += 1
        return real_parse(*args, **kwargs)
    monkeypatch.setattr(runtime_mod, "parse_snapshot", counted)
    for index in range(10):
        runtime._callbacks[str(index)] = lambda: None
    assert await runtime.async_fetch()
    assert count == 1
    assert session.calls == 1


@pytest.mark.asyncio
async def test_all_callbacks_observe_same_received_at():
    clock = MutableClock()
    session = FakeSession([FakeResponse({"raw": []})])
    runtime = make_runtime(session, clock)
    seen = []
    for index in range(10):
        runtime._callbacks[str(index)] = lambda: seen.append(runtime.parsed_snapshot.received_at)
    assert await runtime.async_fetch()
    assert len(seen) == 10
    assert len(set(seen)) == 1
    assert seen[0] == clock.value


@pytest.mark.asyncio
async def test_request_timeout_is_poll_error_and_keeps_snapshot():
    clock = MutableClock()
    session = FakeSession([
        FakeResponse({"raw": []}),
        FakeResponse({"raw": []}, delay=0.05),
    ])
    runtime = make_runtime(session, clock, request_timeout=0.005)
    assert await runtime.async_fetch()
    previous = runtime.parsed_snapshot
    clock.advance(3)
    assert not await runtime.async_fetch()
    assert runtime.parsed_snapshot is previous
    assert runtime.consecutive_errors == 1
    assert "Timeout" in (runtime.last_error or "")


@pytest.mark.asyncio
async def test_register_does_not_emit_synthetic_update_before_first_cycle():
    session = FakeSession([FakeResponse({"raw": []})])
    runtime = make_runtime(session, poll_interval=3600)
    calls = []
    await runtime.async_register("one", lambda: calls.append("cycle"))
    # Registration itself is not a source update. The first callback comes from fetch.
    await runtime.async_wait_first_cycle()
    assert calls == ["cycle"]
    await runtime.async_unregister("one")


def test_default_request_timeout_is_shorter_than_poll_interval():
    const = load("const")
    assert const.REQUEST_TIMEOUT_SECONDS < const.POLL_INTERVAL_SECONDS


@pytest.mark.asyncio
async def test_runtime_uses_hass_background_task_when_hass_is_present():
    class FakeHass:
        def __init__(self):
            self.calls = []

        def async_create_background_task(self, coroutine, name, *, eager_start=True):
            self.calls.append((name, eager_start))
            return asyncio.create_task(coroutine, name=name)

    fake_hass = FakeHass()
    session = FakeSession([FakeResponse({"raw": []})])
    runtime = runtime_mod.UAAlertsRuntime(
        fake_hass,
        session=session,
        poll_interval=60,
        request_timeout=1,
    )
    await runtime.async_register("entry", lambda: None)
    await runtime.async_wait_first_cycle()
    assert fake_hass.calls == [("ua_alerts_polling", False)]
    await runtime.async_unregister("entry")

@pytest.mark.asyncio
async def test_timing_update_is_global_and_recalculates_availability():
    clock = MutableClock()
    session = FakeSession([FakeResponse({"raw": []})])
    runtime = make_runtime(session, clock, stale_after=15)
    calls = []
    runtime._callbacks["entry"] = lambda: calls.append(runtime.source_available)
    assert await runtime.async_fetch()
    clock.advance(10)
    assert runtime.source_available
    await runtime.async_update_timing(poll_interval=5, stale_after=8)
    assert runtime.poll_interval == 5
    assert runtime.stale_after == 8
    assert not runtime.source_available
    assert calls[-1] is False
