"""Shared singleton polling runtime for UA Alerts."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
import logging
import time
from typing import Any, Protocol, TYPE_CHECKING

import aiohttp

from .const import (
    MAX_RUNTIME_ERRORS,
    POLL_INTERVAL_SECONDS,
    REQUEST_TIMEOUT_SECONDS,
    RUNTIME_STATUS_RUNNING,
    RUNTIME_STATUS_STOPPED,
    SOURCE_URL,
    STALE_AFTER_SECONDS,
)
from .models import ParsedSnapshot, SnapshotValidationError, parse_snapshot, validate_payload

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


class _SessionProtocol(Protocol):
    def get(self, url: str, **kwargs: Any) -> Any: ...


@dataclass(frozen=True, slots=True)
class RuntimeErrorRecord:
    """One polling error retained for diagnostics."""

    at: datetime
    error: str
    http_status: int | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "at": self.at.isoformat(),
            "error": self.error,
            "http_status": self.http_status,
        }


class UAAlertsRuntime:
    """Own the one HTTP polling loop shared by all config entries."""

    def __init__(
        self,
        hass: HomeAssistant | None,
        *,
        session: _SessionProtocol | None = None,
        source_url: str = SOURCE_URL,
        poll_interval: float = POLL_INTERVAL_SECONDS,
        stale_after: float = STALE_AFTER_SECONDS,
        request_timeout: float = REQUEST_TIMEOUT_SECONDS,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self.hass = hass
        if session is None:
            if hass is None:
                raise ValueError("hass is required when session is not injected")
            from homeassistant.helpers.aiohttp_client import async_get_clientsession

            session = async_get_clientsession(hass)
        self._session = session
        self.source_url = source_url
        self.poll_interval = poll_interval
        self.stale_after = stale_after
        self.request_timeout = request_timeout
        self._now_fn = now_fn or (lambda: datetime.now(UTC))

        self.last_request: datetime | None = None
        self.last_successful_fetch: datetime | None = None
        self.cachedat: Any = None
        self.http_response_time: float | None = None
        self.http_status: int | None = None
        self.consecutive_errors = 0
        self.raw_snapshot: tuple[dict[str, Any], ...] | None = None
        self.parsed_snapshot: ParsedSnapshot | None = None
        self.last_error: str | None = None
        self.errors: deque[RuntimeErrorRecord] = deque(maxlen=MAX_RUNTIME_ERRORS)

        self._poll_task: asyncio.Task[None] | None = None
        self._request_lock = asyncio.Lock()
        self._lifecycle_lock = asyncio.Lock()
        self._callbacks: dict[str, Callable[[], None]] = {}
        self._first_cycle = asyncio.Event()
        self._poll_wakeup = asyncio.Event()

    @property
    def request_lock(self) -> asyncio.Lock:
        """Expose the request lock for diagnostics/tests without making it an entity."""
        return self._request_lock

    @property
    def registered_entries(self) -> tuple[str, ...]:
        """Return registered config entry IDs."""
        return tuple(self._callbacks)

    @property
    def registered_entry_count(self) -> int:
        return len(self._callbacks)

    @property
    def poll_task(self) -> asyncio.Task[None] | None:
        return self._poll_task

    @property
    def status(self) -> str:
        task = self._poll_task
        if task is not None and not task.done():
            return RUNTIME_STATUS_RUNNING
        return RUNTIME_STATUS_STOPPED

    def now(self) -> datetime:
        """Return current time in UTC."""
        value = self._now_fn()
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @property
    def data_age(self) -> float | None:
        if self.last_successful_fetch is None:
            return None
        return max(0.0, (self.now() - self.last_successful_fetch).total_seconds())

    @property
    def source_available(self) -> bool:
        age = self.data_age
        return age is not None and age < self.stale_after

    async def async_register(self, entry_id: str, callback: Callable[[], None]) -> None:
        """Register one entry and start the singleton loop on first registration."""
        async with self._lifecycle_lock:
            self._callbacks[entry_id] = callback
            if self._poll_task is None or self._poll_task.done():
                self._first_cycle.clear()
                coroutine = self._async_poll_loop()
                if self.hass is not None:
                    self._poll_task = self.hass.async_create_background_task(
                        coroutine,
                        "ua_alerts_polling",
                        eager_start=False,
                    )
                else:
                    # Pure unit tests can inject a session without Home Assistant.
                    self._poll_task = asyncio.create_task(
                        coroutine,
                        name="ua_alerts_polling",
                    )

    async def async_unregister(self, entry_id: str) -> bool:
        """Unregister an entry and stop after the final entry is gone.

        Returns True when this was the last registered entry.
        """
        task_to_stop: asyncio.Task[None] | None = None
        async with self._lifecycle_lock:
            self._callbacks.pop(entry_id, None)
            is_last = not self._callbacks
            if is_last and self._poll_task is not None:
                task_to_stop = self._poll_task
                self._poll_task = None

        if task_to_stop is not None:
            task_to_stop.cancel()
            try:
                await task_to_stop
            except asyncio.CancelledError:
                pass
        return is_last

    async def async_wait_first_cycle(self) -> None:
        """Wait until the first polling attempt completes, successful or not."""
        await self._first_cycle.wait()

    async def async_stop(self) -> None:
        """Stop the loop explicitly."""
        task: asyncio.Task[None] | None
        async with self._lifecycle_lock:
            task = self._poll_task
            self._poll_task = None
            self._callbacks.clear()
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _async_poll_loop(self) -> None:
        first_cycle = True
        try:
            while True:
                # Clear before the fetch so a settings change during/after the
                # request cannot be lost before the sleep phase.
                self._poll_wakeup.clear()
                cycle_started = time.monotonic()
                try:
                    await self.async_fetch()
                finally:
                    if first_cycle:
                        self._first_cycle.set()
                        first_cycle = False

                elapsed = time.monotonic() - cycle_started
                delay = max(0.0, self.poll_interval - elapsed)
                if delay > 0:
                    try:
                        await asyncio.wait_for(self._poll_wakeup.wait(), timeout=delay)
                    except TimeoutError:
                        pass
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.exception("Unexpected UA Alerts polling loop failure")
            self._first_cycle.set()

    async def async_update_timing(self, *, poll_interval: float, stale_after: float) -> None:
        """Apply domain-wide timing settings without recreating the runtime."""
        self.poll_interval = float(poll_interval)
        self.stale_after = float(stale_after)
        self._poll_wakeup.set()
        self._notify_entries()

    async def async_fetch(self) -> bool:
        """Run one serialized HTTP polling cycle."""
        async with self._request_lock:
            requested_at = self.now()
            self.last_request = requested_at
            self.http_status = None
            started = time.monotonic()
            try:
                async with asyncio.timeout(self.request_timeout):
                    async with self._session.get(self.source_url) as response:
                        self.http_status = response.status
                        response.raise_for_status()
                        payload = await response.json(content_type=None)

                raw, cachedat = validate_payload(payload)
                received_at = self.now()
                parsed = parse_snapshot(raw, received_at=received_at, cachedat=cachedat)

                # Atomic successful snapshot replacement.
                self.raw_snapshot = tuple(raw)
                self.parsed_snapshot = parsed
                self.cachedat = cachedat
                self.last_successful_fetch = received_at
                self.consecutive_errors = 0
                self.last_error = None
                success = True
            except (
                TimeoutError,
                asyncio.TimeoutError,
                aiohttp.ClientError,
                SnapshotValidationError,
                ValueError,
                TypeError,
            ) as err:
                self.consecutive_errors += 1
                self.last_error = f"{type(err).__name__}: {err}"
                self.errors.append(
                    RuntimeErrorRecord(
                        at=self.now(),
                        error=self.last_error,
                        http_status=self.http_status,
                    )
                )
                _LOGGER.warning("UA Alerts polling failed: %s", self.last_error)
                success = False
            finally:
                self.http_response_time = max(0.0, time.monotonic() - started)

            self._notify_entries()
            return success

    def _notify_entries(self) -> None:
        """Notify all registered entries after every cycle outcome."""
        for entry_id, callback in tuple(self._callbacks.items()):
            try:
                callback()
            except Exception:
                _LOGGER.exception("UA Alerts callback failed for entry %s", entry_id)
