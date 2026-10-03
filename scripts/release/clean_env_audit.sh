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

# Fail on fixable findings, and on any finding not named in the waiver doc.
# A no-fix id that docs/dev/dependency_audit.md already records does not fail CI.
WAIVER_DOC="$ROOT_DIR/docs/dev/dependency_audit.md"
if [[ "$AUDIT_RC" -ne 0 ]]; then
  python - "$OUT_DIR/pip-audit-clean-env.json" "$WAIVER_DOC" <<'PY'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
waiver = Path(sys.argv[2]).read_text(encoding="utf-8")
deps = report.get("dependencies", report if isinstance(report, list) else [])
blocking = []
waived = []
for dep in deps:
    for vuln in dep.get("vulns") or []:
        ids = [vuln.get("id") or ""]
        ids.extend(vuln.get("aliases") or [])
        ids = [i for i in ids if i]
        fixable = bool(vuln.get("fix_versions"))
        named = any(i in waiver for i in ids)
        label = f"{dep.get('name')} {dep.get('version')} ({', '.join(ids)})"
        if fixable or not named:
            blocking.append(label + (" [fix available]" if fixable else " [not in dependency_audit.md]"))
        else:
            waived.append(label)
for line in waived:
    print(f"WAIVED no-fix: {line}")
if blocking:
    print("ERROR: pip-audit findings are not covered by the no-fix waiver:", file=sys.stderr)
    for line in blocking:
        print(f"  {line}", file=sys.stderr)
    sys.exit(1)
if not waived:
    print("ERROR: pip-audit failed and the report had no parsed findings.", file=sys.stderr)
    sys.exit(1)
PY
fi

echo "OK: clean-env audit passed"
echo "Artefacts under $OUT_DIR"
