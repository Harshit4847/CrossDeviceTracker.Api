"""Command line interface for the CrossDeviceTracker Linux client.

Every command is safe to run repeatedly and never writes secrets to stdout
unless explicitly asked for with ``--show-token``.
"""

from __future__ import annotations

import argparse
import dataclasses
import getpass
import json
import logging
import os
import signal
import socket
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from . import (
    APP_NAME,
    APP_SLUG,
    COMMAND_NAME,
    USER_AGENT,
    __version__,
)
from .api import ApiClient, ApiError
from .config import AppPaths, ConfigStore, Credentials, Settings
from .idle import open_idle_source
from .models import human_duration, to_iso, utcnow
from .queue import PendingLogQueue
from .service import (
    process_alive,
    read_pid_file,
    remove_pid_file,
    write_pid_file,
)
from .sync import AuthRequiredError, SyncEngine, SyncLoop
from .tracker import TrackerOptions, UsageTracker
from .window import (
    NullWindowSource,
    ScriptedWindowSource,
    WindowInfo,
    describe_environment,
    open_window_source,
)

LOGGER = logging.getLogger("cdt")

# --------------------------------------------------------------------------- #
# output helpers
# --------------------------------------------------------------------------- #


class Palette:
    """ANSI colours, automatically disabled for non-terminals."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def _wrap(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.enabled else text

    def bold(self, text: str) -> str:
        return self._wrap("1", text)

    def dim(self, text: str) -> str:
        return self._wrap("2", text)

    def green(self, text: str) -> str:
        return self._wrap("32", text)

    def red(self, text: str) -> str:
        return self._wrap("31", text)

    def yellow(self, text: str) -> str:
        return self._wrap("33", text)

    def cyan(self, text: str) -> str:
        return self._wrap("36", text)


COLORS = Palette(False)


def emit_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, default=str))


def info(message: str = "") -> None:
    print(message)


def success(message: str) -> None:
    print(COLORS.green(message))


def warn(message: str) -> None:
    print(COLORS.yellow(message))


def error(message: str) -> None:
    print(COLORS.red(message), file=sys.stderr)


def table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    """Render a simple aligned text table."""
    if not rows:
        return "  (no data)"
    strings = [[str(cell) for cell in row] for row in rows]
    widths = [len(str(header)) for header in headers]
    for row in strings:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(cell))
    lines = [
        "  "
        + "  ".join(
            str(header).ljust(widths[index]) for index, header in enumerate(headers)
        ).rstrip()
    ]
    lines.append("  " + "  ".join("-" * width for width in widths))
    for row in strings:
        lines.append(
            "  "
            + "  ".join(
                cell.ljust(widths[index]) for index, cell in enumerate(row)
            ).rstrip()
        )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# context
# --------------------------------------------------------------------------- #


class Context:
    """Everything a command needs: settings, credentials, queue and API."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.json_output = bool(getattr(args, "json", False))
        self.paths = AppPaths(
            config_dir=getattr(args, "config_dir", None),
            data_dir=getattr(args, "data_dir", None),
        )
        self.paths.ensure()
        self.store = ConfigStore(self.paths)
        self.settings = self.store.load_settings()
        if getattr(args, "api_url", None):
            self.settings.api_url = args.api_url.strip().rstrip("/")
        self.credentials = self.store.load_credentials()
        self._queue: Optional[PendingLogQueue] = None

    # -- lazily created resources ------------------------------------------
    @property
    def queue(self) -> PendingLogQueue:
        if self._queue is None:
            self._queue = PendingLogQueue(self.paths.queue_db)
        return self._queue

    def api(self) -> ApiClient:
        return ApiClient(self.settings.api_url, timeout=self.settings.request_timeout_seconds)

    # -- guards -------------------------------------------------------------
    def require_device(self) -> Credentials:
        if not self.credentials.is_linked:
            raise SystemExit(
                "This machine is not linked yet.\n"
                "  1. Sign in to the web dashboard and generate a desktop link token\n"
                "  2. Run:  cdt link --token <TOKEN>\n"
                "  (or run 'cdt link' with your account to pair in one step)"
            )
        return self.credentials

    def require_user(self) -> Credentials:
        if not self.credentials.has_user_session:
            raise SystemExit(
                "No user session. Run 'cdt login' first (needed for dashboard data)."
            )
        return self.credentials

    def close(self) -> None:
        if self._queue is not None:
            self._queue.close()
            self._queue = None


# --------------------------------------------------------------------------- #
# logging
# --------------------------------------------------------------------------- #
def configure_logging(verbosity: int, log_file: Optional[str] = None) -> None:
    level = logging.WARNING
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG

    handlers: List[logging.Handler] = [logging.StreamHandler(sys.stderr)]
    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(path, encoding="utf-8"))

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=handlers,
        force=True,
    )
    LOGGER.setLevel(level)


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def default_device_name() -> str:
    host = socket.gethostname() or "linux-pc"
    session = os.environ.get("XDG_CURRENT_DESKTOP", "")
    suffix = session.split(":")[0] if session else ""
    return f"{host} ({suffix})" if suffix else host


def cmd_link(ctx: Context) -> int:
    """Pair this machine with the account using a one-time link token."""
    args = ctx.args
    api = ctx.api()

    token = (args.token or "").strip()
    user_jwt = ctx.credentials.user_jwt

    if not token:
        if args.email and args.password:
            try:
                payload = api.login(args.email, args.password)
            except ApiError as err:
                error(f"login failed: {err}")
                return 1
            user_jwt = payload.get("accessToken") or payload.get("access_token") or ""
            if not user_jwt:
                error("login succeeded but no access token was returned")
                return 1
        elif not user_jwt:
            token = input("Paste the desktop link token: ").strip()

    if not token and not user_jwt:
        error("a link token (or an account login) is required")
        return 1

    if not token:
        try:
            payload = api.create_link_token(user_jwt)
        except ApiError as err:
            if err.is_auth_error:
                error(
                    f"{err}\nYour saved session expired - run 'cdt login' and try again."
                )
            else:
                error(f"could not create a link token: {err}")
            return 1
        token = payload.get("token") or payload.get("Token") or ""
        expires = payload.get("expiresAt") or payload.get("ExpiresAt") or ""
        if not token:
            error("the backend did not return a link token")
            return 1
        info(COLORS.dim(f"  generated a one-time token (expires {expires})"))

    device_name = (args.name or "").strip() or default_device_name()
    platform = (args.platform or "Linux").strip() or "Linux"

    try:
        result = api.link_device(token, device_name, platform)
    except ApiError as err:
        if err.is_auth_error:
            error(f"{err}\nLink tokens are single-use and expire after ~10 minutes.")
        else:
            error(f"linking failed: {err}")
        return 1

    credentials = ctx.credentials
    credentials.device_id = result.device_id
    credentials.device_jwt = result.device_jwt
    credentials.device_name = device_name
    credentials.linked_at = to_iso(utcnow())
    ctx.store.save_credentials(credentials)
    if device_name and device_name != ctx.settings.device_name:
        ctx.settings.device_name = device_name
        ctx.store.save_settings(ctx.settings)

    if ctx.json_output:
        emit_json(
            {
                "linked": True,
                "deviceId": result.device_id,
                "deviceName": device_name,
                "platform": platform,
            }
        )
        return 0

    success(f"Linked as device '{device_name}' ({platform})")
    info(f"  device id : {result.device_id}")
    info(COLORS.dim(f"  credentials: {ctx.paths.credentials_file}"))
    info()
    info("Next steps:")
    info(f"  {COMMAND_NAME} doctor                 # check the environment")
    info(f"  {COMMAND_NAME} start                  # track in the foreground")
    info(f"  {COMMAND_NAME} service install        # run at every login")
    return 0


def cmd_login(ctx: Context) -> int:
    """Store a user JWT so dashboard/report commands work."""
    args = ctx.args
    email = (args.email or "").strip()
    if not email:
        email = input("Email: ").strip()
    password = args.password
    if not password:
        password = getpass.getpass("Password: ")

    if not email or not password:
        error("email and password are required")
        return 1

    try:
        payload = ctx.api().login(email, password)
    except ApiError as err:
        error(f"login failed: {err}")
        return 1

    token = payload.get("accessToken") or payload.get("access_token") or ""
    if not token:
        error("the backend did not return an access token")
        return 1

    credentials = ctx.credentials
    credentials.user_jwt = token
    credentials.user_email = payload.get("email") or email
    ctx.store.save_credentials(credentials)

    if ctx.json_output:
        emit_json({"loggedIn": True, "email": credentials.user_email})
        return 0
    success(f"Signed in as {credentials.user_email}")
    info(COLORS.dim("  the user token is only used for reporting commands"))
    return 0


def cmd_logout(ctx: Context) -> int:
    ctx.credentials.user_jwt = ""
    ctx.credentials.user_email = ""
    ctx.store.save_credentials(ctx.credentials)
    success("User session cleared (device link kept)")
    return 0


def cmd_start(ctx: Context) -> int:
    """Run the tracker in the foreground."""
    args = ctx.args
    ctx.require_device()
    settings = ctx.settings
    if args.api_url:
        settings.api_url = args.api_url.strip().rstrip("/")

    # ---------------------------------------------------------------- sources
    if args.dry_run:
        window_source = ScriptedWindowSource(
            [
                WindowInfo("google-chrome", "Google Chrome", "Inbox - Gmail", 1001, "scripted"),
                WindowInfo("code", "Visual Studio Code", "cli.py - cdt", 1002, "scripted"),
                WindowInfo("org.gnome.Terminal", "Terminal", "~/projects", 1003, "scripted"),
                None,
            ],
            hold=4,
        )
        idle_source = open_idle_source("none")
    else:
        try:
            window_source = open_window_source(
                args.window_source or settings.window_source,
                settings.external_window_command,
            )
        except OSError as err:
            error(f"cannot start the tracker: {err}")
            error("Run 'cdt doctor' for diagnostics, or pick a source with --window-source.")
            return 1
        idle_source = open_idle_source(args.idle_source or settings.idle_source)

    if isinstance(window_source, NullWindowSource) and not args.dry_run:
        warn("window source is disabled - nothing will be tracked")

    queue = ctx.queue

    # ---------------------------------------------------------------- syncing
    engine: Optional[SyncEngine] = None
    sync_loop: Optional[SyncLoop] = None
    if not args.no_sync:
        engine = SyncEngine(
            api=ctx.api(),
            queue=queue,
            token_provider=lambda: ctx.credentials.device_jwt,
            batch_size=settings.batch_size,
            retry_base_seconds=settings.retry_base_seconds,
            retry_max_seconds=settings.retry_max_seconds,
        )
        sync_loop = SyncLoop(
            engine,
            interval_seconds=settings.sync_interval_seconds,
            on_result=lambda result: LOGGER.debug(
                "sync: %s", result.as_dict()
            ),
        )
        sync_loop.start()
        initial = sync_loop.sync_now()
        if initial.auth_error:
            warn("the backend rejected this device token - re-link with 'cdt link'")
        elif initial.sent:
            info(
                COLORS.dim(
                    f"  flushed {initial.accepted} queued session(s) from previous runs"
                )
            )

    options = TrackerOptions(
        poll_interval_seconds=args.poll or settings.poll_interval_seconds,
        idle_threshold_seconds=args.idle_threshold or settings.idle_threshold_seconds,
        min_session_seconds=args.min_session or settings.min_session_seconds,
        max_session_seconds=args.max_session or settings.max_session_seconds,
        gap_threshold_seconds=args.gap_threshold or settings.gap_threshold_seconds,
        include_apps=settings.include_apps,
        exclude_apps=settings.exclude_apps,
    )

    tracker = UsageTracker(
        window_source=window_source,
        idle_source=idle_source,
        queue=queue,
        options=options,
    )

    pid_path: Optional[Path] = None
    if not args.no_pid_file:
        pid_path = ctx.paths.pid_file
        write_pid_file(pid_path)

    if ctx.json_output:
        emit_json({"status": "starting", "pid": os.getpid()})

    info(
        COLORS.bold(
            f"{APP_NAME} tracker - device '{ctx.credentials.device_name or ctx.credentials.device_id}'"
        )
    )
    info(
        COLORS.dim(
            f"  window={window_source.name} idle={idle_source.name} "
            f"poll={options.poll_interval_seconds:.2f}s "
            f"idle>{options.idle_threshold_seconds}s "
            f"backend={settings.api_url}"
        )
    )
    if args.dry_run:
        warn("  dry-run: fake window data, nothing is uploaded")
    info(COLORS.dim("  press Ctrl+C to stop"))

    exit_code = 0
    try:
        tracker.run(duration=args.duration)
    except KeyboardInterrupt:  # pragma: no cover - handled by the signal handler
        pass
    except Exception as err:  # pragma: no cover - defensive
        LOGGER.exception("tracker crashed: %s", err)
        error(f"tracker stopped unexpectedly: {err}")
        exit_code = 1
    finally:
        if sync_loop is not None:
            sync_loop.stop()
            final = sync_loop.sync_now()
            if final.auth_error:
                warn("device token rejected - run 'cdt link' to re-link")
            elif final.accepted:
                info(f"  final sync uploaded {final.accepted} session(s)")
        window_source.close()
        idle_source.close()
        queue_stats = queue.stats()
        queue.close()
        ctx._queue = None
        if pid_path is not None:
            remove_pid_file(pid_path)

    if ctx.json_output:
        emit_json(
            {
                "status": "stopped",
                "stats": tracker.stats.as_dict(),
                "queue": queue_stats,
            }
        )
    else:
        stats = tracker.stats
        info()
        info(
            f"  polls: {stats.polls}   sessions queued: {stats.sessions_created}   "
            f"idle periods: {stats.idle_periods}"
        )
        pending = queue_stats["pending"]
        if pending:
            warn(f"  {pending} session(s) still queued - they upload on the next run")
        success("Tracker stopped.")
    return exit_code


def cmd_sync(ctx: Context) -> int:
    """Flush the local queue right now."""
    ctx.require_device()
    engine = SyncEngine(
        api=ctx.api(),
        queue=ctx.queue,
        token_provider=lambda: ctx.credentials.device_jwt,
        batch_size=ctx.settings.batch_size,
        retry_base_seconds=ctx.settings.retry_base_seconds,
        retry_max_seconds=ctx.settings.retry_max_seconds,
    )
    result = engine.sync_once()
    if ctx.json_output:
        emit_json(result.as_dict())
        return 0 if not result.auth_error else 2
    if result.auth_error:
        error(f"the backend rejected the device token: {result.error}")
        info("Re-link this machine with 'cdt link'.")
        return 2
    if result.sent == 0:
        info("Nothing to sync - the queue is empty.")
        return 0
    if result.error and result.retried:
        warn(f"upload failed ({result.error}); {result.retried} session(s) will be retried")
        return 1
    success(
        f"Uploaded {result.accepted} session(s)"
        + (f", dropped {result.dropped}" if result.dropped else "")
    )
    return 0


def cmd_queue(ctx: Context) -> int:
    """Inspect (or clear) the offline queue."""
    if ctx.args.clear:
        removed = ctx.queue.clear()
        success(f"Cleared {removed} queued session(s).")
        return 0

    stats = ctx.queue.stats()
    if ctx.json_output:
        emit_json({**stats, "entries": [dataclasses.asdict(entry) for entry in ctx.queue.peek()]})
        return 0

    info("Offline queue")
    info(f"  pending      : {stats['pending']} session(s) "
         f"({human_duration(stats['pendingSeconds'])})")
    info(f"  failing      : {stats['failing']}")
    info(f"  dead letters : {stats['deadLetters']}")
    info(f"  last sync    : {stats['lastSyncAt'] or 'never'}")

    entries = ctx.queue.peek(limit=10)
    if entries:
        info("")
        info(
            table(
                ["app", "duration", "start (UTC)", "attempts"],
                [
                    [
                        entry.app_name or entry.package_name,
                        human_duration(entry.duration_seconds),
                        entry.start_time_utc.replace("T", " ").replace("Z", ""),
                        entry.attempts,
                    ]
                    for entry in entries
                ],
            )
        )
    dead = ctx.queue.dead_letters(limit=5)
    if dead:
        info("")
        info(COLORS.dim("  dead letters (rejected by the backend):"))
        for entry in dead:
            info(
                COLORS.dim(
                    f"    {entry['app_name'] or entry['package_name']} "
                    f"({entry['reason']})"
                )
            )
    return 0


def _require_reachable(ctx: Context) -> ApiClient:
    api = ctx.api()
    try:
        api.ping()
    except ApiError as err:
        raise SystemExit(
            f"cannot reach the backend at {ctx.settings.api_url} ({err}).\n"
            "Start the API or point the client elsewhere with --api-url."
        )
    return api


def cmd_status(ctx: Context) -> int:
    """Show local tracker state plus today's screen time from the backend."""
    args = ctx.args
    local: Dict[str, Any] = {}
    if not args.remote:
        pid = read_pid_file(ctx.paths.pid_file)
        local = {
            "running": process_alive(pid),
            "pid": pid,
            "queue": ctx.queue.stats(),
            "linked": ctx.credentials.is_linked,
            "deviceId": ctx.credentials.device_id,
            "deviceName": ctx.credentials.device_name,
            "paths": ctx.paths.describe(),
        }

    remote: Dict[str, Any] = {}
    remote_error: Optional[str] = None
    if not args.local and ctx.credentials.has_user_session:
        api = ctx.api()
        try:
            remote = api.dashboard_summary(ctx.credentials.user_jwt)
        except ApiError as err:
            remote_error = str(err)
    elif not args.local:
        remote_error = "not signed in (run 'cdt login' to see backend data)"

    if ctx.json_output:
        emit_json({"local": local, "remote": remote, "remoteError": remote_error})
        return 0

    info(COLORS.bold(f"{APP_NAME} status"))
    info(f"  backend     : {ctx.settings.api_url}")
    if ctx.credentials.is_linked:
        info(
            f"  device      : {ctx.credentials.device_name or 'unnamed'} "
            f"({ctx.credentials.device_id})"
        )
    else:
        warn("  device      : not linked (run 'cdt link')")
    if ctx.credentials.user_email:
        info(f"  account     : {ctx.credentials.user_email}")

    if local:
        state = (
            COLORS.green(f"running (pid {local['pid']})")
            if local["running"]
            else COLORS.dim("not running")
        )
        info(f"  tracker     : {state}")
        queue_stats = local["queue"]
        info(
            f"  queue       : {queue_stats['pending']} pending, "
            f"{queue_stats['failing']} failing, "
            f"{queue_stats['deadLetters']} dead letter(s)"
        )

    if remote:
        today = remote.get("today") or {}
        yesterday = remote.get("yesterday") or {}
        week = remote.get("thisWeek") or {}
        month = remote.get("thisMonth") or {}
        info("")
        info(
            f"  today       : {COLORS.bold(human_duration(today.get('totalScreenTimeSeconds', 0)))}"
            f"  ({today.get('sessionCount', 0)} sessions, "
            f"{remote.get('appCount', 0)} apps)"
        )
        info(
            f"  yesterday   : {human_duration(yesterday.get('totalScreenTimeSeconds', 0))}"
        )
        info(
            f"  this week   : {human_duration(week.get('totalScreenTimeSeconds', 0))}"
        )
        info(
            f"  this month  : {human_duration(month.get('totalScreenTimeSeconds', 0))}"
        )
        most_used = remote.get("mostUsedApp")
        if most_used:
            info(
                f"  most used   : {most_used.get('appName')} "
                f"({human_duration(most_used.get('durationSeconds', 0))})"
            )
        info(f"  devices     : {remote.get('deviceCount', 0)}")
    elif remote_error:
        info("")
        warn(f"  backend data unavailable: {remote_error}")
    return 0


def cmd_apps(ctx: Context) -> int:
    """Per-app usage breakdown from the dashboard API."""
    ctx.require_user()
    api = ctx.api()
    query: Dict[str, Any] = _days_query(ctx.args.days) if ctx.args.days else {}
    if ctx.args.device_id:
        query["deviceId"] = ctx.args.device_id
    if ctx.args.platform:
        query["platform"] = ctx.args.platform

    try:
        usage = api.dashboard_apps(ctx.credentials.user_jwt, **query)
    except ApiError as err:
        if err.is_auth_error:
            error(f"{err}\nRun 'cdt login' again - the user token expired.")
            return 2
        error(f"request failed: {err}")
        return 1

    if ctx.json_output:
        emit_json([dataclasses.asdict(item) for item in usage])
        return 0
    if not usage:
        info("No usage recorded for that period.")
        return 0

    scope = f"last {ctx.args.days} day(s)" if ctx.args.days else "all time"
    info(COLORS.bold(f"App usage - {scope}"))
    info(
        table(
            ["app", "time", "share", "sessions"],
            [
                [
                    item.app_name,
                    human_duration(item.duration_seconds),
                    f"{item.percentage:5.1f}%",
                    item.session_count,
                ]
                for item in usage
            ],
        )
    )
    return 0


def _days_query(days: int) -> Dict[str, str]:
    from datetime import timedelta

    now = utcnow()
    return {"from": to_iso(now - timedelta(days=days)), "to": to_iso(now)}


def cmd_devices(ctx: Context) -> int:
    """Per-device usage breakdown."""
    ctx.require_user()
    query = _days_query(ctx.args.days) if ctx.args.days else {}
    try:
        devices = ctx.api().dashboard_devices(ctx.credentials.user_jwt, **query)
    except ApiError as err:
        if err.is_auth_error:
            error(f"{err}\nRun 'cdt login' again - the user token expired.")
            return 2
        error(f"request failed: {err}")
        return 1

    if ctx.json_output:
        emit_json(devices)
        return 0
    if not devices:
        info("No device usage recorded for that period.")
        return 0

    def pick(payload: Dict[str, Any], *names: str, default: Any = "") -> Any:
        for name in names:
            if payload.get(name) is not None:
                return payload[name]
        return default

    info(COLORS.bold(f"Device usage - last {ctx.args.days} day(s)" if ctx.args.days else "Device usage"))
    info(
        table(
            ["device", "platform", "time", "sessions", "last sync"],
            [
                [
                    pick(item, "deviceName", "device_name", default="?"),
                    pick(item, "platform", default="?"),
                    human_duration(int(pick(item, "durationSeconds", "totalSeconds", default=0) or 0)),
                    pick(item, "sessionCount", "sessions", default=0),
                    str(pick(item, "lastDataSyncAt", "lastSyncAt", default="-"))[:19],
                ]
                for item in devices
            ],
        )
    )
    return 0


def cmd_timeline(ctx: Context) -> int:
    """Chronological list of recent sessions."""
    ctx.require_user()
    query = _days_query(ctx.args.days) if ctx.args.days else {}
    try:
        timeline = ctx.api().dashboard_timeline(ctx.credentials.user_jwt, **query)
    except ApiError as err:
        if err.is_auth_error:
            error(f"{err}\nRun 'cdt login' again - the user token expired.")
            return 2
        error(f"request failed: {err}")
        return 1

    if ctx.json_output:
        emit_json(timeline)
        return 0
    if not timeline:
        info("No sessions recorded for that period.")
        return 0

    info(COLORS.bold(f"Timeline - last {ctx.args.days} day(s)" if ctx.args.days else "Timeline"))
    rows = []
    for item in timeline[-ctx.args.limit:]:
        start = str(item.get("startTime") or item.get("start") or "")[:19].replace("T", " ")
        rows.append(
            [
                start,
                item.get("appName") or item.get("app") or "?",
                human_duration(int(item.get("durationSeconds") or 0)),
                item.get("deviceName") or item.get("device") or "",
            ]
        )
    info(table(["start (UTC)", "app", "duration", "device"], rows))
    return 0


def cmd_analytics(ctx: Context) -> int:
    """Chart-ready aggregates (daily / weekly / monthly / hourly)."""
    ctx.require_user()
    kind = ctx.args.kind
    query = _days_query(ctx.args.days) if ctx.args.days else {}
    try:
        buckets = ctx.api().analytics(kind, ctx.credentials.user_jwt, **query)
    except ApiError as err:
        if err.is_auth_error:
            error(f"{err}\nRun 'cdt login' again - the user token expired.")
            return 2
        error(f"request failed: {err}")
        return 1

    if ctx.json_output:
        emit_json([dataclasses.asdict(bucket) for bucket in buckets])
        return 0
    if not buckets:
        info(f"No {kind} data available.")
        return 0

    info(COLORS.bold(f"{kind.capitalize()} usage"))
    info(
        table(
            [kind.rstrip("ly") if kind.endswith("ly") else kind, "time", "sessions"],
            [
                [
                    bucket.label,
                    human_duration(bucket.duration_seconds),
                    bucket.session_count or "-",
                ]
                for bucket in buckets
            ],
        )
    )
    return 0


def cmd_logs(ctx: Context) -> int:
    """Raw time logs (works with either the device or the user token)."""
    token = ctx.credentials.device_jwt or ctx.credentials.user_jwt
    if not token:
        raise SystemExit("Not linked and not signed in - nothing to query with.")
    try:
        payload = ctx.api().get_time_logs(
            token, limit=ctx.args.limit, cursor=ctx.args.cursor
        )
    except ApiError as err:
        error(f"request failed: {err}")
        return 1

    if ctx.json_output:
        emit_json(payload)
        return 0

    items = payload.get("items") or []
    if not items:
        info("No time logs found.")
        return 0
    info(COLORS.bold(f"Latest {len(items)} time log(s)"))
    info(
        table(
            ["start (UTC)", "app", "duration", "device"],
            [
                [
                    str(item.get("startTime") or "")[:19].replace("T", " "),
                    item.get("appName") or "?",
                    human_duration(int(item.get("durationSeconds") or 0)),
                    str(item.get("deviceId") or "")[:8],
                ]
                for item in items
            ],
        )
    )
    if payload.get("hasMore"):
        info(COLORS.dim(f"  more available, next cursor: {payload.get('nextCursor')}"))
    return 0


def cmd_account(ctx: Context) -> int:
    """Show the signed-in account and every registered device."""
    ctx.require_user()
    try:
        devices = ctx.api().list_devices(ctx.credentials.user_jwt)
    except ApiError as err:
        if err.is_auth_error:
            error(f"{err}\nRun 'cdt login' again - the user token expired.")
            return 2
        error(f"request failed: {err}")
        return 1

    if ctx.json_output:
        emit_json(
            {
                "email": ctx.credentials.user_email,
                "devices": [dataclasses.asdict(device) for device in devices],
            }
        )
        return 0

    info(COLORS.bold("Account"))
    info(f"  email    : {ctx.credentials.user_email or '?'}")
    info(f"  this pc  : {ctx.credentials.device_id or 'not linked'}")
    info("")
    if devices:
        info(table(
            ["device", "platform", "installation", "revoked", "last sync"],
            [
                [
                    device.device_name,
                    device.platform,
                    (device.installation_id or "-")[:12],
                    "yes" if device.is_revoked else "no",
                    str(device.last_data_sync_at or "-")[:19].replace("T", " "),
                ]
                for device in devices
            ],
        ))
    else:
        info("  no devices registered yet")
    return 0


def cmd_config(ctx: Context) -> int:
    """Show or update the client configuration."""
    args = ctx.args
    if args.set:
        updates: Dict[str, Any] = {}
        for assignment in args.set:
            if "=" not in assignment:
                error(f"expected key=value, got '{assignment}'")
                return 1
            key, _, value = assignment.partition("=")
            key = key.strip()
            if key not in Settings.__dataclass_fields__:
                error(f"unknown setting '{key}'")
                info(f"available: {', '.join(Settings.__dataclass_fields__)}")
                return 1
            updates[key] = _coerce(key, value)
        data = ctx.settings.to_dict()
        data.update(updates)
        ctx.settings = Settings.from_dict(data)
        ctx.store.save_settings(ctx.settings)
        success(f"Updated {len(updates)} setting(s) in {ctx.paths.config_file}")

    if args.get:
        if args.get not in Settings.__dataclass_fields__:
            error(f"unknown setting '{args.get}'")
            return 1
        value = getattr(ctx.settings, args.get)
        if ctx.json_output:
            emit_json({args.get: value})
        else:
            info(str(value))
        return 0

    if ctx.json_output:
        emit_json(ctx.settings.to_dict())
        return 0

    info(COLORS.bold(f"Configuration ({ctx.paths.config_file})"))
    for key, value in ctx.settings.to_dict().items():
        info(f"  {key:<28} {value}")
    info("")
    info(COLORS.dim("  change with: cdt config --set api_url=http://my-server:5148"))
    return 0


def _coerce(key: str, value: str) -> Any:
    """Turn a CLI string into the type declared on ``Settings``."""
    field = Settings.__dataclass_fields__[key]
    text = value.strip()
    if field.type in (int, "int"):
        return int(float(text))
    if field.type in (float, "float"):
        return float(text)
    if field.type in (bool, "bool"):
        return text.lower() in ("1", "true", "yes", "on")
    if "List" in str(field.type):
        return [item.strip() for item in text.split(",") if item.strip()]
    return text


def cmd_doctor(ctx: Context) -> int:
    """Environment and connectivity diagnostics."""
    environment = describe_environment()
    problems: List[str] = []
    notes: List[str] = []

    api = ctx.api()
    reachable = None
    latency = None
    try:
        latency = api.ping()
        reachable = True
    except ApiError as err:
        reachable = False
        problems.append(f"backend unreachable: {err}")

    if not ctx.credentials.is_linked:
        notes.append("device is not linked - run 'cdt link'")

    window_source = None
    window_error = None
    try:
        window_source = open_window_source(
            ctx.args.window_source or ctx.settings.window_source,
            ctx.settings.external_window_command,
        )
    except OSError as err:
        window_error = str(err)
        problems.append(f"no active-window source: {err}")
    idle_source = open_idle_source(ctx.args.idle_source or ctx.settings.idle_source)

    queue_stats = ctx.queue.stats()

    if ctx.json_output:
        emit_json(
            {
                "version": __version__,
                "python": sys.version.split()[0],
                "environment": environment,
                "backend": {
                    "url": ctx.settings.api_url,
                    "reachable": reachable,
                    "latencySeconds": latency,
                },
                "windowSource": window_source.name if window_source else None,
                "windowError": window_error,
                "idleSource": idle_source.name,
                "queue": queue_stats,
                "problems": problems,
                "notes": notes,
            }
        )
        if window_source:
            window_source.close()
        idle_source.close()
        return 0 if not problems else 1

    info(COLORS.bold(f"{APP_NAME} doctor"))
    info(f"  version      : {__version__} (python {sys.version.split()[0]})")
    info(f"  backend      : {ctx.settings.api_url}")
    if reachable:
        success(f"  reachable    : yes ({latency * 1000:.0f} ms)")
    else:
        error("  reachable    : no")
    info(f"  session      : {environment['session']} "
         f"(DISPLAY={environment['display'] or '-'}, "
         f"WAYLAND_DISPLAY={environment['waylandDisplay'] or '-'})")
    info(f"  window source: {window_source.name if window_source else 'none'}"
         + (f" - {window_error}" if window_error else ""))
    info(f"  idle source  : {idle_source.name}")
    info(f"  sources      : {', '.join(environment['availableSources']) or 'none detected'}")
    tools = ", ".join(name for name, present in environment["tools"].items() if present)
    info(f"  tools        : {tools or 'none'}")
    info(f"  queue        : {queue_stats['pending']} pending, "
         f"{queue_stats['failing']} failing, {queue_stats['deadLetters']} dead letter(s)")
    info(f"  linked       : {'yes' if ctx.credentials.is_linked else 'no'}")

    if window_source:
        try:
            window = window_source.get_active_window()
        except Exception as err:  # pragma: no cover - defensive
            window = None
            problems.append(f"window query failed: {err}")
        if window:
            info(f"  active window: {window.describe()} [{window.app_id}]")
        elif window_source.name != "none":
            info(f"  active window: (nothing detected)")

    if problems:
        info("")
        for problem in problems:
            error(f"  ! {problem}")
    for note in notes + environment["notes"]:
        warn(f"  * {note}")
    if not problems and not notes:
        success("Everything looks good.")

    if window_source:
        window_source.close()
    idle_source.close()
    return 0 if not problems else 1


def cmd_service(ctx: Context) -> int:
    """Install / remove / inspect the login service."""
    from . import service as service_module

    action = ctx.args.action
    if action == "install":
        result = service_module.install_systemd(ctx.settings.api_url)
        if not result.get("ok"):
            error(result.get("error", "installation failed"))
            info("Alternative: 'cdt service autostart' (XDG autostart entry)")
            return 1
        for step in result["steps"]:
            info(f"  {step}")
        for failure in result.get("failures", []):
            warn(f"  {failure}")
        if result.get("failures"):
            warn("The unit was written but systemd could not start it.")
            info("Check with:  cdt service status   /   journalctl --user -u "
                 f"{APP_SLUG}.service")
            info("Fallback:    cdt service autostart")
            return 1
        success("Service installed - the tracker now starts at login.")
        info(COLORS.dim(f"  logs: journalctl --user -u {APP_SLUG}.service -f"))
        return 0

    if action == "uninstall":
        result = service_module.uninstall_systemd()
        for step in result.get("steps", []):
            info(f"  {step}")
        success("Service removed.")
        return 0

    if action == "status":
        status = service_module.service_status()
        if not status.get("ok"):
            error(status.get("error", "systemd unavailable"))
            return 1
        if ctx.json_output:
            emit_json(status)
            return 0
        info(f"  installed : {'yes' if status['installed'] else 'no'}")
        info(f"  active    : {status['active']}")
        info(f"  enabled   : {status['enabled']}")
        info(f"  unit      : {status['unit']}")
        return 0

    if action == "logs":
        info(service_module.service_logs(ctx.args.lines))
        return 0

    if action == "autostart":
        result = service_module.install_autostart()
        success(f"XDG autostart entry written to {result['path']}")
        info("It will start the tracker the next time you log in.")
        return 0

    if action == "autostart-remove":
        service_module.uninstall_autostart()
        success("XDG autostart entry removed.")
        return 0

    error(f"unknown service action '{action}'")
    return 1


def cmd_stop(ctx: Context) -> int:
    """Stop a tracker started with ``cdt start`` (pid file based)."""
    pid = read_pid_file(ctx.paths.pid_file)
    if not pid:
        info("No pid file found - the tracker is not running.")
        return 0
    if not process_alive(pid):
        info(f"Tracker (pid {pid}) is not running any more.")
        remove_pid_file(ctx.paths.pid_file)
        return 0
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as err:
        error(f"could not stop pid {pid}: {err}")
        return 1
    for _ in range(50):
        if not process_alive(pid):
            break
        time.sleep(0.2)
    remove_pid_file(ctx.paths.pid_file)
    success(f"Stop signal sent to the tracker (pid {pid}).")
    return 0


def cmd_version(ctx: Context) -> int:
    if ctx.json_output:
        emit_json({"name": APP_SLUG, "version": __version__, "userAgent": USER_AGENT})
        return 0
    info(f"{COMMAND_NAME} {__version__} ({APP_NAME} Linux client)")
    info(f"python {sys.version.split()[0]} - {USER_AGENT}")
    return 0


# --------------------------------------------------------------------------- #
# argument parsing
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=COMMAND_NAME,
        description=(
            "Linux desktop client for CrossDeviceTracker.Api - tracks foreground "
            "application usage and syncs it to your account."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            "  cdt link --token 3fZ...                pair this machine\n"
            "  cdt start                              track in the foreground\n"
            "  cdt service install                    start automatically at login\n"
            "  cdt status                             today's screen time\n"
            "  cdt apps --days 7                      per-app breakdown\n"
            "  cdt doctor                             diagnostics\n"
        ),
    )
    parser.add_argument("--version", action="version", version=f"cdt {__version__}")
    parser.add_argument("--api-url", help="override the backend URL")
    parser.add_argument("--config-dir", type=Path, help="override the config directory")
    parser.add_argument("--data-dir", type=Path, help="override the data directory")
    parser.add_argument("--json", action="store_true", help="machine readable output")
    parser.add_argument(
        "-v", "--verbose", action="count", default=0, help="more logging (-vv for debug)"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    def add(name: str, help_text: str, handler: Any) -> argparse.ArgumentParser:
        sub = subparsers.add_parser(name, help=help_text, description=help_text)
        sub.set_defaults(handler=handler)
        return sub

    # link ------------------------------------------------------------------
    link = add("link", "Pair this machine with your account", cmd_link)
    link.add_argument("--token", help="one-time desktop link token from the dashboard")
    link.add_argument("--email", help="account email (generates a token automatically)")
    link.add_argument("--password", help="account password (use with --email)")
    link.add_argument("--name", help=f"device name (default: {default_device_name()})")
    link.add_argument("--platform", default="Linux", help="platform label (default: Linux)")

    # login -----------------------------------------------------------------
    login = add("login", "Sign in for dashboard/report commands", cmd_login)
    login.add_argument("--email")
    login.add_argument("--password")

    add("logout", "Clear the saved user session", cmd_logout)

    # start -----------------------------------------------------------------
    start = add("start", "Track foreground usage (foreground process)", cmd_start)
    start.add_argument("--duration", type=float, help="stop after N seconds (testing)")
    start.add_argument("--window-source", help="auto | x11 | xprop | sway | hyprland | external | none")
    start.add_argument("--idle-source", help="auto | xss | xprintidle | mutter | none")
    start.add_argument("--poll", type=float, help="poll interval in seconds")
    start.add_argument("--idle-threshold", type=int, help="idle seconds before a session ends")
    start.add_argument("--min-session", type=int, help="minimum session length in seconds")
    start.add_argument("--max-session", type=int, help="flush a running app after N seconds")
    start.add_argument(
        "--gap-threshold", type=float, help="seconds between polls that count as suspend time"
    )
    start.add_argument("--no-sync", action="store_true", help="track locally only")
    start.add_argument("--no-pid-file", action="store_true", help="do not write the pid file")
    start.add_argument("--dry-run", action="store_true", help="fake data, no upload")
    start.add_argument("--log-file", help="also append logs to this file")

    add("sync", "Upload queued sessions now", cmd_sync)

    queue = add("queue", "Inspect the offline queue", cmd_queue)
    queue.add_argument("--clear", action="store_true", help="drop every queued session")

    status = add("status", "Local tracker state + today's screen time", cmd_status)
    status.add_argument("--local", action="store_true", help="skip backend calls")
    status.add_argument("--remote", action="store_true", help="skip local checks")

    apps = add("apps", "Per-app usage breakdown", cmd_apps)
    apps.add_argument("--days", type=int, help="limit to the last N days")
    apps.add_argument("--device-id", help="filter by device id")
    apps.add_argument("--platform", help="filter by platform (Linux, Windows, Android)")

    devices = add("devices", "Per-device usage breakdown", cmd_devices)
    devices.add_argument("--days", type=int, help="limit to the last N days")

    timeline = add("timeline", "Recent usage sessions", cmd_timeline)
    timeline.add_argument("--days", type=int, help="limit to the last N days")
    timeline.add_argument("--limit", type=int, default=25, help="rows to show")

    analytics = add("analytics", "Chart data (daily/weekly/monthly/hourly)", cmd_analytics)
    analytics.add_argument("kind", choices=["daily", "weekly", "monthly", "hourly"])
    analytics.add_argument("--days", type=int, help="limit to the last N days")

    logs = add("logs", "Raw time log entries", cmd_logs)
    logs.add_argument("--limit", type=int, default=20, help="page size (max 50)")
    logs.add_argument("--cursor", help="pagination cursor (ISO timestamp)")

    add("account", "Signed-in account and registered devices", cmd_account)

    config = add("config", "Show or change settings", cmd_config)
    config.add_argument("--set", action="append", help="key=value (repeatable)")
    config.add_argument("--get", help="print a single setting")

    doctor = add("doctor", "Diagnose the environment", cmd_doctor)
    doctor.add_argument("--window-source")
    doctor.add_argument("--idle-source")

    service = add("service", "Manage the login service", cmd_service)
    service.add_argument(
        "action",
        choices=["install", "uninstall", "status", "logs", "autostart", "autostart-remove"],
    )
    service.add_argument("--lines", type=int, default=50, help="log lines for 'service logs'")

    add("stop", "Stop a running tracker (pid file)", cmd_stop)

    add("version", "Print version information", cmd_version)

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    global COLORS

    parser = build_parser()
    args = parser.parse_args(argv)

    COLORS = Palette(
        enabled=sys.stdout.isatty() and not os.environ.get("NO_COLOR") and not args.json
    )
    configure_logging(args.verbose, getattr(args, "log_file", None))

    ctx = Context(args)
    handler = getattr(args, "handler", None)
    if handler is None:  # pragma: no cover - argparse enforces this
        parser.print_help()
        return 1

    try:
        return int(handler(ctx) or 0)
    except AuthRequiredError as err:
        error(str(err))
        return 2
    except ApiError as err:
        error(f"backend error: {err}")
        return 1
    except KeyboardInterrupt:
        info("interrupted")
        return 130
    except SystemExit as exit_request:  # guard clauses (e.g. "not linked")
        message = exit_request.code
        if isinstance(message, str) and message.strip():
            error(message)
        return int(exit_request.code) if isinstance(exit_request.code, int) else 1
    finally:
        ctx.close()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
