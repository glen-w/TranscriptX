#!/usr/bin/env bash
# Zero stale live-doc/code refs (archive + CHANGELOG history exempt).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

fail=0

# Paths to search (live surfaces)
SEARCH_PATHS=(src tests scripts docs README.md SECURITY.md pyproject.toml Makefile docker-compose.yml Dockerfile)

_rg() {
  # Exclude archive + CHANGELOG + policy docs that intentionally quote forbidden strings
  rg "$@" \
    --glob '!docs/archive/**' \
    --glob '!CHANGELOG.md' \
    --glob '!docs/dev/stocktake_*.md' \
    --glob '!docs/dev/shim_inventory.md' \
    --glob '!docs/dev/dependency_audit.md' \
    --glob '!docs/dev/release_governance.md' \
    --glob '!docs/dev/file_override_behaviour_matrix.md' \
    --glob '!docs/runtime/install_verification_matrix.md' \
    --glob '!scripts/release/**' \
    --glob '!artifacts/**' \
    --glob '!.release-*/**' \
    "${SEARCH_PATHS[@]}" 2>/dev/null || true
}

check_absent() {
  local label="$1"
  local pattern="$2"
  local hits
  hits="$(_rg -n -e "$pattern" || true)"
  if [[ -n "$hits" ]]; then
    echo "ERROR: stale ref ($label) still present:"
    echo "$hits"
    fail=1
  else
    echo "OK: no live hits for $label"
  fi
}

# Stale packaging / identity
check_absent "src/setup.py path refs" 'src/setup\.py'
check_absent "hardcoded 0.42 packaging" 'version=["'\'']0\.42["'\'']'
check_absent "dead ReadTheDocs" 'readthedocs\.io'
check_absent "wrong GitHub org URL" 'github\.com/transcriptx/transcriptx'
# Bare primary install claim (allow documented "not on PyPI" matrix cells)
# Flag advertising as primary without not-on-PyPI caveat in same file is hard;
# instead forbid README/installation primary bare install without git/editable context.
hits_pip="$(_rg -n -e 'pip install transcriptx([^\[]|$)' || true)"
if [[ -n "$hits_pip" ]]; then
  # Allow lines that also mention not on PyPI / from git / -e .
  filtered="$(echo "$hits_pip" | grep -viE 'not on PyPI|from (git|source)|pip install -e|editable|matrix' || true)"
  if [[ -n "$filtered" ]]; then
    echo "ERROR: bare pip install transcriptx advertised without not-on-PyPI / editable caveat:"
    echo "$filtered"
    fail=1
  else
    echo "OK: pip install transcriptx mentions are caveated"
  fi
else
  echo "OK: no bare pip install transcriptx hits"
fi

# TODO/FIXME under src must be zero
todo_hits="$(rg -n -e 'TODO|FIXME' src/ 2>/dev/null || true)"
if [[ -n "$todo_hits" ]]; then
  echo "ERROR: TODO/FIXME under src/:"
  echo "$todo_hits"
  fail=1
else
  echo "OK: zero TODO/FIXME under src/"
fi

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi
echo "OK: stale-ref sweep passed"
