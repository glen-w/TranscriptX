#!/usr/bin/env bash
# Docker shallow smoke test: verify compose service and web launcher --help.
# Run from repo root: bash scripts/docker-smoke-test.sh
set -euo pipefail

echo "=== Docker Web Launcher Smoke Test ==="

_smoke_recordings_created=
if [ -z "${HOST_RECORDINGS_DIR:-}" ]; then
  HOST_RECORDINGS_DIR="$(mktemp -d "${TMPDIR:-/tmp}/transcriptx-smoke-recordings.XXXXXX")"
  export HOST_RECORDINGS_DIR
  _smoke_recordings_created=1
fi
mkdir -p "$HOST_RECORDINGS_DIR/imports"
cleanup_smoke_recordings() {
  if [ -n "${_smoke_recordings_created:-}" ]; then
    rm -rf "$HOST_RECORDINGS_DIR"
  fi
}
trap cleanup_smoke_recordings EXIT

mkdir -p data/transcripts data/outputs

echo "--- transcriptx --help ---"
docker compose run --rm transcriptx-web transcriptx --help

echo "--- python -m transcriptx.web --help ---"
docker compose run --rm --entrypoint python transcriptx-web -m transcriptx.web --help

echo "=== Smoke test complete ==="
