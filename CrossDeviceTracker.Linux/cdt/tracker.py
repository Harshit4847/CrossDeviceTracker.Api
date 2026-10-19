"""The foreground usage tracker.

One "tick" of the tracker:

1. read the active window and the idle time,
2. if the user has been idle for ``idle_threshold_seconds`` close the running
   session at the moment of the last input event,
3. if the application changed, close the previous session and open a new one,
4. every ``max_session_seconds`` flush the running session to the local queue so
   that data keeps flowing to the backend instead of waiting for the user to
   switch applications.

Only sessions longer than ``min_session_seconds`` are recorded, which filters
out alt-tab noise and window manager focus flicker.
"""

from __future__ import annotations

import logging
import signal
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Callable, List, Optional, Sequence

from .apps import should_track
from .idle import IdleSource
from .models import (
    TrackerStats,
    UsageSession,
    WindowInfo,
    new_session_id,
    utcnow,
)
from .queue import PendingLogQueue
from .window import WindowSource

LOGGER = logging.getLogger("cdt.tracker")


@dataclass(slots=True)
class TrackerOptions:
    """Tunables for the tracking loop."""

    poll_interval_seconds: float = 1.0
    idle_threshold_seconds: int = 300
    min_session_seconds: int = 2
    max_session_seconds: int = 900
    #: Poll-to-poll gap after which the gap is treated as suspend time.
    #: ``0`` means "auto" (3x the poll interval, at least 30 seconds).
    gap_threshold_seconds: float = 0.0
    include_apps: Sequence[str] = ()
    exclude_apps: Sequence[str] = ()

    def normalized(self) -> "TrackerOptions":
        self.poll_interval_seconds = min(max(float(self.poll_interval_seconds), 0.25), 60.0)
        self.idle_threshold_seconds = max(int(self.idle_threshold_seconds), 10)
        self.min_session_seconds = max(int(self.min_session_seconds), 1)
        self.max_session_seconds = max(int(self.max_session_seconds), 30)
        # a minimum above the maximum would make chunking impossible
        self.min_session_seconds = min(self.min_session_seconds, self.max_session_seconds)
        self.gap_threshold_seconds = max(float(self.gap_threshold_seconds), 0.0)
        return self


@dataclass(slots=True)
class _Running:
    """Bookkeeping for the application currently in the foreground."""

    session_id: str
    info: WindowInfo
    start: datetime
    last_flush: datetime
    last_activity: datetime
    segments: int = 0


class UsageTracker:
    """Turns active-window polls into queued usage sessions."""

    def __init__(
        self,
        window_source: WindowSource,
        idle_source: IdleSource,
        queue: PendingLogQueue,
        options: Optional[TrackerOptions] = None,
        on_session: Optional[Callable[[UsageSession], None]] = None,
        logger: Optional[logging.Logger] = None,
        clock: Callable[[], datetime] = utcnow,
    ) -> None:
        self.window_source = window_source
        self.idle_source = idle_source
        self.queue = queue
        self.options = (options or TrackerOptions()).normalized()
        self._on_session = on_session
        self._logger = logger or LOGGER
        self._current: Optional[_Running] = None
        self._idle = False
        self._stop_event = threading.Event()
        self._clock = clock
        self._now_value = clock()
        self._last_poll: Optional[datetime] = None
        self.stats = TrackerStats()

    # ------------------------------------------------------------------ #
    # introspection
    # ------------------------------------------------------------------ #
    @property
    def gap_threshold_seconds(self) -> float:
        """Poll-to-poll gap after which the gap is assumed to be suspend time."""
        if self.options.gap_threshold_seconds > 0:
            return float(self.options.gap_threshold_seconds)
        return max(3.0 * self.options.poll_interval_seconds, 30.0)

    @property
    def is_idle(self) -> bool:
        return self._idle

    @property
    def current_window(self) -> Optional[WindowInfo]:
        return self._current.info if self._current else None

    def current_elapsed_seconds(self, now: Optional[datetime] = None) -> int:
        if not self._current:
            return 0
        moment = now or self._last_poll or self._clock()
        return max(0, int((moment - self._current.last_flush).total_seconds()))

    def describe(self) -> dict:
        window = self.current_window
        return {
            "windowSource": self.window_source.name,
            "idleSource": self.idle_source.name,
            "currentApp": window.describe() if window else None,
            "currentAppId": window.app_id if window else None,
            "currentWindowTitle": window.title if window else None,
            "currentSessionSeconds": self.current_elapsed_seconds(),
            "idle": self._idle,
            "stats": self.stats.as_dict(),
        }

    # ------------------------------------------------------------------ #
    # one poll
    # ------------------------------------------------------------------ #
    def tick(self, now: Optional[datetime] = None) -> Optional[WindowInfo]:
        """Run a single poll iteration.  Returns the observed window."""
        moment = now or self._clock()
        self._now_value = moment
        self.stats.polls += 1

        # A large gap between two polls means the machine was suspended (or the
        # process was frozen): the application cannot have been in use then, so
        # the running session is closed at the last confirmed observation.
        if self._last_poll is not None:
            gap = (moment - self._last_poll).total_seconds()
            if gap > self.gap_threshold_seconds:
                self._logger.info(
                    "detected a %.0fs gap since the last poll - not recording it", gap
                )
                self._close(self._last_poll + timedelta(seconds=self.options.poll_interval_seconds))
        self._last_poll = moment

        try:
            info = self.window_source.get_active_window()
        except Exception as error:  # a dead display must not kill the daemon
            self.stats.unknown_window_polls += 1
            self.stats.last_error = f"window source failed: {error}"
            self._logger.warning("active window query failed: %s", error)
            info = None

        try:
            idle_ms = self.idle_source.get_idle_ms()
        except Exception as error:  # pragma: no cover - defensive
            self._logger.debug("idle query failed: %s", error)
            idle_ms = 0

        idle_seconds = max(0.0, idle_ms / 1000.0)

        # ---------------------------------------------------------------- idle
        if idle_seconds >= self.options.idle_threshold_seconds:
            if not self._idle:
                self._idle = True
                self.stats.idle_periods += 1
                self._logger.info(
                    "user idle for %.0fs - closing open session", idle_seconds
                )
            if self._current is not None:
                # the session really ended when the last input happened
                self._close(moment - timedelta(seconds=idle_seconds))
            return info

        if self._idle:
            self._idle = False
            self._logger.info("user is active again")

        # ------------------------------------------------------- no usable window
        if info is None or not should_track(
            info.app_id,
            info.app_name,
            info.title,
            include=self.options.include_apps,
            exclude=self.options.exclude_apps,
        ):
            if info is None:
                self.stats.unknown_window_polls += 1
            self._close(moment)
            return info

        self.stats.last_window = info.describe()

        # ------------------------------------------------------- app switching
        if self._current is None or self._current.info.key != info.key:
            self._close(moment)
            self._current = _Running(
                session_id=new_session_id(),
                info=info,
                start=moment,
                last_flush=moment,
                last_activity=moment,
            )
            self._logger.debug("tracking %s", info.describe())
        else:
            self._current.last_activity = moment
            running_for = (moment - self._current.last_flush).total_seconds()
            if running_for >= self.options.max_session_seconds:
                self._flush(moment, reason="max duration reached")

        return info

    # ------------------------------------------------------------------ #
    # session lifecycle
    # ------------------------------------------------------------------ #
    def _flush(self, end: datetime, reason: str = "") -> None:
        """Write the un-flushed part of the running session to the queue."""
        running = self._current
        if running is None:
            return
        # never record anything beyond the moment we actually observed
        end = min(end, self._now_value + timedelta(seconds=1))
        if end <= running.last_flush:
            return

        # Long spans are stored in ``max_session_seconds`` chunks so that data
        # reaches the backend regularly instead of in one huge entry.
        limit = timedelta(seconds=self.options.max_session_seconds)
        for _ in range(100_000):  # hard stop: never spin, whatever the config
            if end - running.last_flush <= limit:
                break
            self._enqueue(running.last_flush + limit, running, reason)
        self._enqueue(end, running, reason)

    def _enqueue(self, end: datetime, running: _Running, reason: str) -> None:
        start = running.last_flush
        duration = (end - start).total_seconds()
        # always advance, even when the chunk is discarded, so the caller's
        # chunking loop cannot spin
        running.last_flush = end
        if duration < self.options.min_session_seconds:
            return
        session = UsageSession(
            session_id=new_session_id(),
            package_name=running.info.app_id,
            app_name=running.info.app_name,
            start=start,
            end=end,
            duration_seconds=int(round(duration)),
            created_at=self._clock(),
            pid=running.info.pid,
            window_title=running.info.title,
            source=running.info.source or self.window_source.name,
        )
        running.last_flush = end
        running.segments += 1
        if self.queue.add(session):
            self.stats.sessions_created += 1
            self._logger.debug(
                "queued %s (%ds)%s",
                session.app_name,
                session.duration_seconds,
                f" [{reason}]" if reason else "",
            )
            if self._on_session is not None:
                self._on_session(session)

    def _close(self, end: datetime) -> None:
        self._flush(end, reason="session closed")
        self._current = None

    def close(self) -> None:
        """Flush whatever is currently running (used on shutdown)."""
        if self._current is not None:
            self._logger.info(
                "closing session for %s", self._current.info.describe()
            )
            self._close(self._last_poll or self._now_value)

    # ------------------------------------------------------------------ #
    # main loop
    # ------------------------------------------------------------------ #
    def run(
        self,
        duration: Optional[float] = None,
        on_tick: Optional[Callable[[], None]] = None,
    ) -> None:
        """Blocking tracking loop.

        ``duration`` (seconds) is mainly useful for tests and smoke runs; the
        daemon passes ``None`` and runs until SIGINT/SIGTERM.
        """
        self.stats.started_at = utcnow()
        self._stop_event.clear()
        self._install_signal_handlers()

        self._logger.info(
            "tracking started (window=%s idle=%s poll=%.2fs min=%ds max=%ds)",
            self.window_source.name,
            self.idle_source.name,
            self.options.poll_interval_seconds,
            self.options.min_session_seconds,
            self.options.max_session_seconds,
        )

        deadline = None if duration is None else time.monotonic() + duration
        try:
            while not self._stop_event.is_set():
                started = time.monotonic()
                try:
                    self.tick()
                except Exception as error:  # pragma: no cover - keep running
                    self.stats.last_error = str(error)
                    self._logger.exception("tick failed: %s", error)
                if on_tick is not None:
                    on_tick()
                if deadline is not None and time.monotonic() >= deadline:
                    break
                remaining = self.options.poll_interval_seconds - (
                    time.monotonic() - started
                )
                if remaining > 0:
                    self._stop_event.wait(remaining)
        finally:
            self.close()
            self._restore_signal_handlers()
            self._logger.info(
                "tracking stopped: %d polls, %d session(s) queued",
                self.stats.polls,
                self.stats.sessions_created,
            )

    def stop(self) -> None:
        self._stop_event.set()

    # ------------------------------------------------------------------ #
    # signals
    # ------------------------------------------------------------------ #
    def _install_signal_handlers(self) -> None:
        self._previous_handlers: List[tuple] = []
        for signum in (signal.SIGINT, signal.SIGTERM):
            try:
                previous = signal.getsignal(signum)
                signal.signal(signum, self._handle_signal)
                self._previous_handlers.append((signum, previous))
            except (ValueError, OSError):  # not the main thread / unsupported
                continue

    def _restore_signal_handlers(self) -> None:
        for signum, previous in getattr(self, "_previous_handlers", []):
            try:
                signal.signal(signum, previous)
            except (ValueError, OSError):  # pragma: no cover - defensive
                continue
        self._previous_handlers = []

    def _handle_signal(self, signum: int, _frame: Any) -> None:
        self._logger.info("received signal %s - shutting down", signum)
        self.stop()
