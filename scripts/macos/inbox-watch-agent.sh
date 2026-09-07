#!/bin/bash
# Login agent for USB → convert → STT → library admit.
# Waits if /Volumes/USB-DISK/RECORD is not mounted.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export PATH="${HOME}/.pyenv/shims:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd "$ROOT"
if [ -x "$ROOT/.venv/bin/python3" ]; then
  PY="$ROOT/.venv/bin/python3"
elif [ -x "$ROOT/.transcriptx/bin/python3" ]; then
  PY="$ROOT/.transcriptx/bin/python3"
else
  PY="$(command -v python3)"
fi
exec "$PY" "$ROOT/scripts/inbox-watch.py" --watch
