#!/usr/bin/env bash
# Docker first-run smoke test: validate, canonicalize, analyze with named-speaker fixture.
# Run from repo root: bash scripts/docker-smoke-test.sh
set -euo pipefail

echo "=== Docker First-Run Smoke Test ==="

# 0. Prep host directories
mkdir -p data/transcripts data/outputs

# 1. Drop in the fixture (idempotent)
cat > data/transcripts/example_meeting_transcriptx.json << 'FIXTURE'
{"schema_version":"1.0","source":{"type":"manual","original_path":"example.wav","imported_at":"2026-02-26T12:00:00Z"},"metadata":{"duration_seconds":30.0,"segment_count":4,"speaker_count":2},"segments":[{"start":0.0,"end":8.0,"speaker":"Alice","text":"Welcome to the meeting. Let us discuss the quarterly results."},{"start":8.0,"end":16.0,"speaker":"Bob","text":"Thanks Alice. Revenue is up fifteen percent compared to last quarter."},{"start":16.0,"end":24.0,"speaker":"Alice","text":"That is great news. What about the customer satisfaction scores?"},{"start":24.0,"end":30.0,"speaker":"Bob","text":"Satisfaction improved across the board. I will share the full report after this."}]}
FIXTURE

# 2. Also drop a non-canonical file for canonicalize test
cp data/transcripts/example_meeting_transcriptx.json data/transcripts/raw_meeting.json

# 3. Validate
echo "--- validate canonical ---"
docker compose run --rm transcriptx transcript validate \
  --file /data/transcripts/example_meeting_transcriptx.json
echo "EXIT: $?"

# 4. Canonicalize (non-canonical -> canonical name)
echo "--- canonicalize ---"
docker compose run --rm transcriptx transcript canonicalize \
  --in /data/transcripts/raw_meeting.json
echo "EXIT: $?"
test -f data/transcripts/raw_meeting_transcriptx.json || { echo "FAIL: canonicalized file not found"; exit 1; }

# 5. Analyze with stats (lightweight, no downloads)
echo "--- analyze stats ---"
docker compose run --rm transcriptx analyze \
  -t /data/transcripts/example_meeting_transcriptx.json \
  --modules stats --skip-confirm
echo "EXIT: $?"

# 6. Analyze with sentiment (needs VADER / HF model -- tests download path)
echo "--- analyze sentiment ---"
docker compose run --rm transcriptx analyze \
  -t /data/transcripts/example_meeting_transcriptx.json \
  --modules sentiment --skip-confirm
echo "EXIT: $?"

# 7. Check output artifacts exist and manifest has manifest_type
OUTDIR="data/outputs/example_meeting_transcriptx"
if [ -d "$OUTDIR" ]; then
  echo "PASS: output directory exists at $OUTDIR"
  find "$OUTDIR" -name '*.json' -o -name '*.csv' 2>/dev/null | head -10
  # Find latest run dir (slug/run_id)
  RUNDIR=$(find "$OUTDIR" -maxdepth 1 -type d -name '20*' | sort | tail -1)
  if [ -n "$RUNDIR" ] && [ -f "$RUNDIR/manifest.json" ]; then
    if grep -q '"manifest_type"' "$RUNDIR/manifest.json" && grep -q '"artifact_manifest"' "$RUNDIR/manifest.json"; then
      echo "PASS: manifest.json contains manifest_type artifact_manifest"
    else
      echo "WARN: manifest.json missing manifest_type (optional for backward compat)"
    fi
  fi
else
  echo "FAIL: no output directory at $OUTDIR"
  exit 1
fi

echo "=== Smoke test complete ==="
