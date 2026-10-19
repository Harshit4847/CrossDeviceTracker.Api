"""Idle time detection.

Idle detection is what makes the numbers honest: without it, leaving a browser
open on a second monitor while reading a book would inflate the usage data.

Supported back-ends
-------------------
``xss``
    ``XScreenSaverQueryInfo`` from ``libXss`` (X11 sessions).
``xprintidle``
    The ``xprintidle`` utility from ``x11-utils``.
``mutter``
    ``org.gnome.Mutter.IdleMonitor`` over D-Bus (GNOME, X11 *and* Wayland).
``none``
    Always report zero idle time.
"""

from __future__ import annotations

import ctypes
import os
import shutil
import subprocess
from abc import ABC, abstractmethod
from typing import Any, Dict, List

from .window import _load_library


class IdleSource(ABC):
    """Returns the number of milliseconds since the last user input."""

    name = "abstract"
    label = "abstract"

    @abstractmethod
    def is_available(self) -> bool: ...

    @abstractmethod
    def get_idle_ms(self) -> int: ...

    def close(self) -> None:  # pragma: no cover - default no-op
        """Release native resources."""


class XssIdleSource(IdleSource):
    """Idle time through the XScreenSaver extension."""

    name = "xss"
    label = "XScreenSaver (libXss)"

    class _ScreenSaverInfo(ctypes.Structure):
        _fields_ = [
            ("window", ctypes.c_ulong),
            ("state", ctypes.c_int),
            ("kind", ctypes.c_int),
            ("til_or_since", ctypes.c_ulong),
            ("idle", ctypes.c_ulong),
            ("event_mask", ctypes.c_ulong),
        ]

    def __init__(self) -> None:
        library = _load_library(["libXss.so.1", "libXss.so"])
        if library is None:
            raise OSError("libXss is not installed")
        x11 = _load_library(["libX11.so.6", "libX11.so"])
        if x11 is None:
            raise OSError("libX11 is not installed")

        self._lib = library
        self._x11 = x11
        x11.XOpenDisplay.restype = ctypes.c_void_p
        x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x11.XDefaultScreen.restype = ctypes.c_int
        x11.XDefaultScreen.argtypes = [ctypes.c_void_p]
        x11.XRootWindow.restype = ctypes.c_ulong
        x11.XRootWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
        x11.XCloseDisplay.restype = ctypes.c_int
        x11.XCloseDisplay.argtypes = [ctypes.c_void_p]

        library.XScreenSaverQueryInfo.restype = ctypes.c_int
        library.XScreenSaverQueryInfo.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ulong,
            ctypes.POINTER(self._ScreenSaverInfo),
        ]

        display = x11.XOpenDisplay(None)
        if not display:
            raise OSError("cannot open the X display (is DISPLAY set?)")
        self._display = display
        self._root = x11.XRootWindow(display, x11.XDefaultScreen(display))
        self._info = self._ScreenSaverInfo()

    def is_available(self) -> bool:
        return bool(os.environ.get("DISPLAY"))

    def get_idle_ms(self) -> int:
        status = self._lib.XScreenSaverQueryInfo(
            self._display, self._root, ctypes.byref(self._info)
        )
        if status == 0:
            return 0
        return int(self._info.idle)

    def close(self) -> None:
        if getattr(self, "_display", None):
            self._x11.XCloseDisplay(self._display)
            self._display = None


class XPrintIdleSource(IdleSource):
    """Idle time through the ``xprintidle`` command."""

    name = "xprintidle"
    label = "xprintidle"

    def is_available(self) -> bool:
        return bool(os.environ.get("DISPLAY")) and shutil.which("xprintidle") is not None

    def get_idle_ms(self) -> int:
        completed = subprocess.run(
            ["xprintidle"], capture_output=True, text=True, timeout=5
        )
        if completed.returncode != 0:
            return 0
        try:
            return int(completed.stdout.strip())
        except ValueError:
            return 0


class MutterIdleSource(IdleSource):
    """Idle time through GNOME's Mutter idle monitor over D-Bus."""

    name = "mutter"
    label = "GNOME Mutter IdleMonitor (gdbus)"

    _DEST = "org.gnome.Mutter.IdleMonitor"
    _PATH = "/org/gnome/Mutter/IdleMonitor/Core"
    _METHOD = "org.gnome.Mutter.IdleMonitor.GetIdletime"

    def is_available(self) -> bool:
        if not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            return False
        return shutil.which("gdbus") is not None

    def get_idle_ms(self) -> int:
        completed = subprocess.run(
            [
                "gdbus",
                "call",
                "--session",
                "--dest",
                self._DEST,
                "--object-path",
                self._PATH,
                "--method",
                self._METHOD,
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if completed.returncode != 0:
            return 0
        text = (completed.stdout or "").strip().strip("(),")
        if not text:
            return 0
        try:
            return int(text.split()[-1])
        except (ValueError, IndexError):
            return 0


class NullIdleSource(IdleSource):
    """Report zero idle time."""

    name = "none"
    label = "disabled"

    def is_available(self) -> bool:
        return True

    def get_idle_ms(self) -> int:
        return 0


class ScriptedIdleSource(IdleSource):
    """Replay a fixed idle sequence (tests and ``--dry-run``)."""

    name = "scripted"
    label = "scripted"

    def __init__(self, sequence: List[int]) -> None:
        self._sequence = list(sequence) or [0]
        self._index = 0

    def is_available(self) -> bool:
        return True

    def get_idle_ms(self) -> int:
        value = self._sequence[min(self._index, len(self._sequence) - 1)]
        self._index += 1
        return int(value)


_SOURCES = {
    "xss": XssIdleSource,
    "xprintidle": XPrintIdleSource,
    "mutter": MutterIdleSource,
    "none": NullIdleSource,
}


def open_idle_source(preference: str = "auto") -> IdleSource:
    """Instantiate the best available idle source (never fatal)."""
    preference = (preference or "auto").strip().lower()

    if preference in _SOURCES:
        candidates = [_SOURCES[preference]]
    elif preference in ("auto", ""):
        if os.environ.get("DISPLAY"):
            candidates = [_SOURCES["xss"], _SOURCES["xprintidle"], _SOURCES["mutter"]]
        elif os.environ.get("WAYLAND_DISPLAY"):
            candidates = [_SOURCES["mutter"], _SOURCES["xss"], _SOURCES["xprintidle"]]
        else:
            candidates = [_SOURCES["mutter"]]
    else:
        raise OSError(
            f"unknown idle source '{preference}' "
            f"(expected one of: auto, {', '.join(sorted(_SOURCES))})"
        )

    failures: List[str] = []
    for cls in candidates:
        try:
            instance = cls()
        except OSError as error:
            failures.append(f"{cls.name}: {error}")
            continue
        if not instance.is_available():
            instance.close()
            continue
        return instance

    # Idle detection is optional: degrade to "never idle" instead of failing.
    return NullIdleSource()


def describe_idle_environment() -> Dict[str, Any]:
    """Diagnostics used by ``cdt doctor``."""
    available: List[str] = []
    for name, cls in _SOURCES.items():
        if name == "none":
            continue
        try:
            instance = cls()
        except Exception:
            continue
        if instance.is_available():
            available.append(name)
        instance.close()
    return {"availableSources": available}
