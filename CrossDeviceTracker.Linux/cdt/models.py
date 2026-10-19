"""Data models shared across the Linux client.

The payload dictionaries produced here deliberately match the JSON contract of
``CrossDeviceTracker.Api`` (``CreateTimeLogRequest`` / ``CreateTimeLogsBatch``),
including the camelCase property names that ASP.NET Core's web JSON defaults
accept.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional

#: ``ClientSessionId`` is stored in a ``character varying(36)`` column, so the
#: client must never generate anything longer than a canonical GUID string.
CLIENT_SESSION_ID_MAX_LENGTH = 36


def utcnow() -> datetime:
    """Current time as an aware UTC ``datetime``."""
    return datetime.now(timezone.utc)


def to_iso(moment: datetime) -> str:
    """Serialise a datetime the way .NET's ``System.Text.Json`` expects it."""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def parse_iso(value: str) -> datetime:
    """Parse an ISO-8601 timestamp, always returning an aware UTC datetime."""
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def new_session_id() -> str:
    """A 36 character GUID used as the idempotency key for a usage session."""
    return str(uuid.uuid4())


def human_duration(seconds: Optional[int]) -> str:
    """``8130`` -> ``"2h 15m"`` (compact, human friendly)."""
    if seconds is None:
        return "-"
    seconds = int(max(0, round(seconds)))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    parts: list[str] = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


@dataclass(slots=True)
class WindowInfo:
    """A snapshot of whatever window/app is currently in the foreground."""

    app_id: str
    app_name: str = ""
    title: str = ""
    pid: Optional[int] = None
    source: str = ""

    @property
    def key(self) -> str:
        """Identity of the tracked application (used to detect app switches)."""
        return self.app_id or self.app_name or self.title

    def describe(self) -> str:
        return self.app_name or self.app_id or self.title or "unknown"


@dataclass(slots=True)
class UsageSession:
    """One contiguous block of foreground time for a single application.

    Long running applications are flushed in ``max_session_seconds`` sized
    segments so that data reaches the backend regularly instead of piling up
    until the application is closed.
    """

    session_id: str
    package_name: str
    app_name: str
    start: datetime
    end: datetime
    duration_seconds: int
    created_at: Optional[datetime] = None
    pid: Optional[int] = None
    window_title: str = ""
    source: str = ""
    attempts: int = 0
    last_error: Optional[str] = None

    # ------------------------------------------------------------------ utils
    @property
    def duration(self) -> timedelta:
        return self.end - self.start

    def validate(self) -> Optional[str]:
        """Return a validation error message, or ``None`` when server-ready.

        Mirrors the guards implemented by ``TimeLogsController`` so that an
        invalid entry is never allowed to poison a whole batch upload.
        """
        if not (self.package_name or "").strip():
            return "PackageName is required"
        if self.duration_seconds <= 0:
            return "DurationSeconds must be greater than zero"
        if self.end <= self.start:
            return "EndTimeUtc must be after StartTimeUtc"
        computed = self.duration.total_seconds()
        if abs(computed - self.duration_seconds) > 1.0:
            return (
                "DurationSeconds must match (EndTimeUtc - StartTimeUtc): "
                f"computed={computed:.3f} reported={self.duration_seconds}"
            )
        if len(self.session_id) > CLIENT_SESSION_ID_MAX_LENGTH:
            return (
                "ClientSessionId must be at most "
                f"{CLIENT_SESSION_ID_MAX_LENGTH} characters"
            )
        return None

    def clamp_to_past(self, now: Optional[datetime] = None) -> bool:
        """Nudge timestamps that sit in the future (skewed local clock).

        The backend rejects ``StartTimeUtc`` values in the future, which would
        otherwise silently block an entire batch.  Returns ``True`` when the
        session was adjusted.
        """
        now = now or utcnow()
        changed = False
        if self.end > now:
            # Shift the whole interval back so its length is preserved.
            shift = self.end - now
            self.start -= shift
            self.end -= shift
            changed = True
        if self.start > now:
            shift = self.start - now
            self.start -= shift
            self.end -= shift
            changed = True
        recomputed = round(self.duration.total_seconds())
        if recomputed != self.duration_seconds:
            self.duration_seconds = max(0, recomputed)
            changed = True
        return changed

    def to_payload(self, created_at: Optional[datetime] = None) -> dict[str, Any]:
        """JSON body for ``POST /api/timelogs`` / ``POST /api/timelogs/batch``."""
        return {
            "packageName": self.package_name,
            "appName": self.app_name or None,
            "startTimeUtc": to_iso(self.start),
            "endTimeUtc": to_iso(self.end),
            "durationSeconds": int(self.duration_seconds),
            "createdAtUtc": to_iso(created_at or self.created_at or utcnow()),
            "clientSessionId": self.session_id,
        }

    def summary(self) -> str:
        return (
            f"{self.app_name or self.package_name} "
            f"{human_duration(self.duration_seconds)} "
            f"({to_iso(self.start)} -> {to_iso(self.end)})"
        )


@dataclass(slots=True)
class PendingLog:
    """A queued usage session read back from the local SQLite database."""

    client_session_id: str
    package_name: str
    app_name: str
    start_time_utc: str
    end_time_utc: str
    duration_seconds: int
    created_at_utc: str
    attempts: int = 0
    last_error: Optional[str] = None
    next_attempt_at: str = ""
    enqueued_at: str = ""

    def to_session(self) -> UsageSession:
        return UsageSession(
            session_id=self.client_session_id,
            package_name=self.package_name,
            app_name=self.app_name,
            start=parse_iso(self.start_time_utc),
            end=parse_iso(self.end_time_utc),
            duration_seconds=int(self.duration_seconds),
            created_at=parse_iso(self.created_at_utc),
            attempts=self.attempts,
            last_error=self.last_error,
        )

    def to_payload(self) -> dict[str, Any]:
        return self.to_session().to_payload()


@dataclass(slots=True)
class SyncResult:
    """Outcome of a single synchronisation pass."""

    sent: int = 0
    accepted: int = 0
    dropped: int = 0
    retried: int = 0
    error: Optional[str] = None
    auth_error: bool = False

    @property
    def ok(self) -> bool:
        return self.error is None

    def as_dict(self) -> dict[str, Any]:
        return {
            "sent": self.sent,
            "accepted": self.accepted,
            "dropped": self.dropped,
            "retried": self.retried,
            "error": self.error,
            "authError": self.auth_error,
        }


@dataclass(slots=True)
class TrackerStats:
    """Runtime counters exposed by ``cdt status --local``."""

    started_at: Optional[datetime] = None
    polls: int = 0
    sessions_created: int = 0
    sessions_sent: int = 0
    idle_periods: int = 0
    unknown_window_polls: int = 0
    last_window: Optional[str] = None
    last_error: Optional[str] = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "startedAt": to_iso(self.started_at) if self.started_at else None,
            "polls": self.polls,
            "sessionsCreated": self.sessions_created,
            "sessionsSent": self.sessions_sent,
            "idlePeriods": self.idle_periods,
            "unknownWindowPolls": self.unknown_window_polls,
            "lastWindow": self.last_window,
            "lastError": self.last_error,
        }


@dataclass(slots=True)
class LinkResult:
    """Result of ``POST /api/devices/link``."""

    device_id: str
    device_jwt: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "LinkResult":
        device_id = payload.get("deviceId") or payload.get("DeviceId") or ""
        device_jwt = payload.get("deviceJwt") or payload.get("DeviceJwt") or ""
        if not device_id or not device_jwt:
            raise ValueError("Link response did not contain deviceId/deviceJwt")
        return cls(device_id=str(device_id), device_jwt=str(device_jwt))


@dataclass(slots=True)
class DeviceInfo:
    """A device as returned by ``GET /api/devices``."""

    id: str
    device_name: str = ""
    platform: str = ""
    installation_id: Optional[str] = None
    token_version: int = 0
    is_revoked: bool = False
    last_data_sync_at: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "DeviceInfo":
        def pick(*names: str, default: Any = "") -> Any:
            for name in names:
                if payload.get(name) is not None:
                    return payload[name]
            return default

        return cls(
            id=str(pick("id", "Id")),
            device_name=str(pick("deviceName", "DeviceName")),
            platform=str(pick("platform", "Platform")),
            installation_id=pick("installationId", "InstallationId", default=None),
            token_version=int(pick("tokenVersion", "TokenVersion", default=0) or 0),
            is_revoked=bool(pick("isRevoked", "IsRevoked", default=False)),
            last_data_sync_at=pick("lastDataSyncAt", "LastDataSyncAt", default=None),
            created_at=pick("createdAt", "CreatedAt", default=None),
        )


@dataclass(slots=True)
class AppUsage:
    """A row of ``GET /api/dashboard/apps``."""

    app_name: str
    duration_seconds: int
    percentage: float
    session_count: int

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "AppUsage":
        return cls(
            app_name=str(payload.get("appName") or payload.get("AppName") or ""),
            duration_seconds=int(payload.get("durationSeconds") or 0),
            percentage=float(payload.get("percentage") or payload.get("Percentage") or 0.0),
            session_count=int(payload.get("sessionCount") or 0),
        )


@dataclass(slots=True)
class DailyUsage:
    """A bucket of ``GET /api/analytics/daily`` (and weekly/monthly/hourly)."""

    label: str
    duration_seconds: int
    session_count: int = 0

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "DailyUsage":
        label = (
            payload.get("date")
            or payload.get("label")
            or payload.get("period")
            or payload.get("day")
            or payload.get("hour")
            or ""
        )
        return cls(
            label=str(label),
            duration_seconds=int(payload.get("durationSeconds") or payload.get("totalSeconds") or 0),
            session_count=int(payload.get("sessionCount") or 0),
        )


@dataclass(slots=True)
class _Accumulator:
    """Internal helper used while a session is being tracked."""

    session_id: str
    info: WindowInfo
    start: datetime
    last_flush: datetime
    last_activity: datetime
    segments: int = field(default=0)
