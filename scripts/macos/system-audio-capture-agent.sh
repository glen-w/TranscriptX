#!/usr/bin/env bash
# Optional wrapper for roadmap G5. Session-started only — do not KeepAlive.
# Do not attach this to com.transcriptx.inbox-watch.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
if [[ -x "${ROOT}/.venv/bin/python" ]]; then
  PY="${ROOT}/.venv/bin/python"
elif [[ -x "${ROOT}/.transcriptx/bin/python" ]]; then
  PY="${ROOT}/.transcriptx/bin/python"
else
  PY="${PYTHON:-python3}"
fi
exec "${PY}" "${ROOT}/scripts/system-audio-capture.py" "$@"
