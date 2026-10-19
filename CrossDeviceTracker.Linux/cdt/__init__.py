"""CrossDeviceTracker Linux client.

A dependency-free (standard library only) desktop client for
``CrossDeviceTracker.Api`` that tracks foreground application usage on a Linux
machine and synchronises it to the backend.

Highlights
----------
* X11 (libX11), Sway and Hyprland active-window detection
* Idle detection via XScreenSaver, ``xprintidle`` or GNOME Mutter
* Offline-first SQLite queue with idempotent, batched uploads
* Device pairing through the backend one-time desktop link token flow
* Dashboard / analytics reporting straight from the CLI
"""

from __future__ import annotations

__version__ = "1.0.0"
__all__ = ["__version__"]

APP_NAME = "CrossDeviceTracker"
APP_SLUG = "crossdevicetracker"
COMMAND_NAME = "cdt"
USER_AGENT = f"CrossDeviceTracker.Linux/{__version__}"
