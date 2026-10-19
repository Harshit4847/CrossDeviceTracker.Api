"""A tiny in-process stand-in for ``CrossDeviceTracker.Api`` used by the tests.

It implements just enough of the contract to exercise the client end to end:
device linking, time-log submission (with the same validation rules as the real
controller) and a canned dashboard summary.
"""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional

REQUIRED_FIELDS = (
    "packageName",
    "startTimeUtc",
    "endTimeUtc",
    "durationSeconds",
    "createdAtUtc",
    "clientSessionId",
)


class StubState:
    """Everything the stub remembers between requests."""

    def __init__(self) -> None:
        self.device_id = str(uuid.uuid4())
        self.device_jwt = "stub-device-jwt"
        self.link_tokens: List[str] = []
        self.time_logs: List[Dict[str, Any]] = []
        self.batches: List[List[Dict[str, Any]]] = []
        self.requests: List[Dict[str, Any]] = []
        self.fail_next_batch: Optional[int] = None
        self.reject_next_batch: bool = False
        self.lock = threading.Lock()

    def log(self, method: str, path: str, body: Any, headers: Dict[str, str]) -> None:
        with self.lock:
            self.requests.append(
                {
                    "method": method,
                    "path": path,
                    "body": body,
                    "authorization": headers.get("Authorization", ""),
                    "userAgent": headers.get("User-Agent", ""),
                }
            )


STATE = StubState()


def _parse_iso(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    return datetime.fromisoformat(text)


def _validate(entry: Dict[str, Any]) -> Optional[str]:
    """Mirror of ``TimeLogsController`` validation."""
    for field in REQUIRED_FIELDS:
        if field not in entry:
            return f"{field} is required"
    if not (entry.get("packageName") or "").strip() and not (entry.get("appName") or "").strip():
        return "AppName or PackageName is required"
    if _parse_iso(entry["startTimeUtc"]) > datetime.now(timezone.utc):
        return "StartTimeUtc cannot be in the future"
    if _parse_iso(entry["endTimeUtc"]) <= _parse_iso(entry["startTimeUtc"]):
        return "EndTimeUtc must be after StartTimeUtc"
    computed = (_parse_iso(entry["endTimeUtc"]) - _parse_iso(entry["startTimeUtc"])).total_seconds()
    if abs(computed - float(entry["durationSeconds"])) > 1.0:
        return "DurationSeconds must match (EndTimeUtc - StartTimeUtc)"
    if int(entry["durationSeconds"]) <= 0:
        return "DurationSeconds must be greater than zero"
    if len(entry["clientSessionId"]) > 36:
        return "ClientSessionId too long"
    return None


class Handler(BaseHTTPRequestHandler):
    server_version = "CrossDeviceTrackerStub/1.0"
    protocol_version = "HTTP/1.1"

    # ------------------------------------------------------------------ #
    def log_message(self, *_args: Any) -> None:  # silence the test output
        return

    def _send(self, status: int, payload: Any) -> None:
        body = json.dumps(payload).encode("utf-8") if payload is not None else b""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _read_body(self) -> Any:
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return None

    def _authorized(self) -> bool:
        return bool(self.headers.get("Authorization", "").startswith("Bearer "))

    # ------------------------------------------------------------------ #
    def do_GET(self) -> None:  # noqa: N802
        STATE.log("GET", self.path, None, dict(self.headers))
        if self.path.startswith("/swagger"):
            self._send(200, {"swagger": "2.0"})
            return
        if self.path.startswith("/api/dashboard/summary"):
            if not self._authorized():
                self._send(401, {"error": "missing token"})
                return
            self._send(
                200,
                {
                    "today": {
                        "totalScreenTimeSeconds": 7380,
                        "totalDeviceUsageSeconds": 7380,
                        "overlapTimeSeconds": 0,
                        "sessionCount": 42,
                    },
                    "yesterday": {"totalScreenTimeSeconds": 6200, "sessionCount": 30},
                    "thisWeek": {"totalScreenTimeSeconds": 41000, "sessionCount": 210},
                    "thisMonth": {"totalScreenTimeSeconds": 160000, "sessionCount": 900},
                    "deviceCount": 2,
                    "appCount": 7,
                    "mostUsedApp": {"appName": "Google Chrome", "durationSeconds": 5100},
                },
            )
            return
        if self.path.startswith("/api/dashboard/apps"):
            self._send(
                200,
                [
                    {"appName": "Google Chrome", "durationSeconds": 5100, "percentage": 62.5, "sessionCount": 30},
                    {"appName": "Visual Studio Code", "durationSeconds": 2100, "percentage": 25.0, "sessionCount": 12},
                ],
            )
            return
        if self.path.startswith("/api/dashboard/devices"):
            self._send(
                200,
                [
                    {
                        "deviceName": "stub-laptop",
                        "platform": "Linux",
                        "durationSeconds": 7380,
                        "sessionCount": 42,
                        "lastDataSyncAt": "2026-10-19T10:00:00Z",
                    }
                ],
            )
            return
        if self.path.startswith("/api/dashboard/timeline"):
            self._send(200, [])
            return
        if self.path.startswith("/api/analytics/"):
            self._send(200, [{"label": "2026-10-19", "durationSeconds": 7380, "sessionCount": 42}])
            return
        if self.path.startswith("/api/timelogs"):
            if not self._authorized():
                self._send(401, {"error": "missing token"})
                return
            self._send(200, {"items": [], "nextCursor": None, "hasMore": False})
            return
        if self.path.startswith("/api/devices"):
            if not self._authorized():
                self._send(401, {"error": "missing token"})
                return
            self._send(
                200,
                [
                    {
                        "id": STATE.device_id,
                        "userId": str(uuid.uuid4()),
                        "deviceName": "stub-laptop",
                        "platform": "Linux",
                        "installationId": None,
                        "tokenVersion": 1,
                        "isRevoked": False,
                        "lastDataSyncAt": None,
                        "createdAt": "2026-10-01T00:00:00Z",
                    }
                ],
            )
            return
        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        body = self._read_body()
        STATE.log("POST", self.path, body, dict(self.headers))

        if self.path.startswith("/api/auth/token"):
            if (body or {}).get("email") == "user@example.com" and (body or {}).get("password") == "secret":
                self._send(200, {"accessToken": "stub-user-jwt", "email": "user@example.com"})
            else:
                self._send(401, "Invalid Email or password")
            return

        if self.path.startswith("/api/auth/register"):
            self._send(201, {"userId": str(uuid.uuid4()), "email": (body or {}).get("email")})
            return

        if self.path.startswith("/api/devices/link-token"):
            if not self._authorized():
                self._send(401, {"error": "missing token"})
                return
            token = "stub-link-token-0123456789abcdef"
            STATE.link_tokens.append(token)
            self._send(200, {"token": token, "expiresAt": "2026-10-19T11:00:00+00:00"})
            return

        if self.path.startswith("/api/devices/link"):
            if not body or len(str(body.get("linkToken", ""))) < 20:
                self._send(400, "LinkToken must be between 20 and 200 characters")
                return
            self._send(200, {"deviceJwt": STATE.device_jwt, "deviceId": STATE.device_id})
            return

        if self.path.startswith("/api/devices"):
            if not self._authorized():
                self._send(401, {"error": "missing token"})
                return
            self._send(
                200,
                {
                    "deviceId": STATE.device_id,
                    "deviceJwt": STATE.device_jwt,
                    "wasCreated": True,
                    "deviceName": (body or {}).get("deviceName", ""),
                    "platform": (body or {}).get("platform", ""),
                },
            )
            return

        if self.path.startswith("/api/timelogs/batch"):
            if not self._authorized():
                self._send(401, {"error": "missing token"})
                return
            entries = body or []
            if not isinstance(entries, list) or not entries:
                self._send(400, "Request body is null or empty")
                return
            for entry in entries:
                problem = _validate(entry)
                if problem:
                    self._send(400, problem)
                    return
            with STATE.lock:
                if STATE.reject_next_batch:
                    STATE.reject_next_batch = False
                    self._send(400, "simulated backend rejection")
                    return
                if STATE.fail_next_batch is not None:
                    STATE.fail_next_batch -= 1
                    self._send(500, "An unexpected error occurred")
                    return
                STATE.batches.append(entries)
                accepted = [entry["clientSessionId"] for entry in entries]
                STATE.time_logs.extend(entries)
            self._send(200, {"acceptedClientSessionIds": accepted})
            return

        if self.path.startswith("/api/timelogs"):
            if not self._authorized():
                self._send(401, {"error": "missing token"})
                return
            if not isinstance(body, dict) or _validate(body):
                self._send(400, "invalid time log")
                return
            with STATE.lock:
                STATE.time_logs.append(body)
            self._send(200, {"id": str(uuid.uuid4())})
            return

        self._send(404, {"error": "not found"})


class StubApiServer:
    """Context manager wrapper around the stub HTTP server."""

    def __init__(self) -> None:
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def port(self) -> int:
        return self.server.server_address[1]

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def __enter__(self) -> "StubApiServer":
        self.thread.start()
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    # helpers -------------------------------------------------------------
    def reset(self) -> None:
        with STATE.lock:
            STATE.time_logs.clear()
            STATE.batches.clear()
            STATE.requests.clear()
            STATE.link_tokens.clear()
            STATE.fail_next_batch = None
            STATE.reject_next_batch = False

    @property
    def state(self) -> StubState:
        return STATE
