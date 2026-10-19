#!/usr/bin/env bash
#
# Install the CrossDeviceTracker Linux client.
#
#   ./scripts/install.sh                    # venv install + systemd user service
#   CDT_INSTALL_MODE=user ./scripts/install.sh
#   CDT_INSTALL_MODE=system ./scripts/install.sh
#   CDT_SKIP_SERVICE=1 ./scripts/install.sh  # do not touch systemd
#
set -euo pipefail

CLIENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
INSTALL_MODE="${CDT_INSTALL_MODE:-venv}"
SKIP_SERVICE="${CDT_SKIP_SERVICE:-0}"
API_URL="${CDT_API_URL:-http://localhost:5148}"
VENV_DIR="${CDT_VENV_DIR:-$HOME/.local/share/crossdevicetracker/venv}"
BIN_DIR="${CDT_BIN_DIR:-$HOME/.local/bin}"

say()  { printf '\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '\033[32m%s\033[0m\n' "$*"; }
note() { printf '\033[2m%s\033[0m\n' "$*"; }
die()  { printf '\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

PYTHON="${PYTHON:-python3}"
command -v "$PYTHON" >/dev/null 2>&1 || die "python3 is required"

say "CrossDeviceTracker Linux client - installer"
note "  source      : $CLIENT_DIR"
note "  install mode: $INSTALL_MODE"
note "  backend     : $API_URL"
echo

# --------------------------------------------------------------------------- #
# 1. install the package
# --------------------------------------------------------------------------- #
case "$INSTALL_MODE" in
  venv)
    mkdir -p "$VENV_DIR" "$BIN_DIR"
    if [ ! -x "$VENV_DIR/bin/python" ]; then
      say "Creating virtual environment in $VENV_DIR"
      "$PYTHON" -m venv "$VENV_DIR"
    fi
    say "Installing the client into the virtual environment"
    "$VENV_DIR/bin/python" -m pip install --quiet --upgrade pip
    "$VENV_DIR/bin/python" -m pip install --quiet "$CLIENT_DIR"
    ln -sf "$VENV_DIR/bin/cdt" "$BIN_DIR/cdt"
    ok "Installed. Command available as: $BIN_DIR/cdt"
    if ! echo "$PATH" | tr ':' '\n' | grep -qx "$BIN_DIR"; then
      note "  NOTE: $BIN_DIR is not in your PATH."
      note "        Add this to your shell profile:  export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi
    CDT_CMD="$BIN_DIR/cdt"
    ;;

  user)
    say "Installing for the current user (pip --user)"
    "$PYTHON" -m pip install --quiet --user "$CLIENT_DIR" \
      || die "pip --user failed (try CDT_INSTALL_MODE=venv)"
    CDT_CMD="$HOME/.local/bin/cdt"
    ok "Installed as $CDT_CMD"
    ;;

  system)
    say "Installing system wide (may ask for your password)"
    "$PYTHON" -m pip install --quiet "$CLIENT_DIR" || die "system install failed"
    CDT_CMD="$(command -v cdt)"
    ok "Installed as $CDT_CMD"
    ;;

  *)
    die "unknown install mode '$INSTALL_MODE' (expected venv|user|system)"
    ;;
esac

echo

# --------------------------------------------------------------------------- #
# 2. register the login service
# --------------------------------------------------------------------------- #
if [ "$SKIP_SERVICE" != "1" ]; then
  if command -v systemctl >/dev/null 2>&1 && systemctl --user is-system-running >/dev/null 2>&1; then
    say "Installing the systemd user service"
    CDT_API_URL="$API_URL" "$CDT_CMD" service install || {
      note "systemd install failed - falling back to XDG autostart"
      "$CDT_CMD" service autostart || true
    }
  else
    note "systemd user services unavailable - writing an XDG autostart entry instead"
    "$CDT_CMD" service autostart || true
  fi
else
  note "Skipping service installation (CDT_SKIP_SERVICE=1)"
fi

echo
ok "Done."
cat <<'EOF'
Next steps
----------
  1. Pair this machine (needs a link token from the web dashboard):
       cdt link --token <TOKEN>
     or pair in one step with your account:
       cdt link --email you@example.com --password '***'

  2. Check the setup:
       cdt doctor

  3. Track right now (foreground, Ctrl+C to stop):
       cdt start

  4. See your numbers:
       cdt status
       cdt apps --days 7

  Service management:
       cdt service status
       cdt service logs --lines 100
       journalctl --user -u crossdevicetracker.service -f
EOF
