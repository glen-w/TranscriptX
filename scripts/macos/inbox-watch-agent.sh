#!/bin/bash
# Login agent for USB → convert → STT → library admit.
# Waits if /Volumes/USB-DISK/RECORD is not mounted.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export PATH="${HOME}/.pyenv/shims:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
cd "$ROOT"
exec /Users/89298/.pyenv/versions/3.10.13/bin/python3 \
  "$ROOT/scripts/inbox-watch.py" --watch
