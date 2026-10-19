# CrossDeviceTracker.Linux

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Platform](https://img.shields.io/badge/platform-Linux-lightgrey)

Linux desktop client for [**CrossDeviceTracker.Api**](https://github.com/Harshit4847/CrossDeviceTracker.Api) — it watches which
application is in the foreground, turns that into usage sessions and syncs them to your
account, exactly like the Windows client does on Windows.

* **No dependencies.** Standard library only — no `pip install` of third party packages,
  no Node, no .NET runtime. Python 3.10+ is enough.
* **Works offline.** Sessions are queued in SQLite and uploaded when the network returns.
  Every upload is idempotent (`ClientSessionId`), so retries never duplicate data.
* **Honest numbers.** Idle detection stops the clock when you walk away, sub-2 second
  app switches are ignored, and a suspended laptop is not counted as screen time.
* **Runs at login.** One command installs a systemd user service (or an XDG autostart
  entry if systemd is not available).

---

## Table of contents

- [Quick start](#quick-start)
- [Quick start (हिंदी में)](#quick-start-हिंदी-में)
- [How it works](#how-it-works)
- [Installation](#installation)
- [Pairing this machine](#pairing-this-machine)
- [Running](#running)
- [Commands](#commands)
- [Configuration](#configuration)
- [Display server support](#display-server-support)
- [Data & privacy](#data--privacy)
- [Development](#development)
- [Troubleshooting](#troubleshooting)

---

## Quick start

```bash
# 1. make sure the backend is running (see https://github.com/Harshit4847/CrossDeviceTracker.Api) and note its URL
#    default: http://localhost:5148

# 2. install the client (creates a private venv, no root required)
./scripts/install.sh

# 3. pair this machine — you need a link token from the web dashboard
cdt link --token <TOKEN>
#    ...or pair in a single step with your account:
cdt link --email you@example.com --password 'your-password'

# 4. check that everything is wired up
cdt doctor

# 5. track in the foreground (Ctrl+C to stop)
cdt start

# 6. see your numbers
cdt status
cdt apps --days 7
```

## Quick start (हिंदी में)

```bash
# 1. Pehle backend API chalu rakhein (https://github.com/Harshit4847/CrossDeviceTracker.Api) — default http://localhost:5148

# 2. Client install karein (root ki zarurat nahi, apna venv banata hai)
./scripts/install.sh

# 3. Is machine ko pair karein — web dashboard se ek link token lein
cdt link --token <TOKEN>
#    ya seedha apne account se:
cdt link --email aapka@email.com --password 'aapka-password'

# 4. Sab theek hai ya nahi check karein
cdt doctor

# 5. Tracking shuru karein (Ctrl+C se band)
cdt start

# 6. Apna data dekhein
cdt status
cdt apps --days 7
```

Login par automatic chalu karne ke liye:

```bash
cdt service install      # systemd user service
cdt service status       # dekhein ki chal raha hai ya nahi
cdt service logs         # aakhri logs
```

---

## How it works

```
┌─────────────────────── Linux desktop ───────────────────────┐
│                                                             │
│  X11 / Sway / Hyprland          Idle source                 │
│  ┌───────────────────┐          ┌───────────────────────┐   │
│  │ active window     │          │ XScreenSaver /        │   │
│  │ + WM_CLASS + PID  │          │ xprintidle / Mutter   │   │
│  └─────────┬─────────┘          └───────────┬───────────┘   │
│            └──────────────┬─────────────────┘               │
│                           ▼                                 │
│                 ┌──────────────────┐                        │
│                 │  UsageTracker    │  poll (default 1s)     │
│                 │  - app switches  │  idle threshold 5 min  │
│                 │  - segmentation  │  min session 2s        │
│                 └────────┬─────────┘                        │
│                          ▼                                  │
│              ┌───────────────────────┐                      │
│              │ SQLite queue (offline)│  ~/.local/share/...  │
│              └───────────┬───────────┘                      │
└──────────────────────────┼──────────────────────────────────┘
                           │ POST /api/timelogs/batch   (Device JWT)
                           ▼
                ┌────────────────────────┐
                │  CrossDeviceTracker.Api │
                └────────────────────────┘
```

Each tick of the tracker:

1. reads the foreground window and the idle time,
2. closes the running session if the application changed, if the user went idle, or if
   the application was filtered out,
3. closes it at the **last input event** when idle, so reading a document without
   touching the mouse does not inflate the numbers,
4. flushes long running applications every `max_session_seconds` (default 15 min) so data
   reaches the backend continuously,
5. never records a gap larger than the suspend threshold — a laptop that was asleep for
   an hour does not become an hour of "browser usage".

Only sessions of at least `min_session_seconds` (default 2s) are stored, which removes
alt-tab noise.

---

## Installation

### One command (recommended)

```bash
./scripts/install.sh
```

This creates a private virtual environment in `~/.local/share/crossdevicetracker/venv`,
installs the `cdt` command into `~/.local/bin`, and registers the login service.
No root, no system Python changes.

Variants:

| Command | Effect |
|---|---|
| `./scripts/install.sh` | venv + systemd user service |
| `CDT_INSTALL_MODE=user ./scripts/install.sh` | `pip install --user` |
| `CDT_INSTALL_MODE=system ./scripts/install.sh` | system wide install |
| `CDT_SKIP_SERVICE=1 ./scripts/install.sh` | only install the command |
| `CDT_API_URL=http://my-server:5148 ./scripts/install.sh` | pre-set the backend URL |

### Without installing anything

The client runs straight from the source tree:

```bash
python3 -m cdt --help
```

### Uninstall

```bash
./scripts/uninstall.sh                 # keeps your credentials and queue
CDT_PURGE_DATA=1 ./scripts/uninstall.sh  # deletes them too
```

---

## Pairing this machine

The backend identifies devices by a **Device JWT** that is issued through a one-time
link token, so no password is ever stored on this machine.

1. Sign in to the web dashboard and click *generate desktop link token*
   (`POST /api/devices/link-token`).
2. Run `cdt link --token <TOKEN>` — tokens are valid for ~10 minutes and work once.
3. Or skip the dashboard entirely: `cdt link --email you@example.com --password '...'`
   generates the token and links in one step.

Credentials are written to `~/.config/crossdevicetracker/credentials.json` with `0600`
permissions. To re-link, simply run `cdt link` again — the old device keeps existing in
your account until you remove it from the dashboard.

---

## Running

### In the foreground

```bash
cdt start
```

Useful flags:

```bash
cdt start --duration 30                 # smoke test: stop after 30s
cdt start --dry-run                     # fake data, nothing uploaded
cdt start --window-source sway          # force a specific window source
cdt start --poll 0.5 --min-session 5    # tune the tracking
cdt start --no-sync                     # track locally only
cdt start -vv                           # debug logging
```

### At login (recommended)

```bash
cdt service install     # systemd user unit + start now
cdt service status      # active / enabled / unit path
cdt service logs        # journalctl tail
cdt service uninstall
```

If systemd user services are unavailable, use the XDG autostart entry instead:

```bash
cdt service autostart           # ~/.config/autostart/crossdevicetracker.desktop
cdt service autostart-remove
```

The unit file is also shipped as a template: [`packaging/crossdevicetracker.service`](packaging/crossdevicetracker.service).

### Stopping

`cdt stop` stops a tracker started with `cdt start` (pid file based). A tracker managed
by systemd is stopped with `systemctl --user stop crossdevicetracker`.

---

## Commands

| Command | What it does |
|---|---|
| `cdt link` | Pair this machine (link token or account credentials) |
| `cdt login` / `cdt logout` | User session for reporting commands |
| `cdt start` | Track foreground usage in the foreground |
| `cdt stop` | Stop a running tracker |
| `cdt sync` | Upload queued sessions right now |
| `cdt queue` | Inspect the offline queue (`--clear` to drop it) |
| `cdt status` | Local tracker state + today's screen time |
| `cdt apps` | Per-app breakdown (`--days`, `--device-id`, `--platform`) |
| `cdt devices` | Per-device breakdown (`--days`) |
| `cdt timeline` | Recent sessions (`--days`, `--limit`) |
| `cdt analytics <daily\|weekly\|monthly\|hourly>` | Chart data |
| `cdt logs` | Raw time log entries (`--limit`, `--cursor`) |
| `cdt account` | Signed-in account and registered devices |
| `cdt config` | Show/change settings (`--set key=value`, `--get key`) |
| `cdt doctor` | Environment and connectivity diagnostics |
| `cdt service` | `install`, `uninstall`, `status`, `logs`, `autostart` |
| `cdt version` | Version information |

Every command accepts `--json` for machine readable output, `--api-url` to override the
backend, and `--config-dir` / `--data-dir` to relocate the state (handy for testing).

```bash
$ cdt status
CrossDeviceTracker status
  backend     : http://localhost:5148
  device      : my-laptop (GNOME) (701d2bca-ccb2-48e3-b42d-8d9b5a6417fb)
  account     : you@example.com
  tracker     : running (pid 12345)
  queue       : 2 pending, 0 failing, 0 dead letter(s)

  today       : 2h 3m  (42 sessions, 7 apps)
  yesterday   : 1h 43m 20s
  this week   : 11h 23m 20s
  this month  : 44h 26m 40s
  most used   : Google Chrome (1h 25m)
  devices     : 2
```

---

## Configuration

`~/.config/crossdevicetracker/config.json` (created on first run):

```json
{
  "api_url": "http://localhost:5148",
  "device_name": "my-laptop (GNOME)",
  "platform": "Linux",
  "window_source": "auto",
  "idle_source": "auto",
  "external_window_command": "",
  "poll_interval_seconds": 1.0,
  "idle_threshold_seconds": 300,
  "min_session_seconds": 2,
  "max_session_seconds": 900,
  "gap_threshold_seconds": 0,
  "sync_interval_seconds": 30,
  "batch_size": 50,
  "retry_base_seconds": 15,
  "retry_max_seconds": 900,
  "include_apps": [],
  "exclude_apps": [],
  "log_level": "INFO"
}
```

Change values with `cdt config --set key=value`, e.g.:

```bash
cdt config --set idle_threshold_seconds=180 --set exclude_apps="Slack,Spotify"
cdt config --set api_url=http://192.168.1.20:5148
```

Environment overrides: `CDT_API_URL`, `CDT_CONFIG_DIR`, `CDT_DATA_DIR`, `CDT_STATE_DIR`,
`NO_COLOR`.

### Filtering

| Setting | Meaning |
|---|---|
| `include_apps` | when non-empty, only matching apps are tracked |
| `exclude_apps` | never tracked — wins over `include_apps` |
| `idle_threshold_seconds` | idle time after which the session is closed |
| `min_session_seconds` | shorter sessions are discarded |
| `max_session_seconds` | a running app is flushed in chunks of this size |
| `gap_threshold_seconds` | `0` = auto (3× poll interval, min 30s) |

Matching is a case-insensitive substring match against the application id, the display
name and the window title, so `exclude_apps: ["youtube"]` also excludes a YouTube tab in
a browser.

---

## Display server support

| Session | Window source | Idle source | Notes |
|---|---|---|---|
| X11 (Xorg, XWayland) | `x11` (libX11 via ctypes) or `xprop` | `xss`, `xprintidle`, `mutter` | full per-app tracking |
| Sway / wlroots | `sway` (`swaymsg -t get_tree`) | `mutter` n/a, see note | full per-app tracking |
| Hyprland | `hyprland` (`hyprctl -j activewindow`) | — | full per-app tracking |
| GNOME on Wayland | — | `mutter` | GNOME does not expose the focused window to clients; only idle time is available |
| KDE on Wayland | — | — | same limitation |

`cdt doctor` prints exactly what is detected. For compositors without an interface you
can plug your own:

```bash
cdt config --set window_source=external
cdt config --set external_window_command='~/.local/bin/my-active-window.sh'
```

The command must print either JSON (`{"app_id": "...", "app_name": "...", "title": "...", "pid": 123}`)
or a pipe separated line (`app_id|app_name|title|pid`).

Why not GNOME Shell extensions? A shell extension would need to be installed and kept in
sync with the user's GNOME version, which is fragile across distributions. The client
therefore reports the limitation instead of silently tracking nothing.

---

## Data & privacy

| Data | Where |
|---|---|
| App id (`WM_CLASS`/`app_id`), display name, window title, pid | sent to your backend |
| Session start/end (UTC) and duration | sent to your backend |
| Device JWT, optional user JWT | `~/.config/crossdevicetracker/credentials.json` (`0600`) |
| Unsynced sessions | `~/.local/share/crossdevicetracker/queue.db` |
| Logs | `~/.local/state/crossdevicetracker/tracker.log` (only with `--log-file`) |

Nothing is sent anywhere except the `api_url` you configured. No telemetry, no crash
reporting, no third party services.

---

## Development

```bash
# run the test suite (standard library unittest, ~15s)
python3 -m unittest discover -s tests -t .
# or
./scripts/run-tests.sh
```

```
CrossDeviceTracker.Linux/
├── cdt/
│   ├── __init__.py      version + user agent
│   ├── __main__.py      python -m cdt
│   ├── cli.py           argument parsing and every command
│   ├── config.py        XDG paths, settings, credentials
│   ├── api.py           HTTP client (stdlib urllib)
│   ├── models.py        dataclasses + backend payload contract
│   ├── window.py        X11 / xprop / Sway / Hyprland / external sources
│   ├── idle.py          XScreenSaver / xprintidle / Mutter idle sources
│   ├── tracker.py       the tracking loop and session aggregation
│   ├── queue.py         SQLite offline queue
│   ├── sync.py          batch upload with retry + backoff
│   ├── apps.py          app naming and filtering
│   └── service.py       systemd unit + XDG autostart + pid file
├── tests/               147 unit + integration tests (stub backend included)
├── scripts/             install.sh, uninstall.sh, run-tests.sh
└── packaging/           systemd unit template
```

The test suite includes an in-process stub of the backend
([`tests/stub_api.py`](tests/stub_api.py)) that implements the same validation rules as
the real controller, plus an end-to-end test that links, tracks, queues and syncs.

### Payload contract

`POST /api/timelogs/batch` with the Device JWT:

```json
[
  {
    "packageName": "google-chrome",
    "appName": "Google Chrome",
    "startTimeUtc": "2026-10-19T09:14:02.123456Z",
    "endTimeUtc": "2026-10-19T09:16:32.123456Z",
    "durationSeconds": 150,
    "createdAtUtc": "2026-10-19T09:16:33.000000Z",
    "clientSessionId": "0f1e2d3c-4b5a-6978-8796-a5b4c3d2e1f0"
  }
]
```

`clientSessionId` is a GUID (36 characters — the backend column limit) and, together with
the device id, forms the unique key that makes retries safe.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `cdt doctor` → *backend unreachable* | start the API, or `cdt config --set api_url=...` |
| *no usable active-window source* | install `libx11-6` (and optionally `x11-utils`), or run on Sway/Hyprland, or set `external_window_command` |
| `cdt sync` → *rejected the device token* | the device was revoked: `cdt link` again |
| `cdt status` → *No user session* | `cdt login` (only needed for reporting commands) |
| Nothing tracked on GNOME/Wayland | expected — see [Display server support](#display-server-support) |
| `cdt` not found after install | add `~/.local/bin` to `PATH` |
| Queue keeps growing | `cdt queue` shows the error; `cdt sync -vv` for details |
| Clock skew warnings | the backend rejects future timestamps; the client clamps them automatically |

Useful log commands:

```bash
cdt start -vv                                   # verbose foreground run
journalctl --user -u crossdevicetracker -f      # systemd service logs
cdt --json doctor                               # machine readable diagnostics
```

---

## License

MIT — see [../../LICENSE](LICENSE).

Part of the [CrossDeviceTracker](https://github.com/Harshit4847/CrossDeviceTracker.Api) family — the backend, the [Windows](https://github.com/Harshit4847/CrossDeviceTracker.Desktop), [Android](https://github.com/Harshit4847/CrossDeviceTracker.Android) and [Web](https://github.com/Harshit4847/CrossDeviceTracker.Web) clients.
