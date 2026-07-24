#!/usr/bin/env bash
# Clean-env dependency audit: build wheel → fresh venv → install wheel+core → pip check + pip-audit.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT_DIR"

OUT_DIR="${TRANSCRIPTX_AUDIT_OUT:-$ROOT_DIR/artifacts/pre-release}"
mkdir -p "$OUT_DIR"

CLEAN_ENV="${TRANSCRIPTX_CLEAN_ENV:-$ROOT_DIR/.release-audit-env}"
rm -rf "$CLEAN_ENV"
python3 -m venv "$CLEAN_ENV"
# shellcheck disable=SC1091
source "$CLEAN_ENV/bin/activate"
python -m pip install -U pip setuptools wheel build pip-audit >/dev/null

echo "==> Building wheel"
python -m build --wheel --outdir "$OUT_DIR/dist"
WHEEL="$(ls -1 "$OUT_DIR/dist"/transcriptx-*.whl | tail -n 1)"
echo "Wheel: $WHEEL"

echo "==> Installing wheel (with core deps from package metadata)"
python -m pip install "$WHEEL"

echo "==> pip check"
python -m pip check | tee "$OUT_DIR/pip-check-clean-env.txt"

echo "==> pip freeze inventory"
python -m pip freeze | tee "$OUT_DIR/pip-freeze-clean-env.txt"

echo "==> pip-audit"
set +e
pip-audit --format json -o "$OUT_DIR/pip-audit-clean-env.json"
AUDIT_RC=$?
pip-audit --format columns | tee "$OUT_DIR/pip-audit-clean-env.txt"
set -e

# Fail on fixable CVEs unless waivers are present (human review of waiver file).
# For Wave 0 automation: non-zero pip-audit fails the script.
if [[ "$AUDIT_RC" -ne 0 ]]; then
  echo "ERROR: pip-audit reported issues (see $OUT_DIR/pip-audit-clean-env.*)."
  echo "Document exceptional waivers in docs/dev/dependency_audit.md before tagging."
  exit "$AUDIT_RC"
fi

echo "OK: clean-env audit passed"
echo "Artefacts under $OUT_DIR"
