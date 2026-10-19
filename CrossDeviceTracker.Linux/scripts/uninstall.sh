#!/usr/bin/env bash
#
# Remove the CrossDeviceTracker Linux client.
#
#   ./scripts/uninstall.sh              # remove the service + the command
#   CDT_PURGE_DATA=1 ./scripts/uninstall.sh   # also delete the local queue/credentials
#
set -euo pipefail

CLIENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PURGE_DATA="${CDT_PURGE_DATA:-0}"
VENV_DIR="${CDT_VENV_DIR:-$HOME/.local/share/crossdevicetracker/venv}"
BIN_DIR="${CDT_BIN_DIR:-$HOME/.local/bin}"

say() { printf '\033[1m%s\033[0m\n' "$*"; }
ok()  { printf '\033[32m%s\033[0m\n' "$*"; }
note(){ printf '\033[2m%s\033[0m\n' "$*"; }

say "CrossDeviceTracker Linux client - uninstaller"

# 1. stop + remove the login service ---------------------------------------- #
if command -v cdt >/dev/null 2>&1; then
  cdt service uninstall >/dev/null 2>&1 || true
  cdt service autostart-remove >/dev/null 2>&1 || true
  note "removed the login service and the autostart entry"
else
  if command -v systemctl >/dev/null 2>&1; then
    systemctl --user disable --now crossdevicetracker.service >/dev/null 2>&1 || true
    rm -f "$HOME/.config/systemd/user/crossdevicetracker.service"
    systemctl --user daemon-reload >/dev/null 2>&1 || true
  fi
  rm -f "$HOME/.config/autostart/crossdevicetracker.desktop"
fi

# 2. remove the command ------------------------------------------------------ #
if [ -x "$VENV_DIR/bin/python" ]; then
  "$VENV_DIR/bin/python" -m pip uninstall -y crossdevicetracker-linux >/dev/null 2>&1 || true
  rm -rf "$VENV_DIR"
fi
python3 -m pip uninstall -y crossdevicetracker-linux >/dev/null 2>&1 || true
rm -f "$BIN_DIR/cdt"
note "removed the cdt command"

# 3. optional: local data ---------------------------------------------------- #
if [ "$PURGE_DATA" = "1" ]; then
  rm -rf "$HOME/.config/crossdevicetracker" \
         "$HOME/.local/share/crossdevicetracker" \
         "$HOME/.local/state/crossdevicetracker"
  note "deleted credentials, queue and logs"
else
  note "kept $HOME/.config/crossdevicetracker (credentials) and $HOME/.local/share/crossdevicetracker (queue)"
  note "re-run with CDT_PURGE_DATA=1 to delete them as well"
fi

ok "Uninstalled."
