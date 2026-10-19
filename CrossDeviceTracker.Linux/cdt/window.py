"""Active window detection.

Four back-ends are implemented so the client works on practically every Linux
desktop:

``x11``
    Direct ``libX11`` access through :mod:`ctypes` (no external tools needed).
``xprop``
    Fallback that shells out to ``xprop`` from ``x11-utils``.
``sway``
    ``swaymsg -t get_tree`` on Sway/wlroots compositors.
``hyprland``
    ``hyprctl -j activewindow`` on Hyprland.
``external``
    Any user supplied command emitting ``{"app_id": ..., "app_name": ...}``.

GNOME on Wayland does not expose the focused window to clients, so the client
detects that situation and reports it through ``cdt doctor`` instead of
silently uploading bogus data.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import json
import os
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .apps import prettify_app_name
from .models import WindowInfo

# X11 constants ---------------------------------------------------------------
_SUCCESS = 0
_ANY_PROPERTY_TYPE = 0
_XA_ATOM = 4
_XA_STRING = 31


def _load_library(candidates: Sequence[str]) -> Optional[ctypes.CDLL]:
    for candidate in candidates:
        try:
            return ctypes.CDLL(candidate)
        except OSError:
            continue
    return None


def _decode(raw: Optional[bytes]) -> str:
    if not raw:
        return ""
    return raw.decode("utf-8", "replace").strip("\x00").strip()


class WindowSource(ABC):
    """Where the foreground application comes from."""

    name = "abstract"
    kind = "abstract"
    label = "abstract"

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def get_active_window(self) -> Optional[WindowInfo]: ...

    def close(self) -> None:  # pragma: no cover - default no-op
        """Release any native resources."""

    def __enter__(self) -> "WindowSource":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()


# --------------------------------------------------------------------------- #
# X11 through libX11
# --------------------------------------------------------------------------- #


class X11WindowSource(WindowSource):
    """Active window via ``libX11`` (works on any X11 session)."""

    name = "x11"
    kind = "x11"
    label = "X11 (libX11)"

    _NET_ACTIVE_WINDOW = b"_NET_ACTIVE_WINDOW"
    _NET_WM_PID = b"_NET_WM_PID"
    _NET_WM_NAME = b"_NET_WM_NAME"
    _UTF8_STRING = b"UTF8_STRING"
    WM_CLASS = b"WM_CLASS"
    WM_NAME = b"WM_NAME"

    def __init__(self) -> None:
        library = _load_library(["libX11.so.6", "libX11.so"])
        if library is None:
            raise OSError("libX11 is not installed")
        self._lib = library
        self._configure_prototypes()
        display = self._lib.XOpenDisplay(None)
        if not display:
            raise OSError("cannot open the X display (is DISPLAY set?)")
        self._display = display
        screen = self._lib.XDefaultScreen(display)
        self._root = self._lib.XRootWindow(display, screen)
        self._atoms: Dict[bytes, int] = {}

    # -- ctypes plumbing ----------------------------------------------------
    def _configure_prototypes(self) -> None:
        lib = self._lib
        lib.XOpenDisplay.restype = ctypes.c_void_p
        lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
        lib.XCloseDisplay.restype = ctypes.c_int
        lib.XCloseDisplay.argtypes = [ctypes.c_void_p]
        lib.XDefaultScreen.restype = ctypes.c_int
        lib.XDefaultScreen.argtypes = [ctypes.c_void_p]
        lib.XRootWindow.restype = ctypes.c_ulong
        lib.XRootWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        lib.XInternAtom.restype = ctypes.c_ulong
        lib.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_bool]
        lib.XGetWindowProperty.restype = ctypes.c_int
        lib.XGetWindowProperty.argtypes = [
            ctypes.c_void_p,  # display
            ctypes.c_ulong,  # window
            ctypes.c_ulong,  # property
            ctypes.c_long,  # long_offset
            ctypes.c_long,  # long_length
            ctypes.c_bool,  # delete
            ctypes.c_ulong,  # req_type
            ctypes.POINTER(ctypes.c_ulong),  # actual_type_return
            ctypes.POINTER(ctypes.c_int),  # actual_format_return
            ctypes.POINTER(ctypes.c_ulong),  # nitems_return
            ctypes.POINTER(ctypes.c_ulong),  # bytes_after_return
            ctypes.POINTER(ctypes.POINTER(ctypes.c_ubyte)),  # prop_return
        ]
        lib.XFree.restype = ctypes.c_int
        lib.XFree.argtypes = [ctypes.c_void_p]
        lib.XFetchName.restype = ctypes.c_int
        lib.XFetchName.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_char_p),
        ]
        lib.XQueryTree.restype = ctypes.c_int
        lib.XQueryTree.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.POINTER(ctypes.c_ulong)),
            ctypes.POINTER(ctypes.c_uint),
        ]
        lib.XGetInputFocus.restype = ctypes.c_int
        lib.XGetInputFocus.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_ulong),
            ctypes.POINTER(ctypes.c_int),
        ]

    # -- helpers ------------------------------------------------------------
    def _atom(self, name: bytes) -> int:
        cached = self._atoms.get(name)
        if cached is None:
            cached = int(self._lib.XInternAtom(self._display, name, False))
            self._atoms[name] = cached
        return cached

    def _property(self, window: int, atom_name: bytes, want_type: int = _ANY_PROPERTY_TYPE):
        """Return ``(raw_bytes, cardinal)`` for a window property."""
        actual_type = ctypes.c_ulong()
        actual_format = ctypes.c_int()
        nitems = ctypes.c_ulong()
        bytes_after = ctypes.c_ulong()
        prop = ctypes.POINTER(ctypes.c_ubyte)()

        status = self._lib.XGetWindowProperty(
            self._display,
            ctypes.c_ulong(window),
            ctypes.c_ulong(self._atom(atom_name)),
            0,
            4096,
            False,
            ctypes.c_ulong(want_type),
            ctypes.byref(actual_type),
            ctypes.byref(actual_format),
            ctypes.byref(nitems),
            ctypes.byref(bytes_after),
            ctypes.byref(prop),
        )
        if status != _SUCCESS or not prop:
            return b"", None

        try:
            count = int(nitems.value)
            if count <= 0:
                return b"", None
            fmt = int(actual_format.value)
            if fmt == 32:
                # Xlib widens every 32-bit item into a C long (8 bytes on LP64).
                stride = ctypes.sizeof(ctypes.c_long)
                raw = ctypes.string_at(prop, count * stride)
                cardinal = int.from_bytes(raw[:4], sys.byteorder)
                return raw, cardinal
            item_size = max(1, fmt // 8)
            raw = ctypes.string_at(prop, count * item_size)
            return raw, None
        finally:
            self._lib.XFree(prop)

    def _cardinal(self, window: int, atom_name: bytes) -> Optional[int]:
        _, value = self._property(window, atom_name)
        return value

    def _text(self, window: int, atom_name: bytes, want_type: int = _ANY_PROPERTY_TYPE) -> str:
        raw, _ = self._property(window, atom_name, want_type)
        return _decode(raw)

    def _parent(self, window: int) -> Optional[int]:
        root = ctypes.c_ulong()
        parent = ctypes.c_ulong()
        children = ctypes.POINTER(ctypes.c_ulong)()
        count = ctypes.c_uint()
        status = self._lib.XQueryTree(
            self._display,
            ctypes.c_ulong(window),
            ctypes.byref(root),
            ctypes.byref(parent),
            ctypes.byref(children),
            ctypes.byref(count),
        )
        if children:
            self._lib.XFree(children)
        if status != _SUCCESS:
            return None
        value = int(parent.value)
        return value or None

    def _wm_class(self, window: int) -> Optional[bytes]:
        raw, _ = self._property(window, self.WM_CLASS, _XA_STRING)
        return raw or None

    # -- public API ---------------------------------------------------------
    def is_available(self) -> bool:
        return bool(os.environ.get("DISPLAY"))

    def _active_window_id(self) -> Optional[int]:
        window = self._cardinal(self._root, self._NET_ACTIVE_WINDOW)
        if window:
            return window
        # Fall back to the input focus (some WMs do not set _NET_ACTIVE_WINDOW).
        focus = ctypes.c_ulong()
        revert = ctypes.c_int()
        if self._lib.XGetInputFocus(self._display, ctypes.byref(focus), ctypes.byref(revert)) != _SUCCESS:
            return None
        value = int(focus.value)
        if not value or value == 1 or value == int(self._root):
            return None
        return value

    def get_active_window(self) -> Optional[WindowInfo]:
        window = self._active_window_id()
        if not window:
            return None

        wm_class: Optional[bytes] = None
        title = ""
        pid: Optional[int] = None
        current = window
        for _ in range(8):  # walk up: some toolkits put WM_CLASS on the parent
            if wm_class is None:
                wm_class = self._wm_class(current)
            pid = self._cardinal(current, self._NET_WM_PID) or pid
            if not title:
                title = self._text(current, self._NET_WM_NAME, self._atom(self._UTF8_STRING))
            if wm_class and pid and title:
                break
            parent = self._parent(current)
            if not parent or parent == current:
                break
            current = parent

        if not title:
            name_ptr = ctypes.c_char_p()
            if self._lib.XFetchName(self._display, ctypes.c_ulong(current), ctypes.byref(name_ptr)) == _SUCCESS:
                if name_ptr.value:
                    title = _decode(name_ptr.value)
                self._lib.XFree(name_ptr)

        res_name, res_class = "", ""
        if wm_class:
            parts = [part for part in wm_class.split(b"\x00") if part]
            if len(parts) >= 2:
                res_name, res_class = _decode(parts[0]), _decode(parts[1])
            elif parts:
                res_name = res_class = _decode(parts[0])

        app_id = res_class or res_name or f"window-{window}"
        app_name = prettify_app_name(app_id, fallback=title)
        return WindowInfo(
            app_id=app_id,
            app_name=app_name,
            title=title,
            pid=pid,
            source=self.name,
        )

    def close(self) -> None:
        if getattr(self, "_display", None):
            self._lib.XCloseDisplay(self._display)
            self._display = None


# --------------------------------------------------------------------------- #
# xprop fallback
# --------------------------------------------------------------------------- #


class XpropWindowSource(WindowSource):
    """Active window via ``xprop`` (``x11-utils`` package)."""

    name = "xprop"
    kind = "x11"
    label = "xprop (x11-utils)"

    def is_available(self) -> bool:
        return bool(os.environ.get("DISPLAY")) and shutil.which("xprop") is not None

    def _run(self, args: Sequence[str]) -> str:
        completed = subprocess.run(
            list(args),
            capture_output=True,
            text=True,
            timeout=5,
            env={**os.environ},
        )
        return completed.stdout or ""

    def get_active_window(self) -> Optional[WindowInfo]:
        output = self._run(["xprop", "-root", "_NET_ACTIVE_WINDOW"])
        window = None
        for token in output.replace("#", " ").split():
            if token.startswith("0x"):
                window = token
                break
        if not window:
            return None

        details = self._run(["xprop", "-id", window, "WM_CLASS", "_NET_WM_NAME", "_NET_WM_PID"])
        res_name = res_class = title = ""
        pid: Optional[int] = None
        for line in details.splitlines():
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"')
            if key == "WM_CLASS":
                parts = [p.strip().strip('"') for p in value.split(",")]
                if parts:
                    res_name = parts[0]
                if len(parts) > 1:
                    res_class = parts[1]
            elif key in ("_NET_WM_NAME", "WM_NAME"):
                title = value
            elif key == "_NET_WM_PID":
                try:
                    pid = int(value.split()[-1])
                except (ValueError, IndexError):
                    pid = None

        app_id = res_class or res_name or f"window-{window}"
        return WindowInfo(
            app_id=app_id,
            app_name=prettify_app_name(app_id, fallback=title),
            title=title,
            pid=pid,
            source=self.name,
        )


# --------------------------------------------------------------------------- #
# Sway / wroots compositors
# --------------------------------------------------------------------------- #


class SwayWindowSource(WindowSource):
    """Active window via ``swaymsg -t get_tree``."""

    name = "sway"
    kind = "wayland"
    label = "Sway (swaymsg)"

    def is_available(self) -> bool:
        if not (os.environ.get("SWAYSOCK") or os.environ.get("WAYLAND_DISPLAY")):
            return False
        return shutil.which("swaymsg") is not None

    def _run(self) -> str:
        completed = subprocess.run(
            ["swaymsg", "-t", "get_tree"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if completed.returncode != 0:
            raise OSError((completed.stderr or "swaymsg failed").strip())
        return completed.stdout

    @staticmethod
    def _focused(node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if node.get("focused") and node.get("type") in ("con", "floating_con"):
            return node
        for key in ("nodes", "floating_nodes"):
            for child in node.get(key) or []:
                found = SwayWindowSource._focused(child)
                if found:
                    return found
        return None

    def get_active_window(self) -> Optional[WindowInfo]:
        tree = json.loads(self._run())
        node = self._focused(tree) or {}
        if not node:
            return None
        props = node.get("window_properties") or {}
        app_id = node.get("app_id") or props.get("class") or props.get("instance") or ""
        title = node.get("name") or ""
        pid = node.get("pid")
        if not app_id:
            return None
        return WindowInfo(
            app_id=str(app_id),
            app_name=prettify_app_name(str(app_id), fallback=title),
            title=title,
            pid=int(pid) if isinstance(pid, int) else None,
            source=self.name,
        )


# --------------------------------------------------------------------------- #
# Hyprland
# --------------------------------------------------------------------------- #


class HyprlandWindowSource(WindowSource):
    """Active window via ``hyprctl -j activewindow``."""

    name = "hyprland"
    kind = "wayland"
    label = "Hyprland (hyprctl)"

    def is_available(self) -> bool:
        if not (os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") or os.environ.get("WAYLAND_DISPLAY")):
            return False
        return shutil.which("hyprctl") is not None

    def get_active_window(self) -> Optional[WindowInfo]:
        completed = subprocess.run(
            ["hyprctl", "-j", "activewindow"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if completed.returncode != 0:
            return None
        payload = json.loads(completed.stdout or "{}")
        app_id = payload.get("class") or payload.get("initialClass") or ""
        title = payload.get("title") or ""
        if not app_id:
            return None
        return WindowInfo(
            app_id=str(app_id),
            app_name=prettify_app_name(str(app_id), fallback=title),
            title=title,
            pid=int(payload["pid"]) if isinstance(payload.get("pid"), int) else None,
            source=self.name,
        )


# --------------------------------------------------------------------------- #
# User supplied command
# --------------------------------------------------------------------------- #


class ExternalWindowSource(WindowSource):
    """Any command that prints the active window as JSON or ``|`` separated."""

    name = "external"
    kind = "external"
    label = "external command"

    def __init__(self, command: str) -> None:
        self.command = command

    def is_available(self) -> bool:
        return bool(self.command.strip())

    def get_active_window(self) -> Optional[WindowInfo]:
        completed = subprocess.run(
            self.command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = (completed.stdout or "").strip()
        if not output:
            return None
        try:
            payload = json.loads(output)
        except json.JSONDecodeError:
            payload = None
        if isinstance(payload, dict):
            app_id = payload.get("app_id") or payload.get("appId") or payload.get("class") or ""
            app_name = payload.get("app_name") or payload.get("appName") or ""
            title = payload.get("title") or ""
            pid = payload.get("pid")
        else:
            fields = output.split("|")
            app_id = fields[0] if fields else ""
            app_name = fields[1] if len(fields) > 1 else ""
            title = fields[2] if len(fields) > 2 else ""
            pid = fields[3] if len(fields) > 3 else None
        app_id = str(app_id).strip()
        if not app_id:
            return None
        try:
            pid_value = int(pid) if pid is not None else None
        except (TypeError, ValueError):
            pid_value = None
        return WindowInfo(
            app_id=app_id,
            app_name=str(app_name).strip() or prettify_app_name(app_id, fallback=str(title)),
            title=str(title),
            pid=pid_value,
            source=self.name,
        )


# --------------------------------------------------------------------------- #
# Null / scripted sources
# --------------------------------------------------------------------------- #


class NullWindowSource(WindowSource):
    """Returns nothing -- used by ``--window-source none`` and tests."""

    name = "none"
    kind = "none"
    label = "disabled"

    def is_available(self) -> bool:
        return True

    def get_active_window(self) -> Optional[WindowInfo]:
        return None


class ScriptedWindowSource(WindowSource):
    """Replays a fixed list of windows; used for tests and ``--dry-run``."""

    name = "scripted"
    kind = "scripted"
    label = "scripted"

    def __init__(self, script: Sequence[Optional[WindowInfo]], hold: int = 1) -> None:
        self._script: List[Optional[WindowInfo]] = list(script)
        self._hold = max(1, int(hold))
        self._index = 0

    def is_available(self) -> bool:
        return True

    def get_active_window(self) -> Optional[WindowInfo]:
        if not self._script:
            return None
        position = min(self._index // self._hold, len(self._script) - 1)
        item = self._script[position]
        self._index += 1
        return item


# --------------------------------------------------------------------------- #
# Factory / environment detection
# --------------------------------------------------------------------------- #

_SOURCES = {
    "x11": X11WindowSource,
    "xprop": XpropWindowSource,
    "sway": SwayWindowSource,
    "hyprland": HyprlandWindowSource,
    "none": NullWindowSource,
}

_AUTO_ORDER = ("x11", "sway", "hyprland", "xprop")


def open_window_source(preference: str = "auto", external_command: str = "") -> WindowSource:
    """Instantiate the best available window source.

    Raises ``OSError`` with an actionable message when the requested source is
    not usable on this machine.
    """
    preference = (preference or "auto").strip().lower()

    if preference == "external":
        if not external_command.strip():
            raise OSError("window source 'external' needs settings.external_window_command")
        source = ExternalWindowSource(external_command)
        if not source.is_available():
            raise OSError("external window source is not configured")
        return source

    if preference in _SOURCES:
        candidates: Iterable[type] = [_SOURCES[preference]]
    elif preference in ("auto", ""):
        candidates = [_SOURCES[name] for name in _AUTO_ORDER]
    else:
        raise OSError(
            f"unknown window source '{preference}' "
            f"(expected one of: auto, {', '.join(sorted(_SOURCES))}, external)"
        )

    failures: List[str] = []
    for cls in candidates:
        try:
            instance = cls()
        except OSError as error:
            failures.append(f"{cls.name}: {error}")
            continue
        except Exception as error:  # pragma: no cover - defensive
            failures.append(f"{cls.name}: {error}")
            continue
        if not instance.is_available():
            instance.close()
            continue
        return instance

    raise OSError(
        "no usable active-window source found"
        + (f" ({'; '.join(failures)})" if failures else "")
        + ". Install libx11 (or x11-utils), or run on Sway/Hyprland, "
        "or set settings.external_window_command."
    )


def _probe(cls: type) -> Optional[WindowSource]:
    """Instantiate a source, returning ``None`` when it is not usable here."""
    try:
        instance = cls()
    except Exception:  # OSError and anything a missing library can raise
        return None
    try:
        if not instance.is_available():
            return None
    except Exception:  # pragma: no cover - defensive
        return None
    return instance


def describe_environment() -> Dict[str, Any]:
    """Diagnostics used by ``cdt doctor``."""
    detected: List[str] = []
    notes: List[str] = []

    for name in _AUTO_ORDER:
        if _probe(_SOURCES[name]) is not None:
            detected.append(name)

    session = "X11" if os.environ.get("DISPLAY") else ""
    if os.environ.get("SWAYSOCK"):
        session = "Sway"
    elif os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        session = "Hyprland"
    elif os.environ.get("WAYLAND_DISPLAY"):
        session = "Wayland"

    if session == "Wayland":
        notes.append(
            "GNOME/KDE Wayland sessions do not expose the focused window to "
            "clients; per-app tracking is unavailable there (idle time is still "
            "recorded). Use X11, Sway, Hyprland or settings.external_window_command."
        )
    if not os.environ.get("DISPLAY") and session != "X11":
        notes.append("No DISPLAY/WAYLAND_DISPLAY found - is this a desktop session?")

    return {
        "session": session or "unknown",
        "display": os.environ.get("DISPLAY", ""),
        "waylandDisplay": os.environ.get("WAYLAND_DISPLAY", ""),
        "availableSources": detected,
        "tools": {
            tool: bool(shutil.which(tool))
            for tool in ("xprop", "swaymsg", "hyprctl", "gdbus", "xprintidle", "systemctl")
        },
        "notes": notes,
    }
