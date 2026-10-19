"""Install the client as a login service (systemd user unit + XDG autostart)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import APP_NAME, APP_SLUG

UNIT_NAME = f"{APP_SLUG}.service"
AUTOSTART_NAME = f"{APP_SLUG}.desktop"


# --------------------------------------------------------------------------- #
# paths
# --------------------------------------------------------------------------- #
def systemd_unit_dir() -> Path:
    return Path(
        os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    ) / "systemd" / "user"


def systemd_unit_path() -> Path:
    return systemd_unit_dir() / UNIT_NAME


def autostart_dir() -> Path:
    return Path(
        os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    ) / "autostart"


def autostart_path() -> Path:
    return autostart_dir() / AUTOSTART_NAME


# --------------------------------------------------------------------------- #
# command resolution
# --------------------------------------------------------------------------- #
def resolve_exec_command() -> Dict[str, Any]:
    """Figure out how to start the tracker from a service manager.

    Prefers an installed ``cdt`` entry point (next to this interpreter or on
    ``PATH``), then falls back to ``python -m cdt`` with an explicit
    ``PYTHONPATH``.
    """
    candidates = [
        Path(sys.executable).resolve().parent / "cdt",
        shutil.which("cdt") and Path(shutil.which("cdt")),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists() and os.access(candidate, os.X_OK):
            return {"argv": [str(candidate), "start"], "env": {}}

    package_parent = str(Path(__file__).resolve().parent.parent)
    return {
        "argv": [sys.executable, "-m", "cdt", "start"],
        "env": {"PYTHONPATH": package_parent, "PYTHONUNBUFFERED": "1"},
    }


def _unit_contents(exec_argv: List[str], env: Dict[str, str], api_url: str) -> str:
    lines = [
        "[Unit]",
        f"Description={APP_NAME} Linux client - screen time tracking",
        "After=default.target",
        # Only start when a graphical session is actually available (X11 or
        # Wayland) - otherwise the tracker has nothing to observe.
        'ExecCondition=/bin/sh -c \'test -n "${DISPLAY}${WAYLAND_DISPLAY}"\'',
        "",
        "[Service]",
        "Type=simple",
        f"ExecStart={' '.join(exec_argv)}",
        "Restart=on-failure",
        "RestartSec=15",
        "StandardOutput=journal",
        "StandardError=journal",
    ]
    for key, value in env.items():
        lines.append(f"Environment={key}={value}")
    lines.append(f"Environment=CDT_API_URL={api_url}")
    lines.extend(
        [
            "",
            "[Install]",
            "WantedBy=default.target",
            "",
        ]
    )
    return "\n".join(lines)


def _desktop_entry_contents(exec_argv: List[str], env: Dict[str, str]) -> str:
    lines = [
        "[Desktop Entry]",
        "Type=Application",
        f"Name={APP_NAME} Tracker",
        "Comment=Tracks foreground application usage and syncs it to the backend",
        f"Exec=env {' '.join(f'{k}={v}' for k, v in env.items())} "
        f"{' '.join(exec_argv)}".rstrip(),
        "Terminal=false",
        "X-GNOME-Autostart-enabled=true",
        "NoDisplay=true",
        "Categories=Utility;",
    ]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# systemd helpers
# --------------------------------------------------------------------------- #
def _run(command: List[str], timeout: float = 30.0) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout)


def _systemctl(args: List[str]) -> subprocess.CompletedProcess:
    return _run(["systemctl", "--user", *args])


def systemd_available() -> bool:
    if shutil.which("systemctl") is None:
        return False
    try:
        completed = _run(["systemctl", "--user", "is-system-running"], timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode in (0, 1)  # 1 == "degraded", still usable


def install_systemd(
    api_url: str, enable: bool = True, start: bool = True
) -> Dict[str, Any]:
    """Write and enable the systemd user unit.  Returns a status dictionary."""
    if not systemd_available():
        return {
            "ok": False,
            "error": "systemd user services are not available on this machine",
        }

    exec_info = resolve_exec_command()
    unit_path = systemd_unit_path()
    unit_path.parent.mkdir(parents=True, exist_ok=True)
    unit_path.write_text(
        _unit_contents(exec_info["argv"], exec_info["env"], api_url), encoding="utf-8"
    )

    steps: List[str] = [f"wrote {unit_path}"]
    failures: List[str] = []
    _systemctl(["daemon-reload"])
    if enable:
        completed = _systemctl(["enable", UNIT_NAME])
        if completed.returncode == 0:
            steps.append("enabled")
        else:
            failures.append(
                f"enable failed: {(completed.stderr or completed.stdout).strip()}"
            )
    if start:
        completed = _systemctl(["restart", UNIT_NAME])
        if completed.returncode == 0:
            steps.append("started")
        else:
            failures.append(
                f"start failed: {(completed.stderr or completed.stdout).strip()}"
            )
    return {
        "ok": not failures,
        "steps": steps,
        "failures": failures,
        "unit": str(unit_path),
    }


def uninstall_systemd() -> Dict[str, Any]:
    if not systemd_available():
        return {"ok": False, "error": "systemd user services are not available"}
    steps: List[str] = []
    completed = _systemctl(["disable", "--now", UNIT_NAME])
    steps.append(
        "disabled" if completed.returncode == 0 else f"disable failed: {completed.stderr.strip()}"
    )
    unit_path = systemd_unit_path()
    try:
        unit_path.unlink()
        steps.append(f"removed {unit_path}")
    except FileNotFoundError:
        steps.append("unit file was not present")
    _systemctl(["daemon-reload"])
    return {"ok": True, "steps": steps}


def service_status() -> Dict[str, Any]:
    if not systemd_available():
        return {"ok": False, "error": "systemd user services are not available"}
    active = _systemctl(["is-active", UNIT_NAME])
    enabled = _systemctl(["is-enabled", UNIT_NAME])
    return {
        "ok": True,
        "installed": systemd_unit_path().exists(),
        "active": active.stdout.strip(),
        "enabled": enabled.stdout.strip(),
        "unit": str(systemd_unit_path()),
    }


def service_logs(lines: int = 50) -> str:
    if shutil.which("journalctl") is None:
        return "journalctl is not available"
    completed = _run(
        ["journalctl", "--user", "-u", UNIT_NAME, "-n", str(lines), "--no-pager"],
        timeout=20,
    )
    return (completed.stdout or completed.stderr or "").strip()


# --------------------------------------------------------------------------- #
# XDG autostart
# --------------------------------------------------------------------------- #
def install_autostart() -> Dict[str, Any]:
    exec_info = resolve_exec_command()
    path = autostart_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_desktop_entry_contents(exec_info["argv"], exec_info["env"]), encoding="utf-8")
    return {"ok": True, "path": str(path)}


def uninstall_autostart() -> Dict[str, Any]:
    try:
        autostart_path().unlink()
    except FileNotFoundError:
        return {"ok": True, "path": None, "note": "autostart entry was not present"}
    return {"ok": True, "path": str(autostart_path())}


# --------------------------------------------------------------------------- #
# pid file
# --------------------------------------------------------------------------- #
def write_pid_file(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{os.getpid()}\n", encoding="utf-8")


def read_pid_file(path: Path) -> Optional[int]:
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return None


def remove_pid_file(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def process_alive(pid: Optional[int]) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True
