"""Configuration, credentials and XDG path handling."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, List, Optional

from . import APP_SLUG

# --------------------------------------------------------------------------- #
# Paths (XDG base directory specification)
# --------------------------------------------------------------------------- #


class AppPaths:
    """Resolve every location the client writes to."""

    def __init__(
        self,
        config_dir: Optional[Path] = None,
        data_dir: Optional[Path] = None,
        state_dir: Optional[Path] = None,
    ) -> None:
        self.config_dir = Path(
            config_dir
            or os.environ.get("CDT_CONFIG_DIR")
            or os.environ.get("XDG_CONFIG_HOME")
            or Path.home() / ".config"
        ) / APP_SLUG
        self.data_dir = Path(
            data_dir
            or os.environ.get("CDT_DATA_DIR")
            or os.environ.get("XDG_DATA_HOME")
            or Path.home() / ".local" / "share"
        ) / APP_SLUG
        self.state_dir = Path(
            state_dir
            or os.environ.get("CDT_STATE_DIR")
            or os.environ.get("XDG_STATE_HOME")
            or Path.home() / ".local" / "state"
        ) / APP_SLUG

    # -- files ---------------------------------------------------------------
    @property
    def config_file(self) -> Path:
        return self.config_dir / "config.json"

    @property
    def credentials_file(self) -> Path:
        return self.config_dir / "credentials.json"

    @property
    def queue_db(self) -> Path:
        return self.data_dir / "queue.db"

    @property
    def log_file(self) -> Path:
        return self.state_dir / "tracker.log"

    @property
    def pid_file(self) -> Path:
        return self.state_dir / "tracker.pid"

    def ensure(self) -> None:
        for directory in (self.config_dir, self.data_dir, self.state_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def describe(self) -> Dict[str, str]:
        return {
            "config": str(self.config_file),
            "credentials": str(self.credentials_file),
            "queue": str(self.queue_db),
            "log": str(self.log_file),
        }


def _write_private_json(path: Path, payload: Dict[str, Any]) -> None:
    """Write JSON with ``0600`` permissions (tokens live here)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
    tmp.replace(path)


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #

#: Known ``WM_CLASS``/``app_id`` -> friendly display names.  The backend stores
#: ``AppName`` (falling back to ``PackageName``) so a readable name makes the
#: dashboard far more useful.
KNOWN_APP_NAMES: Dict[str, str] = {
    "google-chrome": "Google Chrome",
    "google-chrome-stable": "Google Chrome",
    "google-chrome-beta": "Google Chrome Beta",
    "chromium": "Chromium",
    "chromium-browser": "Chromium",
    "firefox": "Firefox",
    "firefox-esr": "Firefox",
    "code": "Visual Studio Code",
    "code-oss": "Visual Studio Code",
    "codium": "VSCodium",
    "org.gnome.nautilus": "Files",
    "nautilus": "Files",
    "org.gnome.terminal": "Terminal",
    "gnome-terminal": "Terminal",
    "org.gnome.console": "Console",
    "kgx": "Console",
    "konsole": "Konsole",
    "xterm": "XTerm",
    "urxvt": "URxvt",
    "alacritty": "Alacritty",
    "kitty": "kitty",
    "wezterm": "WezTerm",
    "org.gnome.gedit": "Text Editor",
    "gedit": "Text Editor",
    "kate": "Kate",
    "org.gnome.settings": "Settings",
    "gnome-control-center": "Settings",
    "gnome-tweaks": "Tweaks",
    "org.gnome.systemmonitor": "System Monitor",
    "gnome-system-monitor": "System Monitor",
    "org.gnome.Calendar": "Calendar",
    "org.gnome.clocks": "Clocks",
    "org.gnome.maps": "Maps",
    "org.gnome.weather": "Weather",
    "org.gnome.totem": "Videos",
    "totem": "Videos",
    "org.gnome.Rhythmbox3": "Rhythmbox",
    "rhythmbox": "Rhythmbox",
    "spotify": "Spotify",
    "vlc": "VLC",
    "org.videolan.vlc": "VLC",
    "mpv": "mpv",
    "celluloid": "Celluloid",
    "org.gnome.eog": "Image Viewer",
    "eog": "Image Viewer",
    "org.gnome.evince": "Document Viewer",
    "evince": "Document Viewer",
    "okular": "Okular",
    "libreoffice-writer": "LibreOffice Writer",
    "libreoffice-calc": "LibreOffice Calc",
    "libreoffice-impress": "LibreOffice Impress",
    "org.telegram.desktop": "Telegram",
    "telegramdesktop": "Telegram",
    "discord": "Discord",
    "slack": "Slack",
    "zoom": "Zoom",
    "org.gnome.characters": "Characters",
    "thunderbird": "Thunderbird",
    "evolution": "Evolution",
    "org.gnome.geary": "Geary",
    "gimp": "GIMP",
    "inkscape": "Inkscape",
    "krita": "Krita",
    "blender": "Blender",
    "obs": "OBS Studio",
    "com.obsproject.studio": "OBS Studio",
    "steam": "Steam",
    "lutris": "Lutris",
    "jetbrains-idea": "IntelliJ IDEA",
    "jetbrains-pycharm": "PyCharm",
    "jetbrains-studio": "Android Studio",
    "vim": "Vim",
    "nvim": "Neovim",
    "emacs": "Emacs",
    "org.qbittorrent.qbittorrent": "qBittorrent",
    "transmission-gtk": "Transmission",
    "org.gnome.books": "Books",
    "org.gnome.music": "Music",
    "org.gnome.photos": "Photos",
    "shotwell": "Shotwell",
    "simple-scan": "Document Scanner",
    "keepassxc": "KeePassXC",
    "bitwarden": "Bitwarden",
    "org.signal.Signal": "Signal",
    "element": "Element",
    "postman": "Postman",
    "insomnia": "Insomnia",
    "dbeaver": "DBeaver",
    "pgadmin4": "pgAdmin 4",
    "docker": "Docker Desktop",
    "org.gnome.design.iconlibrary": "Icon Library",
}


@dataclass(slots=True)
class Settings:
    """Runtime configuration (persisted as ``config.json``)."""

    # connection -----------------------------------------------------------
    api_url: str = "http://localhost:5148"
    request_timeout_seconds: float = 15.0

    # identity -------------------------------------------------------------
    device_name: str = ""
    platform: str = "Linux"

    # tracking -------------------------------------------------------------
    window_source: str = "auto"  # auto | x11 | xprop | sway | hyprland | external | none
    idle_source: str = "auto"  # auto | xss | xprintidle | mutter | none
    external_window_command: str = ""
    poll_interval_seconds: float = 1.0
    idle_threshold_seconds: int = 300
    min_session_seconds: int = 2
    max_session_seconds: int = 900
    #: Poll-to-poll gap after which the gap is treated as suspend time
    #: (0 = auto: 3x the poll interval, at least 30 seconds).
    gap_threshold_seconds: float = 0.0

    # syncing --------------------------------------------------------------
    sync_interval_seconds: int = 30
    batch_size: int = 50
    retry_base_seconds: int = 15
    retry_max_seconds: int = 900

    # filtering ------------------------------------------------------------
    include_apps: List[str] = field(default_factory=list)
    exclude_apps: List[str] = field(default_factory=list)

    # logging --------------------------------------------------------------
    log_level: str = "INFO"

    # ------------------------------------------------------------------ #
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Settings":
        known = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in (data or {}).items() if k in known and v is not None}
        settings = cls(**kwargs)
        settings.normalize()
        return settings

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def normalize(self) -> None:
        """Coerce/validate values so a hand-edited config cannot break the daemon."""
        self.api_url = (self.api_url or "").strip().rstrip("/") or "http://localhost:5148"
        self.device_name = (self.device_name or "").strip()
        self.platform = (self.platform or "Linux").strip() or "Linux"
        self.window_source = (self.window_source or "auto").strip().lower()
        self.idle_source = (self.idle_source or "auto").strip().lower()
        self.poll_interval_seconds = min(max(float(self.poll_interval_seconds), 0.25), 60.0)
        self.idle_threshold_seconds = max(int(self.idle_threshold_seconds), 10)
        self.min_session_seconds = max(int(self.min_session_seconds), 1)
        self.max_session_seconds = max(int(self.max_session_seconds), 30)
        self.gap_threshold_seconds = max(float(self.gap_threshold_seconds), 0.0)
        self.sync_interval_seconds = max(int(self.sync_interval_seconds), 5)
        self.batch_size = min(max(int(self.batch_size), 1), 200)
        self.retry_base_seconds = max(int(self.retry_base_seconds), 1)
        self.retry_max_seconds = max(int(self.retry_max_seconds), self.retry_base_seconds)
        self.request_timeout_seconds = min(max(float(self.request_timeout_seconds), 1.0), 120.0)
        self.include_apps = [str(x).strip() for x in self.include_apps if str(x).strip()]
        self.exclude_apps = [str(x).strip() for x in self.exclude_apps if str(x).strip()]
        self.log_level = (self.log_level or "INFO").upper()


@dataclass(slots=True)
class Credentials:
    """Tokens stored with ``0600`` permissions."""

    device_id: str = ""
    device_jwt: str = ""
    linked_at: str = ""
    device_name: str = ""
    user_jwt: str = ""
    user_email: str = ""

    @property
    def is_linked(self) -> bool:
        return bool(self.device_id and self.device_jwt)

    @property
    def has_user_session(self) -> bool:
        return bool(self.user_jwt)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Credentials":
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (data or {}).items() if k in known and v is not None})

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Load / save helpers
# --------------------------------------------------------------------------- #


class ConfigStore:
    """Loads/saves ``Settings`` and ``Credentials`` for the given paths."""

    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths

    # -- settings -----------------------------------------------------------
    def load_settings(self) -> Settings:
        data = _read_json(self.paths.config_file)
        settings = Settings.from_dict(data)
        # environment variables win over the file (handy for systemd units)
        env_url = os.environ.get("CDT_API_URL")
        if env_url:
            settings.api_url = env_url.strip().rstrip("/")
        return settings

    def save_settings(self, settings: Settings) -> None:
        settings.normalize()
        _write_private_json(self.paths.config_file, settings.to_dict())

    # -- credentials --------------------------------------------------------
    def load_credentials(self) -> Credentials:
        return Credentials.from_dict(_read_json(self.paths.credentials_file))

    def save_credentials(self, credentials: Credentials) -> None:
        _write_private_json(self.paths.credentials_file, credentials.to_dict())

    def clear_credentials(self) -> None:
        try:
            self.paths.credentials_file.unlink()
        except FileNotFoundError:
            pass
