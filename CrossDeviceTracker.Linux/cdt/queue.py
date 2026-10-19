"""Offline-first storage for usage sessions that are not uploaded yet.

The queue is a small SQLite database (``~/.local/share/crossdevicetracker/queue.db``)
so that:

* the tracker keeps working when the network or the backend is down,
* a crash never loses already measured time,
* retries are idempotent -- ``ClientSessionId`` is the primary key and the
  backend has a unique index on ``(ClientSessionId, DeviceId)`` with
  ``ON CONFLICT DO NOTHING``.
"""

from __future__ import annotations

import sqlite3
import threading
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from .models import PendingLog, UsageSession, to_iso, utcnow

SCHEMA = """
CREATE TABLE IF NOT EXISTS pending_logs (
    client_session_id TEXT PRIMARY KEY,
    package_name      TEXT NOT NULL,
    app_name          TEXT NOT NULL DEFAULT '',
    start_time_utc    TEXT NOT NULL,
    end_time_utc      TEXT NOT NULL,
    duration_seconds  INTEGER NOT NULL,
    created_at_utc    TEXT NOT NULL,
    enqueued_at       TEXT NOT NULL,
    attempts          INTEGER NOT NULL DEFAULT 0,
    last_error        TEXT,
    next_attempt_at   TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_pending_logs_due
    ON pending_logs (next_attempt_at, enqueued_at);

CREATE TABLE IF NOT EXISTS dead_letters (
    client_session_id TEXT PRIMARY KEY,
    package_name      TEXT NOT NULL,
    app_name          TEXT NOT NULL DEFAULT '',
    start_time_utc    TEXT NOT NULL,
    end_time_utc      TEXT NOT NULL,
    duration_seconds  INTEGER NOT NULL,
    created_at_utc    TEXT NOT NULL,
    dropped_at        TEXT NOT NULL,
    reason            TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class PendingLogQueue:
    """Thread-safe SQLite queue of unsent usage sessions."""

    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(
            str(self.db_path), check_same_thread=False, timeout=30.0
        )
        self._connection.row_factory = sqlite3.Row
        with self._lock:
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA busy_timeout=30000")
            self._connection.execute("PRAGMA synchronous=NORMAL")
            self._connection.executescript(SCHEMA)
            self._connection.commit()

    # ------------------------------------------------------------------ #
    # writing
    # ------------------------------------------------------------------ #
    def add(self, session: UsageSession) -> bool:
        """Queue a session.  Returns ``False`` for duplicates/invalid entries."""
        problem = session.validate()
        if problem:
            return False
        session.clamp_to_past()
        if session.duration_seconds <= 0:
            return False

        with self._lock:
            cursor = self._connection.execute(
                """
                INSERT OR IGNORE INTO pending_logs (
                    client_session_id, package_name, app_name,
                    start_time_utc, end_time_utc, duration_seconds,
                    created_at_utc, enqueued_at, attempts, last_error, next_attempt_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, '')
                """,
                (
                    session.session_id,
                    session.package_name,
                    session.app_name,
                    to_iso(session.start),
                    to_iso(session.end),
                    int(session.duration_seconds),
                    to_iso(session.created_at or utcnow()),
                    to_iso(utcnow()),
                ),
            )
            self._connection.commit()
            return cursor.rowcount > 0

    def add_many(self, sessions: Iterable[UsageSession]) -> int:
        return sum(1 for session in sessions if self.add(session))

    # ------------------------------------------------------------------ #
    # reading
    # ------------------------------------------------------------------ #
    def due(self, limit: int = 50, now: Optional[Any] = None) -> List[PendingLog]:
        """Sessions that are due for another upload attempt."""
        moment = now or utcnow()
        cutoff = to_iso(moment)
        with self._lock:
            rows = self._connection.execute(
                """
                SELECT * FROM pending_logs
                 WHERE next_attempt_at = '' OR next_attempt_at <= ?
                 ORDER BY enqueued_at ASC
                 LIMIT ?
                """,
                (cutoff, int(limit)),
            ).fetchall()
        return [self._to_pending(row) for row in rows]

    @staticmethod
    def _to_pending(row: sqlite3.Row) -> PendingLog:
        return PendingLog(
            client_session_id=row["client_session_id"],
            package_name=row["package_name"],
            app_name=row["app_name"],
            start_time_utc=row["start_time_utc"],
            end_time_utc=row["end_time_utc"],
            duration_seconds=int(row["duration_seconds"]),
            created_at_utc=row["created_at_utc"],
            attempts=int(row["attempts"]),
            last_error=row["last_error"],
            next_attempt_at=row["next_attempt_at"],
            enqueued_at=row["enqueued_at"],
        )

    def peek(self, limit: int = 20) -> List[PendingLog]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM pending_logs ORDER BY enqueued_at ASC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [self._to_pending(row) for row in rows]

    # ------------------------------------------------------------------ #
    # bookkeeping
    # ------------------------------------------------------------------ #
    def mark_sent(self, session_ids: Iterable[str]) -> int:
        ids = [str(session_id) for session_id in session_ids]
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        with self._lock:
            cursor = self._connection.execute(
                f"DELETE FROM pending_logs WHERE client_session_id IN ({placeholders})",
                ids,
            )
            self._connection.commit()
            self._set_meta("last_sync_at", to_iso(utcnow()))
            return cursor.rowcount

    def mark_failure(
        self,
        session_ids: Iterable[str],
        error: str,
        delay_seconds: float = 15.0,
    ) -> None:
        ids = [str(session_id) for session_id in session_ids]
        if not ids:
            return
        next_attempt = to_iso(utcnow() + timedelta(seconds=max(0.0, delay_seconds)))
        placeholders = ",".join("?" for _ in ids)
        message = (error or "")[:500]
        with self._lock:
            self._connection.execute(
                f"""
                UPDATE pending_logs
                   SET attempts = attempts + 1,
                       last_error = ?,
                       next_attempt_at = ?
                 WHERE client_session_id IN ({placeholders})
                """,
                [message, next_attempt, *ids],
            )
            self._connection.commit()

    def quarantine(self, session_ids: Iterable[str], reason: str) -> int:
        """Move permanently rejected entries to a dead-letter table."""
        ids = [str(session_id) for session_id in session_ids]
        if not ids:
            return 0
        placeholders = ",".join("?" for _ in ids)
        dropped_at = to_iso(utcnow())
        with self._lock:
            rows = self._connection.execute(
                f"SELECT * FROM pending_logs WHERE client_session_id IN ({placeholders})",
                ids,
            ).fetchall()
            for row in rows:
                self._connection.execute(
                    """
                    INSERT OR REPLACE INTO dead_letters (
                        client_session_id, package_name, app_name,
                        start_time_utc, end_time_utc, duration_seconds,
                        created_at_utc, dropped_at, reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["client_session_id"],
                        row["package_name"],
                        row["app_name"],
                        row["start_time_utc"],
                        row["end_time_utc"],
                        int(row["duration_seconds"]),
                        row["created_at_utc"],
                        dropped_at,
                        (reason or "")[:500],
                    ),
                )
            cursor = self._connection.execute(
                f"DELETE FROM pending_logs WHERE client_session_id IN ({placeholders})",
                ids,
            )
            self._connection.commit()
            return cursor.rowcount

    def clear(self) -> int:
        with self._lock:
            cursor = self._connection.execute("DELETE FROM pending_logs")
            self._connection.commit()
            return cursor.rowcount

    # ------------------------------------------------------------------ #
    # meta / stats
    # ------------------------------------------------------------------ #
    def _set_meta(self, key: str, value: str) -> None:
        self._connection.execute(
            "INSERT INTO meta (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self._connection.commit()

    def get_meta(self, key: str) -> Optional[str]:
        row = self._connection.execute(
            "SELECT value FROM meta WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            pending = self._connection.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(duration_seconds), 0) AS total "
                "FROM pending_logs"
            ).fetchone()
            failing = self._connection.execute(
                "SELECT COUNT(*) AS n FROM pending_logs WHERE attempts > 0"
            ).fetchone()
            dead = self._connection.execute(
                "SELECT COUNT(*) AS n FROM dead_letters"
            ).fetchone()
        return {
            "pending": int(pending["n"]),
            "pendingSeconds": int(pending["total"]),
            "failing": int(failing["n"]),
            "deadLetters": int(dead["n"]),
            "lastSyncAt": self.get_meta("last_sync_at"),
        }

    def dead_letters(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM dead_letters ORDER BY dropped_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [dict(row) for row in rows]

    def purge_dead_letters(self, older_than_days: int = 30) -> int:
        cutoff = to_iso(utcnow() - timedelta(days=older_than_days))
        with self._lock:
            cursor = self._connection.execute(
                "DELETE FROM dead_letters WHERE dropped_at < ?", (cutoff,)
            )
            self._connection.commit()
            return cursor.rowcount

    def close(self) -> None:
        with self._lock:
            try:
                self._connection.close()
            except sqlite3.Error:  # pragma: no cover - defensive
                pass

    def __enter__(self) -> "PendingLogQueue":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


def backoff_delay(attempts: int, base_seconds: int, max_seconds: int) -> float:
    """Exponential backoff: 15s, 30s, 60s ... capped at ``max_seconds``."""
    if attempts <= 0:
        return float(base_seconds)
    return float(min(base_seconds * (2 ** min(attempts - 1, 10)), max_seconds))
