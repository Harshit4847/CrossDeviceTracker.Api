"""Minimal, dependency-free HTTP client for ``CrossDeviceTracker.Api``.

Only the standard library is used (``urllib.request``) so the client runs on any
Linux box with Python 3.10+ and nothing else installed.
"""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence

from . import USER_AGENT
from .models import AppUsage, DailyUsage, DeviceInfo, LinkResult


class ApiError(Exception):
    """A non-success response from the backend."""

    def __init__(
        self,
        message: str,
        status: int = 0,
        payload: Any = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.status = int(status)
        self.payload = payload
        self.retryable = retryable

    @property
    def is_auth_error(self) -> bool:
        return self.status in (401, 403)

    @property
    def is_validation_error(self) -> bool:
        return self.status in (400, 422)

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        prefix = f"HTTP {self.status}" if self.status else "network error"
        return f"{prefix}: {super().__str__()}"


def _extract_message(status: int, body: bytes, content_type: str = "") -> str:
    """Turn an ASP.NET Core error body into a short human readable string."""
    text = (body or b"").decode("utf-8", "replace").strip()
    if not text:
        return f"request failed with status {status}"
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return text
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        for key in ("error", "message", "detail", "title"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        errors = data.get("errors")
        if isinstance(errors, dict) and errors:
            parts = []
            for key, value in errors.items():
                if isinstance(value, list):
                    parts.append(f"{key}: {', '.join(str(v) for v in value)}")
                else:
                    parts.append(f"{key}: {value}")
            return "; ".join(parts)
    return text


@dataclass(slots=True)
class ApiResponse:
    status: int
    body: bytes
    headers: Mapping[str, str]

    def json(self) -> Any:
        if not self.body:
            return None
        try:
            return json.loads(self.body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return None


class ApiClient:
    """Thin wrapper around the REST surface of the backend."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 15.0,
        opener: Optional[urllib.request.OpenerDirector] = None,
    ) -> None:
        self.base_url = (base_url or "").strip().rstrip("/")
        self.timeout = float(timeout)
        self._opener = opener or urllib.request.build_opener()

    # ------------------------------------------------------------------ #
    # low level
    # ------------------------------------------------------------------ #
    def _url(self, path: str, query: Optional[Mapping[str, Any]] = None) -> str:
        if not path.startswith("/"):
            path = "/" + path
        url = self.base_url + path
        if query:
            params = {
                key: value
                for key, value in query.items()
                if value is not None and value != ""
            }
            if params:
                url += "?" + urllib.parse.urlencode(params)
        return url

    def request(
        self,
        method: str,
        path: str,
        *,
        body: Any = None,
        token: Optional[str] = None,
        query: Optional[Mapping[str, Any]] = None,
        timeout: Optional[float] = None,
    ) -> ApiResponse:
        data = None
        headers = {
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        }
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"

        request = urllib.request.Request(
            self._url(path, query), data=data, headers=headers, method=method.upper()
        )
        try:
            with self._opener.open(request, timeout=timeout or self.timeout) as response:
                return ApiResponse(
                    status=response.status,
                    body=response.read(),
                    headers=dict(response.headers.items()),
                )
        except urllib.error.HTTPError as error:  # 4xx / 5xx
            payload = error.read()
            message = _extract_message(error.code, payload)
            retryable = error.code >= 500 or error.code in (408, 429)
            raise ApiError(message, status=error.code, payload=payload, retryable=retryable) from error
        except urllib.error.URLError as error:
            reason = getattr(error, "reason", error)
            if isinstance(reason, socket.timeout):
                message = f"request timed out after {timeout or self.timeout:.0f}s"
            else:
                message = f"cannot reach {self.base_url} ({reason})"
            raise ApiError(message, status=0, retryable=True) from error
        except (socket.timeout, TimeoutError) as error:
            raise ApiError("request timed out", status=0, retryable=True) from error
        except OSError as error:  # connection reset, refused, DNS, ...
            raise ApiError(f"network error: {error}", status=0, retryable=True) from error

    # ------------------------------------------------------------------ #
    # auth
    # ------------------------------------------------------------------ #
    def register(self, email: str, password: str) -> Dict[str, Any]:
        response = self.request(
            "POST", "/api/auth/register", body={"email": email, "password": password}
        )
        return response.json() or {}

    def login(self, email: str, password: str) -> Dict[str, Any]:
        response = self.request(
            "POST", "/api/auth/token", body={"email": email, "password": password}
        )
        return response.json() or {}

    # ------------------------------------------------------------------ #
    # devices
    # ------------------------------------------------------------------ #
    def list_devices(self, user_jwt: str) -> List[DeviceInfo]:
        response = self.request("GET", "/api/devices", token=user_jwt)
        payload = response.json()
        if isinstance(payload, list):
            return [DeviceInfo.from_payload(item) for item in payload if isinstance(item, dict)]
        return []

    def create_link_token(self, user_jwt: str) -> Dict[str, Any]:
        response = self.request("POST", "/api/devices/link-token", token=user_jwt)
        return response.json() or {}

    def link_device(self, link_token: str, device_name: str, platform: str) -> LinkResult:
        """Pair this machine using a one-time desktop link token.

        Note: ``POST /api/devices/link`` is intentionally *not* ``[Authorize]``d
        -- the one-time token itself carries the proof of ownership.
        """
        response = self.request(
            "POST",
            "/api/devices/link",
            body={
                "linkToken": link_token.strip(),
                "deviceName": device_name,
                "platform": platform,
            },
        )
        return LinkResult.from_payload(response.json() or {})

    def register_device(
        self, user_jwt: str, device_name: str, platform: str, installation_id: str
    ) -> Dict[str, Any]:
        response = self.request(
            "POST",
            "/api/devices",
            token=user_jwt,
            body={
                "deviceName": device_name,
                "platform": platform,
                "installationId": installation_id,
            },
        )
        return response.json() or {}

    # ------------------------------------------------------------------ #
    # time logs
    # ------------------------------------------------------------------ #
    def create_time_logs_batch(self, device_jwt: str, entries: Sequence[Mapping[str, Any]]) -> List[str]:
        response = self.request("POST", "/api/timelogs/batch", body=list(entries), token=device_jwt)
        payload = response.json() or {}
        accepted = (
            payload.get("acceptedClientSessionIds")
            or payload.get("AcceptedClientSessionIds")
            or []
        )
        if not isinstance(accepted, list):
            return []
        return [str(item) for item in accepted]

    def create_time_log(self, device_jwt: str, entry: Mapping[str, Any]) -> Dict[str, Any]:
        response = self.request("POST", "/api/timelogs", body=dict(entry), token=device_jwt)
        return response.json() or {}

    def get_time_logs(
        self,
        token: str,
        limit: Optional[int] = None,
        cursor: Optional[str] = None,
    ) -> Dict[str, Any]:
        response = self.request(
            "GET", "/api/timelogs", token=token, query={"limit": limit, "cursor": cursor}
        )
        return response.json() or {}

    # ------------------------------------------------------------------ #
    # dashboard / analytics
    # ------------------------------------------------------------------ #
    def _get_json(self, path: str, token: str, query: Mapping[str, Any]) -> Any:
        response = self.request("GET", path, token=token, query=query)
        return response.json()

    def dashboard_summary(self, token: str, **query: Any) -> Dict[str, Any]:
        return self._get_json("/api/dashboard/summary", token, query) or {}

    def dashboard_apps(self, token: str, **query: Any) -> List[AppUsage]:
        payload = self._get_json("/api/dashboard/apps", token, query)
        if isinstance(payload, list):
            return [AppUsage.from_payload(item) for item in payload if isinstance(item, dict)]
        return []

    def dashboard_devices(self, token: str, **query: Any) -> List[Dict[str, Any]]:
        payload = self._get_json("/api/dashboard/devices", token, query)
        return payload if isinstance(payload, list) else []

    def dashboard_timeline(self, token: str, **query: Any) -> List[Dict[str, Any]]:
        payload = self._get_json("/api/dashboard/timeline", token, query)
        return payload if isinstance(payload, list) else []

    def analytics(
        self, kind: str, token: str, **query: Any
    ) -> List[DailyUsage]:
        payload = self._get_json(f"/api/analytics/{kind}", token, query)
        if isinstance(payload, list):
            return [DailyUsage.from_payload(item) for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            # Some analytics payloads wrap the buckets in a property.
            for key in ("items", "data", "buckets", "points"):
                if isinstance(payload.get(key), list):
                    return [
                        DailyUsage.from_payload(item)
                        for item in payload[key]
                        if isinstance(item, dict)
                    ]
        return []

    # ------------------------------------------------------------------ #
    def ping(self) -> float:
        """Round-trip time to ``/swagger/v1/swagger.json`` (seconds)."""
        import time

        started = time.monotonic()
        self.request("GET", "/swagger/v1/swagger.json", timeout=self.timeout)
        return time.monotonic() - started


def iso_range(days: Optional[int] = None) -> Dict[str, str]:
    """Build ``from``/``to`` query params for the last ``days`` days (UTC)."""
    from datetime import timedelta

    from .models import to_iso, utcnow

    if not days:
        return {}
    now = utcnow()
    return {"from": to_iso(now - timedelta(days=days)), "to": to_iso(now)}


__all__ = ["ApiClient", "ApiError", "ApiResponse", "iso_range"]
