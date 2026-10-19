#!/usr/bin/env bash
#
# Run the client test suite (standard library unittest - no extra packages).
#
set -euo pipefail

CLIENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$CLIENT_DIR"

PYTHON="${PYTHON:-python3}"

echo "Running the CrossDeviceTracker Linux client test suite..."
"$PYTHON" -m unittest discover -s tests -t . -v "$@"
