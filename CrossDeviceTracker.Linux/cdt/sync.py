"""Upload engine: turns queued sessions into backend time logs."""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from .api import ApiClient, ApiError
from .models import PendingLog, SyncResult
from .queue import PendingLogQueue, backoff_delay

LOGGER = logging.getLogger("cdt.sync")

#: How long to wait before re-trying entries the backend failed to acknowledge.
_UNACKNOWLEDGED_DELAY_SECONDS = 60.0


class AuthRequiredError(Exception):
    """The device JWT was rejected (401/403) -- the device must be re-linked."""


class SyncEngine:
    """Flushes the local queue to ``POST /api/timelogs/batch``."""

    def __init__(
        self,
        api: ApiClient,
        queue: PendingLogQueue,
        token_provider: Callable[[], str],
        batch_size: int = 50,
        retry_base_seconds: int = 15,
        retry_max_seconds: int = 900,
    ) -> None:
        self.api = api
        self.queue = queue
        self._token_provider = token_provider
        self.batch_size = max(1, int(batch_size))
        self.retry_base_seconds = max(1, int(retry_base_seconds))
        self.retry_max_seconds = max(1, int(retry_max_seconds))
        self.last_result: Optional[SyncResult] = None

    # ------------------------------------------------------------------ #
    def _token(self) -> str:
        token = self._token_provider()
        if not token:
            raise AuthRequiredError("device is not linked - run 'cdt link' first")
        return token

    def _prepare(
        self, rows: Sequence[PendingLog]
    ) -> Tuple[List[Tuple[PendingLog, Dict[str, Any]]], List[Tuple[str, str]]]:
        """Validate and normalise rows; returns ``(sendable, rejected)``."""
        sendable: List[Tuple[PendingLog, Dict[str, Any]]] = []
        rejected: List[Tuple[str, str]] = []
        for row in rows:
            session = row.to_session()
            problem = session.validate()
            if problem is None:
                session.clamp_to_past()
                problem = session.validate()
            if problem is not None or session.duration_seconds <= 0:
                rejected.append((row.client_session_id, problem or "non positive duration"))
                continue
            sendable.append((row, session.to_payload()))
        return sendable, rejected

    # ------------------------------------------------------------------ #
    def sync_once(self) -> SyncResult:
        """One upload pass.  Never raises for network/API problems."""
        rows = self.queue.due(self.batch_size)
        if not rows:
            result = SyncResult()
            self.last_result = result
            return result

        sendable, rejected = self._prepare(rows)
        if rejected:
            self.queue.quarantine(
                [session_id for session_id, _ in rejected],
                reason="; ".join(sorted({reason for _, reason in rejected})),
            )
            LOGGER.warning("dropped %d invalid queued session(s)", len(rejected))

        if not sendable:
            result = SyncResult(dropped=len(rejected))
            self.last_result = result
            return result

        try:
            token = self._token()
        except AuthRequiredError as error:
            result = SyncResult(sent=len(sendable), error=str(error), auth_error=True)
            self.last_result = result
            return result

        payloads = [payload for _, payload in sendable]
        ids = [row.client_session_id for row, _ in sendable]

        try:
            accepted = self.api.create_time_logs_batch(token, payloads)
        except ApiError as error:
            if error.is_auth_error:
                LOGGER.error("backend rejected the device token: %s", error)
                result = SyncResult(
                    sent=len(sendable), error=str(error), auth_error=True
                )
                self.last_result = result
                return result
            if error.is_validation_error:
                LOGGER.warning(
                    "batch rejected (%s) - falling back to single uploads", error
                )
                return self._sync_individually(sendable, token=token)
            LOGGER.warning("batch upload failed: %s", error)
            self.queue.mark_failure(
                ids,
                str(error),
                backoff_delay(
                    self._max_attempts(rows), self.retry_base_seconds, self.retry_max_seconds
                ),
            )
            result = SyncResult(
                sent=len(sendable), retried=len(sendable), error=str(error)
            )
            self.last_result = result
            return result

        acknowledged = {str(item) for item in accepted}
        if acknowledged:
            confirmed = [i for i in ids if i in acknowledged]
            unconfirmed = [i for i in ids if i not in acknowledged]
        else:  # pragma: no cover - defensive (backend always echoes the ids)
            confirmed, unconfirmed = ids, []

        self.queue.mark_sent(confirmed)
        if unconfirmed:
            LOGGER.warning(
                "backend did not acknowledge %d session(s); they will be retried",
                len(unconfirmed),
            )
            self.queue.mark_failure(
                unconfirmed, "not acknowledged by backend", _UNACKNOWLEDGED_DELAY_SECONDS
            )

        result = SyncResult(
            sent=len(sendable),
            accepted=len(confirmed),
            retried=len(unconfirmed),
            dropped=len(rejected),
        )
        self.last_result = result
        LOGGER.info(
            "synced %d session(s) (%d accepted, %d retried, %d dropped)",
            result.sent,
            result.accepted,
            result.retried,
            result.dropped,
        )
        return result

    # ------------------------------------------------------------------ #
    def _sync_individually(
        self,
        sendable: Sequence[Tuple[PendingLog, Dict[str, Any]]],
        token: str,
    ) -> SyncResult:
        """Retry a rejected batch entry-by-entry to isolate the bad ones."""
        accepted: List[str] = []
        dropped: List[Tuple[str, str]] = []
        failed: List[Tuple[str, str]] = []

        for row, payload in sendable:
            try:
                self.api.create_time_log(token, payload)
                accepted.append(row.client_session_id)
            except ApiError as error:
                if error.is_auth_error:
                    return SyncResult(
                        sent=len(sendable), error=str(error), auth_error=True
                    )
                if error.is_validation_error:
                    dropped.append((row.client_session_id, str(error)))
                else:
                    failed.append((row.client_session_id, str(error)))

        if dropped:
            self.queue.quarantine(
                [session_id for session_id, _ in dropped],
                reason="; ".join(sorted({reason for _, reason in dropped})),
            )
        if accepted:
            self.queue.mark_sent(accepted)
        if failed:
            self.queue.mark_failure(
                [session_id for session_id, _ in failed],
                failed[0][1],
                backoff_delay(1, self.retry_base_seconds, self.retry_max_seconds),
            )

        result = SyncResult(
            sent=len(accepted) + len(dropped) + len(failed),
            accepted=len(accepted),
            dropped=len(dropped),
            retried=len(failed),
            error=failed[0][1] if failed else None,
        )
        self.last_result = result
        return result

    @staticmethod
    def _max_attempts(rows: Sequence[PendingLog]) -> int:
        return max((row.attempts for row in rows), default=0)


class SyncLoop(threading.Thread):
    """Background thread that periodically drains the queue."""

    def __init__(
        self,
        engine: SyncEngine,
        interval_seconds: int = 30,
        on_result: Optional[Callable[[SyncResult], None]] = None,
    ) -> None:
        super().__init__(name="cdt-sync", daemon=True)
        self.engine = engine
        self.interval = max(1, int(interval_seconds))
        self._on_result = on_result
        self._stop_event = threading.Event()
        self._wake = threading.Event()
        self.last_error: Optional[str] = None
        self.auth_error = False

    # ------------------------------------------------------------------ #
    def run(self) -> None:
        while not self._stop_event.is_set():
            triggered = self._wake.wait(self.interval)
            if self._stop_event.is_set():
                break
            if triggered:
                self._wake.clear()
            try:
                result = self.engine.sync_once()
                self.auth_error = result.auth_error
                self.last_error = result.error
                if self._on_result is not None:
                    self._on_result(result)
            except Exception as error:  # pragma: no cover - keep the loop alive
                LOGGER.exception("sync loop error: %s", error)
                self.last_error = str(error)

    def sync_now(self) -> SyncResult:
        """Wake the loop immediately and wait for one synchronous pass."""
        result = self.engine.sync_once()
        self.auth_error = result.auth_error
        self.last_error = result.error
        if self._on_result is not None:
            self._on_result(result)
        return result

    def stop(self, timeout: float = 10.0) -> None:
        self._stop_event.set()
        self._wake.set()
        if self.is_alive() and threading.current_thread() is not self:
            self.join(timeout=timeout)
